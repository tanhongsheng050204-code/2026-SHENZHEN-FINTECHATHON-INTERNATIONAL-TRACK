from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.jwt import AccessTokenError, verify_access_token
from app.auth.principal import AuthPrincipal
from app.auth.sessions import aware, resolve_session, token_claims
from app.config import get_settings
from app.db import get_db, set_rls_context
from app.models import AuthUserRole, TenantSettingsRecord
from app.schemas import UserRole

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthPrincipal:
    session = None
    if request.cookies.get("finbrain_session"):
        session = resolve_session(db, request)
        if not session.email_verified or not session.password_verified or not session.tenant_id:
            raise HTTPException(403, "onboarding_required")
        claims = token_claims(session)
        claims["tenant_id"] = session.tenant_id
        claims.pop("user_role", None)
    elif credentials and get_settings().auth_allow_bearer:
        try:
            claims = verify_access_token(credentials.credentials)
        except AccessTokenError as error:
            raise HTTPException(401, str(error)) from error
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication_required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if "tenant_id" not in claims:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_tenant_claim",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_id = UUID(str(claims["sub"]))
        tenant_id = UUID(str(claims["tenant_id"]))
    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_identity_claims",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    assignment = db.get(AuthUserRole, (str(user_id), str(tenant_id)))
    if assignment is None or not assignment.active:
        raise HTTPException(status_code=403, detail="user_not_provisioned")
    try:
        role = UserRole(assignment.user_role)
    except ValueError as error:
        raise HTTPException(status_code=403, detail="invalid_user_role") from error
    token_role = claims.get("user_role")
    if token_role is not None and token_role != role.value:
        raise HTTPException(status_code=403, detail="stale_user_role_claim")
    principal = AuthPrincipal(
        user_id=user_id,
        email=claims.get("email"),
        role=role,
        tenant_id=tenant_id,
        job_functions=tuple(assignment.job_functions),
        aal=claims.get("aal", "aal1"),
        mfa_verified_at=session.mfa_verified_at if session else _mfa_time(claims),
        session_id=session.id if session else None,
    )
    setting = db.get(TenantSettingsRecord, str(tenant_id))
    mandatory = (
        setting.document["security"]["mfa_required_roles"]
        if setting
        else ["owner_director", "finance_ops", "compliance"]
    )
    if (
        role.value in mandatory
        and (principal.aal != "aal2" or principal.mfa_verified_at is None)
        and request.url.path != "/auth/me"
    ):
        raise HTTPException(
            403, "mfa_enrollment_required" if not assignment.mfa_enrolled else "mfa_required"
        )
    if session:
        db.commit()
    db.info["finbrain_disclosure_allowed"] = has_recent_mfa(principal)
    db.info["finbrain_request_tenant"] = str(principal.tenant_id)
    db.info["finbrain_request_actor"] = principal.actor_ref
    db.info["finbrain_request_role"] = principal.role.value
    db.info["finbrain_request_jobs"] = principal.job_functions
    set_rls_context(
        db,
        user_id=str(principal.user_id),
        user_role=principal.role.value,
        actor_ref=principal.actor_ref,
        tenant_id=str(principal.tenant_id),
    )
    return principal


def _mfa_time(claims: dict) -> datetime | None:
    times = [
        method.get("timestamp")
        for method in claims.get("amr", [])
        if method.get("method") == "totp" and isinstance(method.get("timestamp"), (int, float))
    ]
    return datetime.fromtimestamp(max(times), UTC) if times else None


def has_recent_mfa(principal: AuthPrincipal) -> bool:
    if principal.aal != "aal2" or principal.mfa_verified_at is None:
        return False
    age = (datetime.now(UTC) - aware(principal.mfa_verified_at)).total_seconds()
    return 0 <= age <= get_settings().auth_step_up_seconds


CurrentUser = Annotated[AuthPrincipal, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[AuthPrincipal], AuthPrincipal]:
    allowed = frozenset(roles)

    def dependency(principal: CurrentUser) -> AuthPrincipal:
        if principal.role not in allowed:
            raise HTTPException(status_code=403, detail="insufficient_role")
        return principal

    return dependency


def require_step_up(*roles: UserRole) -> Callable[[AuthPrincipal], AuthPrincipal]:
    def dependency(principal: CurrentUser) -> AuthPrincipal:
        if roles and principal.role not in roles:
            raise HTTPException(403, "insufficient_role")
        if not has_recent_mfa(principal):
            raise HTTPException(403, "step_up_required")
        return principal

    return dependency
