import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.jwt import AccessTokenError, verify_access_token
from app.auth.provider import provider
from app.config import get_settings
from app.models import AuthUserRole, BackendAuthSession, TenantSettingsRecord, utcnow
from app.security.crypto import decrypt_value, derive_key_from_secret, encrypt_value

COOKIE = "finbrain_session"
UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def validate_origin(request: Request) -> None:
    # Exact origin allowlist, including login CSRF. Regex CORS cannot widen this list.
    if (
        request.method in UNSAFE
        and request.headers.get("origin") not in get_settings().cors_origin_list
    ):
        raise HTTPException(403, "csrf_origin_denied")


def _key() -> bytes:
    return derive_key_from_secret(
        get_settings().vault_wrapping_secret.encode(), info=b"finbrain:backend-auth-session:v1"
    )


def save_credentials(row: BackendAuthSession, data: dict) -> None:
    row.credential_ciphertext, row.credential_nonce = encrypt_value(
        json.dumps(data), _key(), row.id.encode()
    )


def credentials(row: BackendAuthSession) -> dict:
    return json.loads(
        decrypt_value(row.credential_ciphertext, row.credential_nonce, _key(), row.id.encode())
    )


def create_session(
    db: Session, response: Response, data: dict, purpose: str
) -> tuple[BackendAuthSession, str]:
    handle, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    row = BackendAuthSession(
        id=digest(handle),
        csrf_hash=digest(csrf),
        purpose=purpose,
        expires_at=utcnow() + timedelta(minutes=15),
    )
    save_credentials(row, {**data, "csrf_token": csrf})
    db.add(row)
    db.flush()
    response.set_cookie(
        COOKIE,
        handle,
        max_age=get_settings().auth_session_hours * 3600,
        httponly=True,
        secure=get_settings().auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return row, csrf


def resolve_session(db: Session, request: Request, *, touch=True) -> BackendAuthSession:
    handle = request.cookies.get(COOKIE)
    if not handle:
        raise HTTPException(401, "authentication_required")
    # Locks serialize refresh-token rotation and revocation across API processes.
    row = db.scalar(
        select(BackendAuthSession).where(BackendAuthSession.id == digest(handle)).with_for_update()
    )
    now = utcnow()
    if row is None or row.revoked_at or aware(row.expires_at) <= now:
        raise HTTPException(401, "session_expired")
    if request.method in UNSAFE:
        validate_origin(request)
        supplied = request.headers.get("x-csrf-token", "")
        if not supplied or not hmac.compare_digest(digest(supplied), row.csrf_hash):
            raise HTTPException(403, "csrf_token_invalid")
    if row.tenant_id and row.user_id:
        assignment = db.get(AuthUserRole, (row.user_id, row.tenant_id))
        if (
            assignment is None
            or not assignment.active
            or assignment.session_generation != row.generation
        ):
            raise HTTPException(401, "session_revoked")
        setting = db.get(TenantSettingsRecord, row.tenant_id)
        idle = setting.document["security"]["session_idle_minutes"] if setting else 30
        if (now - aware(row.last_seen_at)).total_seconds() >= idle * 60:
            row.revoked_at = now
            db.commit()
            raise HTTPException(401, "session_idle_timeout")
        if touch:
            assignment.last_active_at = now
    if touch:
        row.last_seen_at = now
    request.state.auth_session = row
    return row


def token_claims(row: BackendAuthSession) -> dict:
    data = credentials(row)
    if not data.get("access_token"):
        raise HTTPException(401, "email_verification_required")
    # Provider expiry is server data; the refreshed JWT is still signature-verified below.
    if data.get("expires_at", 0) <= utcnow().timestamp() + 30:
        result = provider.call(
            "POST",
            "/token?grant_type=refresh_token",
            payload={"refresh_token": data["refresh_token"]},
        )
        result["email"] = data["email"]
        result["csrf_token"] = data.get("csrf_token")
        result["expires_at"] = utcnow().timestamp() + int(result.get("expires_in", 3600))
        data = result
    claims = _verified(data["access_token"])
    if str(UUID(claims["sub"])) != row.user_id:
        raise HTTPException(401, "session_identity_mismatch")
    save_credentials(row, data)
    row.aal = claims.get("aal", "aal1")
    return claims


def accept_tokens(row: BackendAuthSession, result: dict, *, email: str) -> dict:
    claims = _verified(result["access_token"])
    user_id = str(UUID(claims["sub"]))
    if row.user_id and row.user_id != user_id:
        raise HTTPException(401, "session_identity_mismatch")
    if str(claims.get("email", "")).casefold() != email.casefold():
        raise HTTPException(401, "session_identity_mismatch")
    row.user_id = user_id
    row.aal = claims.get("aal", "aal1")
    result = {**result, "email": email, "csrf_token": credentials(row).get("csrf_token")}
    if "expires_at" not in result:
        result["expires_at"] = utcnow().timestamp() + int(result.get("expires_in", 3600))
    save_credentials(row, result)
    return claims


def _verified(token: str) -> dict:
    try:
        return verify_access_token(token)
    except AccessTokenError as error:
        code = str(error)
        raise HTTPException(
            503 if code in {"jwks_unavailable", "supabase_auth_not_configured"} else 401, code
        ) from error


def bind_membership(db: Session, row: BackendAuthSession) -> AuthUserRole | None:
    assignment = db.scalar(
        select(AuthUserRole)
        .where(AuthUserRole.user_id == row.user_id, AuthUserRole.active.is_(True))
        .order_by(AuthUserRole.created_at, AuthUserRole.tenant_id)
        .limit(1)
    )
    if assignment:
        row.tenant_id = assignment.tenant_id
        row.generation = assignment.session_generation
        row.expires_at = utcnow() + timedelta(hours=get_settings().auth_session_hours)
        data = credentials(row)
        email = data.get("email", "")
        if "@" in email:
            local, domain = email.split("@", 1)
            assignment.email_masked = f"{local[:1]}***@{domain}"
        factors = data.get("user", {}).get("factors")
        if factors is not None:
            assignment.mfa_enrolled = any(
                factor.get("factor_type") == "totp" and factor.get("status") == "verified"
                for factor in factors
            )
    return assignment
