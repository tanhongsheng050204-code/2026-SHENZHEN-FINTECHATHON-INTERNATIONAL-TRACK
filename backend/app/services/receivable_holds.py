"""Holds on chasing: a disputed invoice, a promise to pay, or a paused customer.

A hold stops reminders and automations for what it covers. It never hides the
debt: the invoice keeps its due date and days overdue, in an "On hold" column of
the collections board. A promise to pay lasts until its date; if the invoice is
still unpaid after that, chasing resumes and the card says the promise was broken.

Holds live on the workflow chain ("receivable_hold_set", "receivable_hold_cleared",
the latest event per target wins), with the kind and the date only.
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import select

from app.auth.principal import AuthPrincipal
from app.contracts.collaboration import HoldRequest
from app.models import WorkflowAuditEntry
from app.services.workflow_audit import chain_scalars, write_workflow_event

SET, CLEARED = "receivable_hold_set", "receivable_hold_cleared"
MAX_PROMISE_DAYS = 90


class HoldError(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class StoredHold:
    target: str
    kind: str
    until: dt.date | None
    set_at: dt.datetime
    set_by_role: str


def stored(db, tenant_id: str) -> dict[str, StoredHold]:
    """Every target's latest hold, expired promises included."""
    current: dict[str, StoredHold | None] = {}
    for row in chain_scalars(
        db,
        select(WorkflowAuditEntry)
        .where(
            WorkflowAuditEntry.tenant_id == tenant_id,
            WorkflowAuditEntry.event_type.in_((SET, CLEARED)),
        )
        .order_by(WorkflowAuditEntry.id),
    ):
        if row.event_type == CLEARED:
            current[row.resource_id] = None
            continue
        until = row.event_payload.get("until")
        current[row.resource_id] = StoredHold(
            target=row.resource_id,
            kind=row.event_payload["kind"],
            until=dt.date.fromisoformat(until) if until else None,
            set_at=row.created_at
            if row.created_at.tzinfo
            else row.created_at.replace(tzinfo=dt.UTC),
            set_by_role=row.actor_role,
        )
    return {target: hold for target, hold in current.items() if hold is not None}


def active(hold: StoredHold, as_of: dt.date) -> bool:
    return hold.kind != "promised" or (hold.until is not None and hold.until >= as_of)


def check(target: str, request: HoldRequest, as_of: dt.date) -> None:
    customer = target.startswith("customer:")
    if customer != (request.kind == "paused"):
        raise HoldError("hold_kind_does_not_fit", 422)
    if request.kind == "promised":
        if request.until is None:
            raise HoldError("promise_needs_a_date", 422)
        if not as_of <= request.until <= as_of + dt.timedelta(days=MAX_PROMISE_DAYS):
            raise HoldError("promise_date_out_of_range", 422)
    elif request.until is not None:
        raise HoldError("only_a_promise_has_a_date", 422)


def put(db, principal: AuthPrincipal, target: str, request: HoldRequest) -> None:
    write_workflow_event(
        db,
        event_type=SET,
        actor_role=principal.role.value,
        actor_ref=str(principal.user_id),
        resource_type="receivable_hold",
        resource_id=target,
        event_payload={
            "kind": request.kind,
            "until": request.until.isoformat() if request.until else None,
        },
        tenant_id=str(principal.tenant_id),
    )
    db.commit()


def clear(db, principal: AuthPrincipal, target: str) -> None:
    if target not in stored(db, str(principal.tenant_id)):
        raise HoldError("hold_not_found", 404)
    write_workflow_event(
        db,
        event_type=CLEARED,
        actor_role=principal.role.value,
        actor_ref=str(principal.user_id),
        resource_type="receivable_hold",
        resource_id=target,
        event_payload={},
        tenant_id=str(principal.tenant_id),
    )
    db.commit()
