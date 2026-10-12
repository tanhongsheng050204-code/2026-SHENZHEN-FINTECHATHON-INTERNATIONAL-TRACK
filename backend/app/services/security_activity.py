"""Sign-in activity and the security feed.

A completed sign-in is kept as "sign_in_recorded" on the company's workflow chain
with the browser family, the operating system, how the person signed in, and a
device fingerprint: an HMAC of the person, browser, system and network (the first
two parts of the address). The address itself and the full browser string are
never stored. A sign-in from a fingerprint the person has not used before is
flagged as a new device; the very first sign-in only sets the baseline.

The security feed reads the chain for the events that matter to an owner or
Compliance (keys, roles, kill switches, autonomy, settings, shared links, erasures,
exports, incidents, new devices) and gives each a fixed title and severity. It
shows kinds and roles only, never payloads.
"""

import datetime as dt
import hashlib
import hmac
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.contracts.security import SecurityEvent, SignIn
from app.models import AuthUserRole, WorkflowAuditEntry
from app.security import rate_limit
from app.services.workflow_audit import chain_scalars, write_workflow_event

SIGN_IN = "sign_in_recorded"
FEED_DAYS = 30
SIGN_INS_SHOWN = 20

_BROWSERS = (
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("Firefox/", "Firefox"),
    ("Chrome/", "Chrome"),
    ("Safari/", "Safari"),
)
_SYSTEMS = (
    ("iPhone", "iOS"),
    ("iPad", "iOS"),
    ("Android", "Android"),
    ("Windows", "Windows"),
    ("Mac OS X", "macOS"),
    ("Linux", "Linux"),
)

# kind → (severity, title). Anything not listed is not a security event.
FEED: dict[str, tuple[str, str]] = {
    "incident_opened": ("critical", "A security incident was recorded"),
    "incident_step": ("info", "An incident step was completed"),
    "api_key_created": ("warning", "An AI connection key was created"),
    "api_key_revoked": ("info", "An AI connection key was revoked"),
    "team.invited": ("info", "A team member was invited"),
    "team.updated": ("warning", "A team member's role or access changed"),
    "team.sessions_revoked": ("info", "A team member was signed out everywhere"),
    "agent.kill_switch": ("warning", "An agent kill switch was changed"),
    "autonomy_granted": ("warning", "An agent was given more autonomy"),
    "settings.proposed": ("info", "A settings change was proposed"),
    "settings.applied": ("warning", "Company settings changed"),
    "external_grant_created": ("warning", "A lender or auditor link was shared"),
    "external_grant_revoked": ("info", "A lender or auditor link was revoked"),
    "privacy_token_erased": ("info", "Personal data was erased on request"),
    "data_export_prepared": ("warning", "A personal data export was prepared"),
    "dpo_assigned": ("info", "The data protection officer was named"),
}


def _aware(moment: dt.datetime) -> dt.datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=dt.UTC)


def describe_agent(agent: str) -> tuple[str, str]:
    browser = next((name for mark, name in _BROWSERS if mark in agent), "Other browser")
    system = next((name for mark, name in _SYSTEMS if mark in agent), "Other system")
    return browser, system


def _network(address: str) -> str:
    if ":" in address:  # IPv6: the first two groups
        return ":".join(address.split(":")[:2])
    return ".".join(address.split(".")[:2]) if re.match(r"^\d+\.\d+\.", address) else address


def _fingerprint(user_id: str, browser: str, system: str, address: str) -> str:
    secret = get_settings().token_root_secret.encode()
    message = f"device:{user_id}:{browser}:{system}:{_network(address)}".encode()
    return hmac.new(secret, message, hashlib.sha256).hexdigest()[:16]


def _previous(db: Session, tenant_id: str, user_id: str) -> list[WorkflowAuditEntry]:
    """This person's earlier sign-ins; read on a worker session, as sign-in has no RLS yet."""
    query = (
        select(WorkflowAuditEntry)
        .where(
            WorkflowAuditEntry.tenant_id == tenant_id,
            WorkflowAuditEntry.event_type == SIGN_IN,
            WorkflowAuditEntry.resource_id == user_id,
        )
        .order_by(WorkflowAuditEntry.id.desc())
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        from app.db import set_worker_context

        with Session(bind=db.get_bind()) as worker:
            set_worker_context(worker, actor_ref="sign-in-history")
            rows = list(worker.scalars(query).all())
            worker.expunge_all()
            return rows
    return list(db.scalars(query).all())


def record_sign_in(db: Session, row, request, *, method: str) -> bool:
    """Keep one completed sign-in; True when it came from a device not seen before."""
    if not (row.tenant_id and row.user_id):
        return False
    browser, system = describe_agent(request.headers.get("user-agent", ""))
    device = _fingerprint(row.user_id, browser, system, rate_limit.client_address(request))
    earlier = _previous(db, row.tenant_id, row.user_id)
    new_device = bool(earlier) and all(e.event_payload.get("device") != device for e in earlier)
    assignment = db.get(AuthUserRole, (row.user_id, row.tenant_id))
    write_workflow_event(
        db,
        event_type=SIGN_IN,
        actor_role=assignment.user_role if assignment else "member",
        actor_ref=f"user:{row.user_id}",
        resource_type="auth_user",
        resource_id=row.user_id,
        event_payload={
            "browser": browser,
            "system": system,
            "device": device,
            "method": method,
            "new_device": new_device,
        },
        tenant_id=row.tenant_id,
    )
    return new_device


def sign_ins(db: Session, tenant_id: str, user_id: str) -> list[SignIn]:
    rows = chain_scalars(
        db,
        select(WorkflowAuditEntry)
        .where(
            WorkflowAuditEntry.tenant_id == tenant_id,
            WorkflowAuditEntry.event_type == SIGN_IN,
            WorkflowAuditEntry.resource_id == user_id,
        )
        .order_by(WorkflowAuditEntry.id.desc())
        .limit(SIGN_INS_SHOWN),
    )
    return [
        SignIn(
            at=_aware(row.created_at),
            browser=row.event_payload["browser"],
            system=row.event_payload["system"],
            method=row.event_payload.get("method", "password"),
            new_device=bool(row.event_payload.get("new_device")),
        )
        for row in rows
    ]


def feed(db: Session, tenant_id: str, now: dt.datetime | None = None) -> list[SecurityEvent]:
    since = (now or dt.datetime.now(dt.UTC)) - dt.timedelta(days=FEED_DAYS)
    rows = chain_scalars(
        db,
        select(WorkflowAuditEntry)
        .where(
            WorkflowAuditEntry.tenant_id == tenant_id,
            WorkflowAuditEntry.event_type.in_([*FEED, SIGN_IN]),
        )
        .order_by(WorkflowAuditEntry.id.desc())
        .limit(500),
    )
    events = []
    for row in rows:
        at = _aware(row.created_at)
        if at < since:
            continue
        if row.event_type == SIGN_IN:
            payload = row.event_payload
            if not payload.get("new_device"):
                continue  # ordinary sign-ins are in each person's own list
            severity = "warning"
            title = f"Sign-in from a new device: {payload['browser']} on {payload['system']}"
        else:
            severity, title = FEED[row.event_type]
        events.append(
            SecurityEvent(
                at=at,
                kind=row.event_type,
                severity=severity,
                title=title,
                actor_role=row.actor_role,
            )
        )
    return events
