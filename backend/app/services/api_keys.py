"""Read-only API keys for connecting an AI tool (Claude, ChatGPT) over MCP.

The owner creates a key; it is shown once and only an HMAC of it is kept, on the
company's workflow chain ("api_key_created", "api_key_revoked"). A key reads with
the owner's role but only through the MCP tools, which never change anything and
return figures and masked labels, never contact details or restored names: what
reaches the AI tool is what an AI model inside DuitDuit may see.
"""

import datetime as dt
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.principal import AuthPrincipal
from app.config import get_settings
from app.models import WorkflowAuditEntry
from app.schemas import UserRole
from app.services.workflow_audit import chain_scalars, write_workflow_event

CREATED, REVOKED = "api_key_created", "api_key_revoked"
MAX_KEYS = 5
_KEY = re.compile(r"^ddk_([0-9a-f]{12})_([A-Za-z0-9_-]{32,64})$")


class KeyError_(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class ApiKey:
    id: str
    created_at: dt.datetime
    revoked: bool


def _digest(key: str) -> str:
    secret = get_settings().token_root_secret.encode()
    return hmac.new(secret, f"api-key:{key}".encode(), hashlib.sha256).hexdigest()


def _events(rows) -> dict[str, tuple[WorkflowAuditEntry, bool]]:
    keys: dict[str, tuple[WorkflowAuditEntry, bool]] = {}
    for row in rows:
        if row.event_type == CREATED:
            keys[row.resource_id] = (row, False)
        elif row.resource_id in keys:
            keys[row.resource_id] = (keys[row.resource_id][0], True)
    return keys


def keys(db, tenant_id: str) -> list[ApiKey]:
    rows = chain_scalars(
        db,
        select(WorkflowAuditEntry)
        .where(
            WorkflowAuditEntry.tenant_id == tenant_id,
            WorkflowAuditEntry.event_type.in_((CREATED, REVOKED)),
        )
        .order_by(WorkflowAuditEntry.id),
    )
    return [
        ApiKey(
            id=key_id,
            created_at=row.created_at
            if row.created_at.tzinfo
            else row.created_at.replace(tzinfo=dt.UTC),
            revoked=revoked,
        )
        for key_id, (row, revoked) in _events(rows).items()
    ]


def create(db, principal: AuthPrincipal) -> tuple[ApiKey, str]:
    tenant_id = str(principal.tenant_id)
    if sum(not k.revoked for k in keys(db, tenant_id)) >= MAX_KEYS:
        raise KeyError_("too_many_api_keys", 409)
    key_id = secrets.token_hex(6)
    key = f"ddk_{key_id}_{secrets.token_urlsafe(32)}"
    write_workflow_event(
        db,
        event_type=CREATED,
        actor_role=principal.role.value,
        actor_ref=str(principal.user_id),
        resource_type="api_key",
        resource_id=key_id,
        event_payload={"digest": _digest(key), "scope": "read", "owner": str(principal.user_id)},
        tenant_id=tenant_id,
    )
    db.commit()
    return next(k for k in keys(db, tenant_id) if k.id == key_id), key


def revoke(db, principal: AuthPrincipal, key_id: str) -> None:
    current = {k.id: k for k in keys(db, str(principal.tenant_id))}
    if key_id not in current or current[key_id].revoked:
        raise KeyError_("api_key_not_found", 404)
    write_workflow_event(
        db,
        event_type=REVOKED,
        actor_role=principal.role.value,
        actor_ref=str(principal.user_id),
        resource_type="api_key",
        resource_id=key_id,
        event_payload={},
        tenant_id=str(principal.tenant_id),
    )
    db.commit()


def authenticate(db: Session, key: str) -> tuple[AuthPrincipal, str] | None:
    """The read-only principal a key stands for, and its id; None for any bad key.

    The key names no tenant, so its events are looked up on a worker session.
    """
    match = _KEY.match(key or "")
    if match is None:
        return None
    key_id = match.group(1)
    query = (
        select(WorkflowAuditEntry)
        .where(
            WorkflowAuditEntry.event_type.in_((CREATED, REVOKED)),
            WorkflowAuditEntry.resource_type == "api_key",
            WorkflowAuditEntry.resource_id == key_id,
        )
        .order_by(WorkflowAuditEntry.id)
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        from app.db import set_worker_context

        with Session(bind=db.get_bind()) as worker:
            set_worker_context(worker, actor_ref="api-key-lookup")
            rows = list(worker.scalars(query).all())
            worker.expunge_all()
    else:
        rows = list(db.scalars(query).all())
    found = _events(rows).get(key_id)
    if found is None or found[1]:
        return None
    row, _ = found
    if not hmac.compare_digest(row.event_payload["digest"], _digest(key)):
        return None
    principal = AuthPrincipal(
        user_id=UUID(row.event_payload["owner"]),
        email=None,
        role=UserRole.OWNER_DIRECTOR,
        tenant_id=UUID(str(row.tenant_id)),
        job_functions=("owner",),
        aal="aal1",
    )
    return principal, key_id
