"""The shared demo account for the synthetic company.

Judges sign in with one click, but nothing is bypassed: the API signs in to the
identity provider with a password and an authenticator code exactly as a person
would, using secrets that only the server holds. In the demo company:
- the authenticator code is shown to the demo session itself, like a phone beside the screen;
- email and Telegram deliveries are recorded as simulated and never leave the system;
- team changes, global sign-out and new authenticators are closed, so one judge
  cannot lock the next one out.
"""

import base64
import hashlib
import hmac
import struct
import time

from fastapi import HTTPException

from app.auth.principal import AuthPrincipal
from app.config import get_settings

STEP = 30


def totp(secret: str, *, at: float | None = None, digits: int = 6) -> str:
    """RFC 6238 time-based code (SHA-1, 30-second steps), as authenticator apps compute it."""
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    counter = int((time.time() if at is None else at) // STEP)
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    value = struct.unpack(">I", mac[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10**digits).zfill(digits)


def seconds_left() -> int:
    return STEP - int(time.time()) % STEP


def enabled() -> bool:
    settings = get_settings()
    return bool(
        settings.demo_sign_in_enabled
        and settings.demo_email
        and settings.demo_password
        and settings.demo_totp_secret
        and settings.demo_tenant_id
    )


def is_demo_tenant(tenant_id: str | None) -> bool:
    settings = get_settings()
    return bool(
        settings.demo_sign_in_enabled and tenant_id and str(tenant_id) == settings.demo_tenant_id
    )


def is_demo_email(email: str | None) -> bool:
    return enabled() and (email or "").casefold() == get_settings().demo_email.casefold()


def forbid_in_demo(principal: AuthPrincipal) -> None:
    if is_demo_tenant(str(principal.tenant_id)):
        raise HTTPException(403, "demo_company_read_only")
