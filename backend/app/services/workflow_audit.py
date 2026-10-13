import hashlib
import json
from datetime import UTC, datetime

from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from app.models import WorkflowAuditEntry, utcnow


def _payload(
    *,
    event_type: str,
    actor_role: str,
    actor_ref: str,
    resource_type: str,
    resource_id: str,
    event_payload: dict,
    created_at: datetime,
) -> dict:
    timestamp = (
        created_at.replace(tzinfo=UTC) if created_at.tzinfo is None else created_at.astimezone(UTC)
    )
    return {
        "actor_ref": actor_ref,
        "actor_role": actor_role,
        "created_at": timestamp.isoformat(timespec="microseconds"),
        "event_payload": event_payload,
        "event_type": event_type,
        "resource_id": resource_id,
        "resource_type": resource_type,
    }


def _hash(previous_hash: str, payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(f"{canonical}{previous_hash}".encode()).hexdigest()


def write_workflow_event(
    db: Session,
    *,
    event_type: str,
    actor_role: str,
    actor_ref: str,
    resource_type: str,
    resource_id: str,
    event_payload: dict,
    tenant_id: str | None = None,
) -> WorkflowAuditEntry:
    """Append to a hash chain scoped to `tenant_id`. Pass tenant_id=None only for
    genuinely system-level events (e.g. vault key rotation) that aren't owned by any
    one tenant — everything tenant-owned (recommendations, einvoice, etc.) must pass
    its real tenant_id so its chain is verifiable independently of other tenants'."""
    if _unreadable_by_writer(db, actor_ref):
        # Row-level security returns an inserted row to its writer, and only the owner,
        # Compliance and the entry's own actor may read it. Entries written for an
        # agent, or under a person's user id, by anyone else are appended on a worker
        # session for the same tenant and committed there.
        # If this transaction already holds the chain's lock (it appended an entry
        # earlier), the worker session would wait for it forever: commit first.
        # Otherwise stay in one transaction, so locks such as the inbox's still hold.
        if db.info.get(_CHAIN_LOCKED):
            db.commit()
        trusted = _trusted_session(db)
        with trusted:
            row = write_workflow_event(
                trusted,
                event_type=event_type,
                actor_role=actor_role,
                actor_ref=actor_ref,
                resource_type=resource_type,
                resource_id=resource_id,
                event_payload=event_payload,
                tenant_id=tenant_id,
            )
            trusted.commit()
            trusted.expunge(row)
        return row
    lock_key = f"finbrain:workflow-audit:{tenant_id or 'system'}"
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("select pg_advisory_xact_lock(hashtext(:key))"), {"key": lock_key})
        db.info[_CHAIN_LOCKED] = True
        previous_hash = db.scalar(
            text("select public.finbrain_audit_tail('workflow', cast(:tenant_id as uuid))"),
            {"tenant_id": tenant_id},
        )
    else:
        last = db.scalar(
            select(WorkflowAuditEntry)
            .where(WorkflowAuditEntry.tenant_id == tenant_id)
            .order_by(WorkflowAuditEntry.id.desc())
            .limit(1)
        )
        previous_hash = last.event_hash if last else "genesis"
    timestamp = utcnow()
    payload = _payload(
        event_type=event_type,
        actor_role=actor_role,
        actor_ref=actor_ref,
        resource_type=resource_type,
        resource_id=resource_id,
        event_payload=event_payload,
        created_at=timestamp,
    )
    row = WorkflowAuditEntry(
        tenant_id=tenant_id,
        prev_hash=previous_hash,
        event_hash=_hash(previous_hash, payload),
        event_type=event_type,
        actor_role=actor_role,
        actor_ref=actor_ref,
        resource_type=resource_type,
        resource_id=resource_id,
        event_payload=event_payload,
        created_at=timestamp,
    )
    db.add(row)
    db.flush()
    return row


def verify_workflow_chain(db: Session, tenant_id: str | None = None) -> bool:
    """Verify one chain: the given tenant's, or the system chain when tenant_id=None."""
    previous_hash = "genesis"
    rows = db.scalars(
        select(WorkflowAuditEntry)
        .where(WorkflowAuditEntry.tenant_id == tenant_id)
        .order_by(WorkflowAuditEntry.id)
    ).all()
    for row in rows:
        payload = _payload(
            event_type=row.event_type,
            actor_role=row.actor_role,
            actor_ref=row.actor_ref,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            event_payload=row.event_payload,
            created_at=row.created_at,
        )
        if row.prev_hash != previous_hash or row.event_hash != _hash(previous_hash, payload):
            return False
        previous_hash = row.event_hash
    return True


# ── Reading a tenant's chain for the people who work in it ─────────────────
#
# Row-level security lets the application role read only the chain entries a
# person wrote, unless they are the owner or Compliance. The review inbox,
# comments, autonomy grants, automations, saved views and the demo reset are all
# replayed from entries other people (or agents) wrote, so those reads run on a
# separate session in the worker role, scoped to the same tenant. Every caller
# filters by tenant and decides in code what this person may see, as the inbox
# always has. Writes stay on the person's own session.


_CHAIN_LOCKED = "finbrain_chain_locked"


@event.listens_for(Session, "after_commit")
@event.listens_for(Session, "after_rollback")
def _chain_lock_released(session: Session) -> None:
    session.info.pop(_CHAIN_LOCKED, None)


def _unreadable_by_writer(db: Session, actor_ref: str) -> bool:
    context = db.info.get("finbrain_rls_context") or {}
    return (
        db.bind is not None
        and db.bind.dialect.name == "postgresql"
        and context.get("database_role") == "finbrain_app"
        and context.get("user_role") not in ("owner_director", "compliance")
        and actor_ref != context.get("actor_ref")
    )


def _trusted_session(db: Session) -> Session | None:
    context = db.info.get("finbrain_rls_context") or {}
    if (
        db.bind is None
        or db.bind.dialect.name != "postgresql"
        or context.get("database_role") != "finbrain_app"
    ):
        return None
    from app.db import set_worker_context, trusted_bind

    # The same database as the person's session, from its own pool; one transaction.
    session = Session(bind=trusted_bind(db), expire_on_commit=False)
    set_worker_context(session, actor_ref="chain-reader", tenant_id=context.get("tenant_id"))
    return session


def chain_scalars(db: Session, statement) -> list:
    """db.scalars(statement).all() for chain reads, visible to every role."""
    trusted = _trusted_session(db)
    if trusted is None:
        return list(db.scalars(statement).all())
    # The worker role may read every tenant's chain; this read is held to the
    # person's own tenant here, whatever the caller's statement says.
    tenant_id = (db.info.get("finbrain_rls_context") or {}).get("tenant_id")
    if not tenant_id:
        trusted.close()
        return []
    with trusted:
        rows = list(
            trusted.scalars(statement.where(WorkflowAuditEntry.tenant_id == tenant_id)).all()
        )
        trusted.expunge_all()
        return rows


def chain_scalar(db: Session, statement):
    """db.scalar(statement) for chain reads, visible to every role."""
    rows = chain_scalars(db, statement.limit(1) if hasattr(statement, "limit") else statement)
    return rows[0] if rows else None
