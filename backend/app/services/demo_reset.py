"""A clean start each day for the shared demo company, without rewriting history.

Every judge signs in to the same synthetic company. Without a reset, one visitor's
stopped agents, widened autonomy, decided inbox items or changed settings are what
the next visitor finds. A reset:

- switches every stopped agent back on;
- restores the settings the seed left (the first version with a registration date,
  else version 1), as a new version, so the history of changes stays;
- appends a "demo_reset" event to the tenant's workflow chain. Review decisions and
  autonomy grants recorded before it stay on the chain, but no longer count:
  decided items wait for review again and agents return to their default levels.

Only the configured demo tenant can be reset. The API runs it once a day at
RESET_HOUR in the application timezone while the one-click demo is switched on;
`python -m scripts.reset_demo_company` runs it on demand.
"""

import datetime as dt

from sqlalchemy import select, update

from app.config import get_settings
from app.models import (
    AgentSecurityControl,
    TenantSettingsRecord,
    TenantSettingsVersion,
    WorkflowAuditEntry,
)
from app.services.workflow_audit import chain_scalar, write_workflow_event

RESET_HOUR = 3
EVENT = "demo_reset"


class NotDemoTenant(ValueError):
    pass


def reset_mark(db, tenant_id: str) -> int:
    """The chain id of the tenant's latest reset; 0 when it was never reset."""
    return (
        chain_scalar(
            db,
            select(WorkflowAuditEntry.id)
            .where(
                WorkflowAuditEntry.tenant_id == tenant_id,
                WorkflowAuditEntry.event_type == EVENT,
            )
            .order_by(WorkflowAuditEntry.id.desc())
            .limit(1),
        )
        or 0
    )


def _last_reset_day(db, tenant_id: str) -> str | None:
    payload = chain_scalar(
        db,
        select(WorkflowAuditEntry.event_payload)
        .where(WorkflowAuditEntry.tenant_id == tenant_id, WorkflowAuditEntry.event_type == EVENT)
        .order_by(WorkflowAuditEntry.id.desc())
        .limit(1),
    )
    return None if payload is None else payload.get("day")


def _seeded_settings(db, tenant_id: str) -> dict | None:
    versions = db.scalars(
        select(TenantSettingsVersion)
        .where(TenantSettingsVersion.tenant_id == tenant_id)
        .order_by(TenantSettingsVersion.version)
    ).all()
    for version in versions:
        if version.document.get("profile", {}).get("registered_on"):
            return version.document
    return versions[0].document if versions else None


def _restore_settings(db, tenant_id: str) -> bool:
    row = db.get(TenantSettingsRecord, tenant_id)
    seeded = _seeded_settings(db, tenant_id)
    if row is None or seeded is None or row.document == seeded:
        return False
    version = row.version + 1
    db.execute(
        update(TenantSettingsRecord)
        .where(TenantSettingsRecord.tenant_id == tenant_id)
        .values(version=version, document=seeded)
    )
    db.add(TenantSettingsVersion(tenant_id=tenant_id, version=version, document=seeded))
    return True


def reset(db, tenant_id: str, day: dt.date | None = None) -> list[str]:
    """Reset the demo company; return what was restored, as kinds.

    `day` is the local day the reset counts for (today when not given).
    """
    if str(tenant_id) != get_settings().demo_tenant_id:
        raise NotDemoTenant(str(tenant_id))
    tenant_id = str(tenant_id)
    restored = ["review_decisions", "autonomy_grants"]
    stopped = db.execute(
        update(AgentSecurityControl)
        .where(AgentSecurityControl.tenant_id == tenant_id, AgentSecurityControl.engaged.is_(True))
        .values(engaged=False)
    ).rowcount
    if stopped:
        restored.append("agents_restarted")
    if _restore_settings(db, tenant_id):
        restored.append("settings")
    write_workflow_event(
        db,
        event_type=EVENT,
        actor_role="system",
        actor_ref="system:demo_reset",
        resource_type="tenant",
        resource_id=tenant_id,
        event_payload={"restored": restored, "day": (day or dt.date.today()).isoformat()},
        tenant_id=tenant_id,
    )
    db.commit()
    return restored


def run_due(db, now: dt.datetime) -> bool:
    """Reset once a day, at or after RESET_HOUR local time, while the demo is on.

    `now` is local wall-clock time without a timezone, as the scheduler passes it.
    """
    settings = get_settings()
    if not (settings.demo_sign_in_enabled and settings.demo_daily_reset):
        return False
    if now.hour < RESET_HOUR:
        return False
    if _last_reset_day(db, settings.demo_tenant_id) == now.date().isoformat():
        return False
    reset(db, settings.demo_tenant_id, now.date())
    return True
