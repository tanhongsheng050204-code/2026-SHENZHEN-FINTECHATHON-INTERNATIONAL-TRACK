from datetime import timedelta
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import demo
from app.auth.dependencies import CurrentUser
from app.auth.provider import provider
from app.auth.sessions import (
    COOKIE,
    accept_tokens,
    aware,
    bind_membership,
    create_session,
    credentials,
    digest,
    resolve_session,
    token_claims,
    validate_origin,
)
from app.config import get_settings
from app.contracts.auth import (
    CodeRequest,
    CompanySetup,
    EmailRequest,
    PasswordRequest,
    PasswordSignIn,
    SessionResponse,
    SignUp,
    TotpChallenge,
    TotpEnrollment,
    TotpVerify,
)
from app.db import get_db
from app.models import AuthUserRole, BackendAuthSession, Tenant, utcnow
from app.schemas import AuthMeResponse
from app.security import rate_limit
from app.services.workflow_audit import write_workflow_event

router = APIRouter(prefix="/auth", tags=["auth"])


def _view(db: Session, row: BackendAuthSession, csrf=None) -> SessionResponse:
    assignment = db.get(AuthUserRole, (row.user_id, row.tenant_id)) if row.tenant_id else None
    if not row.email_verified:
        state = "email_code_required"
    elif (
        row.purpose == "recovery"
        and not row.password_verified
        and (row.aal != "aal2" or row.mfa_verified_at is None)
        and any(
            f.get("status") == "verified" and f.get("factor_type") == "totp"
            for f in credentials(row).get("user", {}).get("factors", [])
        )
    ):
        state = "mfa_required"
    elif not row.password_verified:
        state = "password_required"
    elif (row.aal != "aal2" or row.mfa_verified_at is None) and (
        not assignment or assignment.user_role in _required_roles(db, row)
    ):
        state = (
            "mfa_required" if assignment and assignment.mfa_enrolled else "mfa_enrollment_required"
        )
    elif not assignment:
        state = "company_setup_required"
    else:
        state = "authenticated"
    return SessionResponse(
        state=state,
        csrf_token=csrf,
        user_id=row.user_id,
        tenant_id=row.tenant_id,
        role=assignment.user_role if assignment else None,
        job_functions=assignment.job_functions if assignment else [],
        aal=row.aal,
    )


def _required_roles(db, row):
    from app.models import TenantSettingsRecord

    settings = db.get(TenantSettingsRecord, row.tenant_id) if row.tenant_id else None
    return (
        settings.document["security"]["mfa_required_roles"]
        if settings
        else ["owner_director", "finance_ops", "compliance"]
    )


def _bootstrap(request: Request, db: Session) -> BackendAuthSession:
    row = resolve_session(db, request)
    if not row.email_verified:
        raise HTTPException(403, "email_verification_required")
    token_claims(row)
    return row


def _not_demo(row: BackendAuthSession) -> None:
    if demo.is_demo_email(credentials(row).get("email")):
        raise HTTPException(403, "demo_account_locked")


def _recent_mfa(row: BackendAuthSession) -> bool:
    if row.aal != "aal2" or row.mfa_verified_at is None:
        return False
    age = (utcnow() - aware(row.mfa_verified_at)).total_seconds()
    return 0 <= age <= get_settings().auth_step_up_seconds


@router.get("/me", response_model=AuthMeResponse)
def me(principal: CurrentUser) -> AuthMeResponse:
    from app.services.identity import mask_email

    return AuthMeResponse(
        user_id=str(principal.user_id), email=mask_email(principal.email or ""), role=principal.role
    )


@router.post("/sign-in", response_model=SessionResponse)
def sign_in(
    body: PasswordSignIn, request: Request, response: Response, db: Session = Depends(get_db)
):
    validate_origin(request)
    result = provider.call("POST", "/token?grant_type=password", payload=body.model_dump())
    row, csrf = create_session(db, response, {"email": body.email}, "signin")
    accept_tokens(row, result, email=body.email)
    row.password_verified = True
    provider.call("POST", "/otp", payload={"email": body.email, "create_user": False})
    db.commit()
    return _view(db, row, csrf)


@router.get("/demo/status")
def demo_status() -> dict:
    return {"available": demo.enabled()}


@router.post(
    "/demo",
    response_model=SessionResponse,
    dependencies=[Depends(rate_limit.limit("demo-sign-in", 20))],
)
def demo_sign_in(request: Request, response: Response, db: Session = Depends(get_db)):
    """Sign in to the synthetic company with the usual password and authenticator steps,
    run by the server with secrets only it holds."""
    validate_origin(request)
    if not demo.enabled():
        raise HTTPException(404, "demo_not_available")
    settings = get_settings()
    email = settings.demo_email
    result = provider.call(
        "POST",
        "/token?grant_type=password",
        payload={"email": email, "password": settings.demo_password},
    )
    row, csrf = create_session(db, response, {"email": email}, "signin")
    accept_tokens(row, result, email=email)
    # The server provisioned this mailbox, so there is no inbox for an email code to reach.
    row.email_verified = True
    row.password_verified = True
    assignment = bind_membership(db, row)
    if assignment is None or assignment.tenant_id != settings.demo_tenant_id:
        row.revoked_at = utcnow()
        db.commit()
        raise HTTPException(503, "demo_not_provisioned")
    token = credentials(row)["access_token"]
    user = provider.call("GET", "/user", token=token)
    factor = next(
        (
            f["id"]
            for f in user.get("factors", [])
            if f.get("factor_type") == "totp" and f.get("status") == "verified"
        ),
        None,
    )
    if factor is None:
        row.revoked_at = utcnow()
        db.commit()
        raise HTTPException(503, "demo_not_provisioned")
    challenge = provider.call("POST", f"/factors/{factor}/challenge", payload={}, token=token)
    challenge_id = challenge["id"]
    verified = provider.call(
        "POST",
        f"/factors/{factor}/verify",
        token=token,
        payload={"challenge_id": str(challenge_id), "code": demo.totp(settings.demo_totp_secret)},
    )
    accept_tokens(row, verified, email=email)
    if row.aal != "aal2":
        row.revoked_at = utcnow()
        db.commit()
        raise HTTPException(503, "mfa_verification_failed")
    row.mfa_verified_at = utcnow()
    assignment.mfa_enrolled = True
    write_workflow_event(
        db,
        event_type="demo_sign_in",
        actor_role=assignment.user_role,
        actor_ref="demo-sign-in",
        resource_type="auth_user",
        resource_id=row.user_id,
        event_payload={"aal": row.aal},
        tenant_id=assignment.tenant_id,
    )
    db.commit()
    return _view(db, row, csrf)


@router.get("/demo/code")
def demo_code(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    """The demo account's current authenticator code, for its own session only."""
    row = _bootstrap(request, db)
    db.commit()
    if not demo.is_demo_email(credentials(row).get("email")):
        raise HTTPException(404, "not_found")
    response.headers["Cache-Control"] = "no-store"
    return {"code": demo.totp(get_settings().demo_totp_secret), "seconds_left": demo.seconds_left()}


@router.post("/sign-up", response_model=SessionResponse)
def sign_up(body: SignUp, request: Request, response: Response, db: Session = Depends(get_db)):
    validate_origin(request)
    provider.call("POST", "/signup", payload=body.model_dump())
    row, csrf = create_session(db, response, {"email": body.email}, "signup")
    row.password_verified = True
    db.commit()
    return _view(db, row, csrf)


@router.post("/recovery", response_model=SessionResponse)
def recovery(
    body: EmailRequest, request: Request, response: Response, db: Session = Depends(get_db)
):
    validate_origin(request)
    provider.call("POST", "/recover", payload={"email": body.email})
    row, csrf = create_session(db, response, {"email": body.email}, "recovery")
    db.commit()
    return _view(db, row, csrf)


@router.post("/invitation", response_model=SessionResponse)
def invitation(
    body: EmailRequest, request: Request, response: Response, db: Session = Depends(get_db)
):
    validate_origin(request)
    row, csrf = create_session(db, response, {"email": body.email}, "invite")
    db.commit()
    return _view(db, row, csrf)


@router.post("/email/verify", response_model=SessionResponse)
def verify_email(body: CodeRequest, request: Request, db: Session = Depends(get_db)):
    row = resolve_session(db, request)
    if row.email_verified:
        raise HTTPException(409, "email_already_verified")
    email = credentials(row)["email"]
    kind = {"signup": "signup", "signin": "magiclink", "invite": "invite", "recovery": "recovery"}[
        row.purpose
    ]
    result = provider.call(
        "POST", "/verify", payload={"type": kind, "email": email, "token": body.code}
    )
    accept_tokens(row, result, email=email)
    row.email_verified = True
    bind_membership(db, row)
    db.commit()
    return _view(db, row)


@router.get("/session", response_model=SessionResponse)
def session(request: Request, response: Response, db: Session = Depends(get_db)):
    import secrets

    row = resolve_session(db, request)
    if row.email_verified:
        token_claims(row)
    data = credentials(row)
    csrf = data.get("csrf_token")
    if not csrf:
        # Upgrade sessions created before stable encrypted CSRF storage.
        from app.auth.sessions import save_credentials

        csrf = secrets.token_urlsafe(32)
        row.csrf_hash = digest(csrf)
        save_credentials(row, {**data, "csrf_token": csrf})
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return _view(db, row, csrf)


@router.post("/password", response_model=SessionResponse)
def set_password(body: PasswordRequest, request: Request, db: Session = Depends(get_db)):
    row = _bootstrap(request, db)
    if row.purpose not in {"invite", "recovery"} or row.password_verified:
        raise HTTPException(403, "password_reset_not_authorized")
    user = provider.call("GET", "/user", token=credentials(row)["access_token"])
    if any(
        f.get("factor_type") == "totp" and f.get("status") == "verified"
        for f in user.get("factors", [])
    ) and not _recent_mfa(row):
        raise HTTPException(403, "step_up_required")
    provider.call("PUT", "/user", token=credentials(row)["access_token"], payload=body.model_dump())
    row.password_verified = True
    row.aal = "aal1"
    row.mfa_verified_at = None
    db.execute(
        update(BackendAuthSession)
        .where(BackendAuthSession.user_id == row.user_id, BackendAuthSession.id != row.id)
        .values(revoked_at=utcnow())
    )
    db.commit()
    return _view(db, row)


@router.get("/mfa/factors")
def factors(request: Request, db: Session = Depends(get_db)):
    row = _bootstrap(request, db)
    user = provider.call("GET", "/user", token=credentials(row)["access_token"])
    db.commit()
    return {
        "factors": [
            {"id": factor["id"], "status": factor["status"], "type": factor["factor_type"]}
            for factor in user.get("factors", [])
            if factor.get("factor_type") == "totp"
        ]
    }


@router.post("/mfa/enroll", response_model=TotpEnrollment)
def enroll(request: Request, response: Response, db: Session = Depends(get_db)):
    row = _bootstrap(request, db)
    _not_demo(row)
    if not row.password_verified:
        raise HTTPException(403, "password_required")
    user = provider.call("GET", "/user", token=credentials(row)["access_token"])
    if any(f.get("status") == "verified" for f in user.get("factors", [])) and not _recent_mfa(row):
        raise HTTPException(403, "step_up_required")
    result = provider.call(
        "POST",
        "/factors",
        token=credentials(row)["access_token"],
        payload={"factor_type": "totp", "friendly_name": "DuitDuit"},
    )
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return TotpEnrollment(factor_id=result["id"], **result["totp"])


@router.post("/mfa/{factor_id}/challenge", response_model=TotpChallenge)
def challenge(factor_id: UUID, request: Request, db: Session = Depends(get_db)):
    row = _bootstrap(request, db)
    result = provider.call(
        "POST",
        f"/factors/{factor_id}/challenge",
        payload={},
        token=credentials(row)["access_token"],
    )
    db.commit()
    return TotpChallenge(challenge_id=result["id"])


@router.post("/mfa/verify", response_model=SessionResponse)
def verify_totp(body: TotpVerify, request: Request, db: Session = Depends(get_db)):
    row = _bootstrap(request, db)
    data = credentials(row)
    result = provider.call(
        "POST",
        f"/factors/{body.factor_id}/verify",
        token=data["access_token"],
        payload={"challenge_id": str(body.challenge_id), "code": body.code},
    )
    accept_tokens(row, result, email=data["email"])
    if row.aal != "aal2":
        raise HTTPException(403, "mfa_verification_failed")
    row.mfa_verified_at = utcnow()
    if row.tenant_id:
        assignment = db.get(AuthUserRole, (row.user_id, row.tenant_id))
        assignment.mfa_enrolled = True
    db.commit()
    return _view(db, row)


@router.post("/company", response_model=SessionResponse)
def company(body: CompanySetup, request: Request, db: Session = Depends(get_db)):
    from app.services.identity import mask_email
    from app.services.tenant_settings import initialize_settings

    row = _bootstrap(request, db)
    if (
        row.purpose != "signup"
        or not row.password_verified
        or row.aal != "aal2"
        or row.mfa_verified_at is None
    ):
        raise HTTPException(403, "owner_mfa_required")
    if bind_membership(db, row):
        raise HTTPException(409, "already_provisioned")
    tenant_id = str(uuid4())
    try:
        db.add(Tenant(id=tenant_id, name=body.company_name, slug=body.slug))
        db.flush()
        db.add(
            AuthUserRole(
                user_id=row.user_id,
                tenant_id=tenant_id,
                user_role="owner_director",
                job_functions=["owner"],
                active=True,
                mfa_enrolled=True,
                email_masked=mask_email(credentials(row)["email"]),
                display_name="Owner",
            )
        )
        initialize_settings(db, tenant_id, body.company_name)
        row.tenant_id = tenant_id
        row.expires_at = utcnow() + timedelta(hours=get_settings().auth_session_hours)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "company_already_exists") from error
    return _view(db, row)


@router.post("/sign-out", status_code=204)
def sign_out(request: Request, response: Response, db: Session = Depends(get_db)):
    row = resolve_session(db, request)
    row.revoked_at = utcnow()
    data = credentials(row)
    db.commit()
    response.delete_cookie(
        COOKIE, path="/", secure=get_settings().auth_cookie_secure, httponly=True, samesite="lax"
    )
    if data.get("access_token"):
        try:
            provider.call("POST", "/logout?scope=local", token=data["access_token"])
        except HTTPException:
            # API sessions are already durably revoked; retrying provider sign-out
            # must not prevent clearing the browser's cookie.
            pass


@router.post("/sign-out-everywhere", status_code=204)
def sign_out_everywhere(request: Request, response: Response, db: Session = Depends(get_db)):
    row = _bootstrap(request, db)
    _not_demo(row)
    data = credentials(row)
    db.execute(
        update(BackendAuthSession)
        .where(BackendAuthSession.user_id == row.user_id)
        .values(revoked_at=utcnow())
    )
    db.commit()
    response.delete_cookie(
        COOKIE, path="/", secure=get_settings().auth_cookie_secure, httponly=True, samesite="lax"
    )
    try:
        provider.call("POST", "/logout?scope=global", token=data["access_token"])
    except HTTPException:
        pass
