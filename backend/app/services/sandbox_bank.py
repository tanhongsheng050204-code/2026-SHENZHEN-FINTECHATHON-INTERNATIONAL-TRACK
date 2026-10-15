"""DuitDuit's simulated bank: where an approved L3 payment actually executes.

No real bank is connected. When a money item has its maker's approval and then a
different checker's (with a fresh authenticator code, as the decision route
requires), the payment executes once on this sandbox ledger and gets a reference.
Nothing else can move money here: an agent, a rejected item, a half-approved one or
an L1/L2 item never does. Each execution is an event on the company's workflow
audit chain carrying ids and the amount only, never titles or names.
"""

import datetime as dt
import hashlib
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select

from app.contracts.common import AutonomyLevel
from app.models import WorkflowAuditEntry
from app.services.workflow_audit import chain_scalars, write_workflow_event

EVENT = "sandbox_payment_executed"
LEDGER = "duitduit-simulated-bank"


@dataclass(frozen=True)
class Payment:
    action_id: str
    amount: Decimal
    reference: str
    executed_at: dt.datetime


def _reference(tenant_id: str, action_id: str) -> str:
    digest = hashlib.sha256(f"{tenant_id}:{action_id}".encode()).hexdigest()
    return f"SIM-{digest[:10].upper()}"


def payments(db, tenant_id: str) -> list[Payment]:
    """Payments executed since the demo company's latest reset (all, elsewhere)."""
    from app.services.demo_reset import reset_mark

    mark = reset_mark(db, tenant_id)
    rows = chain_scalars(
        db,
        select(WorkflowAuditEntry)
        .where(
            WorkflowAuditEntry.tenant_id == tenant_id,
            WorkflowAuditEntry.event_type == EVENT,
            WorkflowAuditEntry.id > mark,
        )
        .order_by(WorkflowAuditEntry.id),
    )
    return [
        Payment(
            action_id=row.event_payload["action_id"],
            amount=Decimal(row.event_payload["amount"]),
            reference=row.event_payload["reference"],
            executed_at=row.created_at
            if row.created_at.tzinfo
            else row.created_at.replace(tzinfo=dt.UTC),
        )
        for row in rows
    ]


def references(db, tenant_id: str) -> dict[str, str]:
    return {p.action_id: p.reference for p in payments(db, tenant_id)}


def execute_if_due(db, tenant_id: str, action_id: str) -> str | None:
    """Execute a fully approved L3 payment once; its reference, or None if not due."""
    from app.services import review_inbox

    item = review_inbox._replay(db, tenant_id).get(action_id)
    if item is None:
        return None
    action = item.action
    approvers = {a.approver_id for a in action.approvals}
    if (
        action.autonomy_level != AutonomyLevel.L3
        or action.status != "approved"
        or len(approvers) < 2
        or action.amount is None
    ):
        return None
    done = references(db, tenant_id).get(action_id)
    if done:
        return done
    reference = _reference(tenant_id, action_id)
    write_workflow_event(
        db,
        event_type=EVENT,
        actor_role="system",
        actor_ref="system:sandbox_bank",
        resource_type="sandbox_payment",
        resource_id=action_id,
        event_payload={
            "action_id": action_id,
            "amount": str(action.amount),
            "reference": reference,
            "ledger": LEDGER,
        },
        tenant_id=tenant_id,
    )
    db.commit()
    return reference
