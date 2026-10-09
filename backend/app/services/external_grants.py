"""Expiring, revocable read-only links for lenders and auditors, kept on the audit chain.

A grant is not a table row: it is a "external_grant_created" event on the owner's
tenant workflow chain, closed by a later "external_grant_revoked" event. Its state
is replayed from those events, so creating, revoking and every view are audited by
construction. The grantee's email is kept only as a keyed digest specific to the grant.

The share link carries the grant id and an HMAC over it and the tenant, so a link
cannot be guessed or altered; the server still checks revocation and expiry on
every view. Email one-time codes for lenders are not built: the spec's fallback,
an expiring signed link, is what this provides.
"""

import datetime as dt
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select

from app.auth.principal import AuthPrincipal
from app.config import get_settings
from app.contracts.passports import ExternalGrant, GrantRequest
from app.models import WorkflowAuditEntry
from app.services.workflow_audit import write_workflow_event

GrantKind = Literal["lender", "auditor"]
_SCOPE = {"lender": "passport", "auditor": "audit_pack"}
_VIEW = {"lender": "lender/passports", "auditor": "auditor/packs"}
_TOKEN = re.compile(r"^(grant_[0-9a-f]{16})\.([0-9a-f]{32})$")


class GrantClosed(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class OpenGrant:
    grant: ExternalGrant
    tenant_id: str
    scope_id: str


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _mac(grant_id: str, tenant_id: str) -> str:
    key = get_settings().token_root_secret.encode()
    return hmac.new(key, f"grant|{grant_id}|{tenant_id}".encode(), hashlib.sha256).hexdigest()[:32]


def _grantee_ref(email: str, grant_id: str) -> str:
    # Specific to this grant: not a vault token, so it cannot be resolved by the
    # disclosure path or matched against the same address anywhere else.
    key = get_settings().token_identity_secret.encode()
    message = f"grantee|{grant_id}|{email.strip().casefold()}".encode()
    return "GRANTEE_" + hmac.new(key, message, hashlib.sha256).hexdigest()[:20]


def _share_token(grant_id: str, tenant_id: str) -> str:
    return f"{grant_id}.{_mac(grant_id, tenant_id)}"


def _events(db, *, grant_id: str | None = None, tenant_id: str | None = None):
    query = select(WorkflowAuditEntry).where(WorkflowAuditEntry.resource_type == "external_grant")
    if grant_id is not None:
        query = query.where(WorkflowAuditEntry.resource_id == grant_id)
    if tenant_id is not None:
        query = query.where(WorkflowAuditEntry.tenant_id == tenant_id)
    return db.scalars(query.order_by(WorkflowAuditEntry.id)).all()


def _replay(rows, now: dt.datetime) -> dict[str, tuple[ExternalGrant, str]]:
    grants: dict[str, tuple[ExternalGrant, str]] = {}
    for row in rows:
        payload = row.event_payload
        if row.event_type == "external_grant_created":
            kind = payload["kind"]
            expires_at = dt.datetime.fromisoformat(payload["expires_at"])
            grant = ExternalGrant(
                id=row.resource_id,
                kind=kind,
                scope=payload["scope"],
                grantee_email_token=payload["email_token"],
                expires_at=expires_at,
                allow_exact_values=payload["allow_exact_values"],
                status="active" if expires_at > now else "expired",
                share_path=f"/{_VIEW[kind]}/{_share_token(row.resource_id, row.tenant_id)}",
            )
            grants[row.resource_id] = (grant, row.tenant_id)
        elif row.event_type == "external_grant_revoked" and row.resource_id in grants:
            grant, tenant = grants[row.resource_id]
            grants[row.resource_id] = (grant.model_copy(update={"status": "revoked"}), tenant)
    return grants


def create(
    db, principal: AuthPrincipal, kind: GrantKind, scope_id: str, request: GrantRequest
) -> ExternalGrant:
    tenant_id = str(principal.tenant_id)
    grant_id = "grant_" + secrets.token_hex(8)
    expires_at = (_now() + dt.timedelta(days=request.expires_in_days)).replace(microsecond=0)
    write_workflow_event(
        db,
        event_type="external_grant_created",
        actor_role=principal.role.value,
        actor_ref=str(principal.user_id),
        resource_type="external_grant",
        resource_id=grant_id,
        event_payload={
            "kind": kind,
            "scope": f"{_SCOPE[kind]}:{scope_id}",
            "email_token": _grantee_ref(request.grantee_email, grant_id),
            "expires_at": expires_at.isoformat(),
            "allow_exact_values": request.allow_exact_values,
        },
        tenant_id=tenant_id,
    )
    db.commit()
    return _replay(_events(db, grant_id=grant_id), _now())[grant_id][0]


def list_for(db, tenant_id: str, kind: GrantKind, scope_id: str) -> list[ExternalGrant]:
    scope = f"{_SCOPE[kind]}:{scope_id}"
    grants = _replay(_events(db, tenant_id=tenant_id), _now())
    return [grant for grant, _ in grants.values() if grant.scope == scope]


def revoke(
    db, principal: AuthPrincipal, kind: GrantKind, scope_id: str, grant_id: str
) -> ExternalGrant:
    tenant_id = str(principal.tenant_id)
    found = _replay(_events(db, grant_id=grant_id, tenant_id=tenant_id), _now()).get(grant_id)
    if found is None or found[0].scope != f"{_SCOPE[kind]}:{scope_id}":
        raise LookupError(grant_id)
    if found[0].status != "revoked":
        write_workflow_event(
            db,
            event_type="external_grant_revoked",
            actor_role=principal.role.value,
            actor_ref=str(principal.user_id),
            resource_type="external_grant",
            resource_id=grant_id,
            event_payload={"scope": found[0].scope},
            tenant_id=tenant_id,
        )
        db.commit()
    return _replay(_events(db, grant_id=grant_id, tenant_id=tenant_id), _now())[grant_id][0]


def open_link(db, kind: GrantKind, token: str) -> OpenGrant:
    """Resolve a share token, refuse closed grants and audit the view."""
    match = _TOKEN.match(token)
    if match is None:
        raise LookupError(token)
    grant_id, mac = match.groups()
    found = _replay(_events(db, grant_id=grant_id), _now()).get(grant_id)
    if found is None:
        raise LookupError(token)
    grant, tenant_id = found
    if not hmac.compare_digest(mac, _mac(grant_id, tenant_id)) or grant.kind != kind:
        raise LookupError(token)
    if grant.status == "revoked":
        raise GrantClosed("grant_revoked")
    if grant.expires_at <= _now():
        raise GrantClosed("grant_expired")
    write_workflow_event(
        db,
        event_type="external_grant_viewed",
        actor_role="external",
        actor_ref=f"grant:{grant_id}",
        resource_type="external_grant",
        resource_id=grant_id,
        event_payload={"scope": grant.scope},
        tenant_id=tenant_id,
    )
    db.commit()
    return OpenGrant(grant=grant, tenant_id=tenant_id, scope_id=grant.scope.split(":", 1)[1])
