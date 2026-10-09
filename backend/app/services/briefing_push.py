"""Opt-in morning briefings by email and Telegram.

Off by default. A person turns them on in My preferences; the choice is an event on
the tenant's audit chain, with their email and Telegram chat id encrypted, so the
chain never holds either in clear. Every morning at BRIEFING_PUSH_HOUR in the
application timezone each opted-in person gets one briefing per channel, built
for their current role and positions with ranges and counts only (briefing.push_text).
Each delivery is recorded, which also stops a second send that day.
"""

import base64
import datetime as dt
import json
import smtplib
from email.message import EmailMessage
from uuid import UUID

import httpx
from sqlalchemy import select

from app.auth.principal import AuthPrincipal
from app.config import get_settings
from app.models import AuthUserRole, WorkflowAuditEntry
from app.schemas import UserRole
from app.security.crypto import decrypt_value, derive_key_from_secret, encrypt_value
from app.services import briefing
from app.services.workflow_audit import write_workflow_event

_PREFERENCE = "briefing_preference"
_PUSHED = "briefing_pushed"


def _key() -> bytes:
    secret = get_settings().vault_wrapping_secret.encode()
    return derive_key_from_secret(secret, info=b"duitduit-briefing-contacts")


def _seal(user_id: str, contacts: dict) -> dict:
    ciphertext, nonce = encrypt_value(json.dumps(contacts), _key(), user_id.encode())
    return {
        "sealed": base64.b64encode(ciphertext).decode(),
        "nonce": base64.b64encode(nonce).decode(),
    }


def _open(user_id: str, payload: dict) -> dict:
    return json.loads(
        decrypt_value(
            base64.b64decode(payload["sealed"]),
            base64.b64decode(payload["nonce"]),
            _key(),
            user_id.encode(),
        )
    )


def _preferences(db, tenant_id: str) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for row in db.scalars(
        select(WorkflowAuditEntry)
        .where(
            WorkflowAuditEntry.tenant_id == tenant_id,
            WorkflowAuditEntry.event_type == _PREFERENCE,
        )
        .order_by(WorkflowAuditEntry.id)
    ):
        latest[row.resource_id] = row.event_payload
    return latest


def preference(db, principal: AuthPrincipal) -> dict:
    payload = _preferences(db, str(principal.tenant_id)).get(str(principal.user_id))
    if payload is None:
        return {"email": False, "telegram": False}
    contacts = _open(str(principal.user_id), payload)
    return {"email": bool(contacts.get("email")), "telegram": bool(contacts.get("telegram"))}


def set_preference(
    db, principal: AuthPrincipal, *, email: bool, telegram_chat_id: str | None
) -> dict:
    user_id = str(principal.user_id)
    contacts = {
        "email": principal.email if email else None,
        "telegram": telegram_chat_id,
    }
    write_workflow_event(
        db,
        event_type=_PREFERENCE,
        actor_role=principal.role.value,
        actor_ref=user_id,
        resource_type="user_preference",
        resource_id=user_id,
        event_payload=_seal(user_id, contacts),
        tenant_id=str(principal.tenant_id),
    )
    db.commit()
    return preference(db, principal)


def _send_email(to: str, subject: str, body: str) -> None:
    settings = get_settings()
    username = settings.email_smtp_username or settings.email_imap_username
    password = settings.email_smtp_password or settings.email_imap_password
    if not settings.email_smtp_configured:
        raise RuntimeError("email_not_configured")
    message = EmailMessage()
    message["From"] = settings.email_smtp_from_address or username
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(
        settings.email_smtp_host,
        settings.email_smtp_port,
        timeout=settings.email_send_timeout_seconds,
    ) as smtp:
        if settings.email_smtp_use_starttls:
            smtp.starttls()
        smtp.login(username, password)
        smtp.send_message(message)


def _send_telegram(chat_id: str, body: str) -> None:
    token = get_settings().telegram_bot_token
    if not token:
        raise RuntimeError("telegram_not_configured")
    response = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": int(chat_id), "text": body},
        timeout=10,
    )
    response.raise_for_status()


def _already(db, tenant_id: str, key: str) -> bool:
    return (
        db.scalar(
            select(WorkflowAuditEntry.id).where(
                WorkflowAuditEntry.tenant_id == tenant_id,
                WorkflowAuditEntry.event_type == _PUSHED,
                WorkflowAuditEntry.resource_id == key,
            )
        )
        is not None
    )


def _deliver(db, principal: AuthPrincipal, contacts: dict, day: dt.date, *, force: bool) -> list:
    tenant_id = str(principal.tenant_id)
    body = briefing.push_text(db, principal)
    sent = []
    targets = [("email", contacts.get("email")), ("telegram", contacts.get("telegram"))]
    for channel, address in targets:
        if not address:
            continue
        key = f"{principal.user_id}:{day.isoformat()}:{channel}"
        if not force and _already(db, tenant_id, key):
            continue
        try:
            if channel == "email":
                _send_email(address, "Your DuitDuit morning briefing", body)
            else:
                _send_telegram(address, body)
        except Exception:
            continue
        write_workflow_event(
            db,
            event_type=_PUSHED,
            actor_role="system",
            actor_ref="briefing-push",
            resource_type="briefing_push",
            resource_id=key + (":manual" if force else ""),
            event_payload={"channel": channel, "day": day.isoformat(), "manual": force},
            tenant_id=tenant_id,
        )
        db.commit()
        sent.append(channel)
    return sent


def send_now(db, principal: AuthPrincipal) -> list[str]:
    payload = _preferences(db, str(principal.tenant_id)).get(str(principal.user_id))
    if payload is None:
        return []
    contacts = _open(str(principal.user_id), payload)
    return _deliver(db, principal, contacts, dt.date.today(), force=True)


def _principal_for(db, tenant_id: str, user_id: str, contacts: dict) -> AuthPrincipal | None:
    # The current membership is the only authority: no active row, no briefing.
    row = db.get(AuthUserRole, (user_id, tenant_id))
    if row is None or not row.active:
        return None
    role = UserRole(row.user_role)
    jobs = tuple(row.job_functions or ())
    extra = {}
    if "job_functions" in getattr(AuthPrincipal, "__dataclass_fields__", {}):
        extra["job_functions"] = jobs
    return AuthPrincipal(
        user_id=UUID(user_id),
        email=contacts.get("email"),
        role=role,
        tenant_id=UUID(tenant_id),
        **extra,
    )


def run_due(db, now_local: dt.datetime) -> int:
    """Send every opted-in person's briefing once, at the configured hour. Returns sends."""
    if now_local.hour != get_settings().briefing_push_hour:
        return 0
    tenants = db.scalars(
        select(WorkflowAuditEntry.tenant_id)
        .where(WorkflowAuditEntry.event_type == _PREFERENCE)
        .distinct()
    ).all()
    count = 0
    for tenant_id in tenants:
        for user_id, payload in _preferences(db, str(tenant_id)).items():
            contacts = _open(user_id, payload)
            if not (contacts.get("email") or contacts.get("telegram")):
                continue
            person = _principal_for(db, str(tenant_id), user_id, contacts)
            if person is None:
                continue
            count += len(_deliver(db, person, contacts, now_local.date(), force=False))
    return count
