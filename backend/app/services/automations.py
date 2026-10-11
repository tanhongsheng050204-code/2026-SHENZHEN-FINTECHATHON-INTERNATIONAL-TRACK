"""Automations: "when this happens, prepare that for a person to review".

An automation pairs one trigger with one action:

- invoice_overdue_days N: a receivable is at least N days overdue;
- cash_shortfall_within_days N: the likely balance falls below the minimum within N days;
- bill_due_within_days N: a supplier bill falls due within N days.

- draft_reminder (overdue invoices only): a payment reminder proposal, L2;
- ask_review: an L1 item asking the chosen position to look at it.

Either way the result is a proposal in the review inbox. An automation never sends,
pays or changes a record, and the usual approvals apply. Proposals that are already
open are not repeated (review_inbox.propose).

Automations are stored on the workflow chain ("automation_saved", "automation_removed",
the latest event per automation wins), with kinds and numbers only. The API checks
them every 15 minutes with the alert rules; "Run now" checks them at once.
"""

import datetime as dt
import secrets
from types import SimpleNamespace

from sqlalchemy import select

from app.auth.principal import AuthPrincipal
from app.contracts.collaboration import Automation, AutomationRequest
from app.contracts.common import AutonomyLevel, EvidenceRef, JobFunction
from app.models import WorkflowAuditEntry
from app.services import cashflow, cashflow_engine, collections, review_inbox
from app.services.workflow_audit import write_workflow_event

SAVED, REMOVED = "automation_saved", "automation_removed"
HORIZON_DAYS = 90


class AutomationError(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _ringgit(amount) -> str:
    return f"RM{amount:,.2f}"


def automations(db, tenant_id: str) -> list[Automation]:
    current: dict[str, Automation | None] = {}
    for row in db.scalars(
        select(WorkflowAuditEntry)
        .where(
            WorkflowAuditEntry.tenant_id == tenant_id,
            WorkflowAuditEntry.event_type.in_((SAVED, REMOVED)),
        )
        .order_by(WorkflowAuditEntry.id)
    ):
        key = row.resource_id
        if row.event_type == REMOVED:
            current[key] = None
            continue
        created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=dt.UTC)
        previous = current.get(key)
        current[key] = Automation(
            id=key,
            created_at=previous.created_at if previous else created,
            **row.event_payload,
        )
    return [automation for automation in current.values() if automation is not None]


def save(db, principal: AuthPrincipal, request: AutomationRequest) -> Automation:
    if request.action == "draft_reminder" and request.trigger != "invoice_overdue_days":
        raise AutomationError("reminders_need_an_overdue_trigger", 422)
    automation_id = "auto_" + secrets.token_hex(6)
    write_workflow_event(
        db,
        event_type=SAVED,
        actor_role=principal.role.value,
        actor_ref=str(principal.user_id),
        resource_type="automation",
        resource_id=automation_id,
        event_payload=request.model_dump(mode="json"),
        tenant_id=str(principal.tenant_id),
    )
    db.commit()
    return next(a for a in automations(db, str(principal.tenant_id)) if a.id == automation_id)


def remove(db, principal: AuthPrincipal, automation_id: str) -> None:
    if automation_id not in {a.id for a in automations(db, str(principal.tenant_id))}:
        raise AutomationError("automation_not_found", 404)
    write_workflow_event(
        db,
        event_type=REMOVED,
        actor_role=principal.role.value,
        actor_ref=str(principal.user_id),
        resource_type="automation",
        resource_id=automation_id,
        event_payload={},
        tenant_id=str(principal.tenant_id),
    )
    db.commit()


def _ask(db, tenant_id, automation, agent, title, summary, amount, source) -> str:
    return review_inbox.propose(
        db,
        tenant_id,
        agent_id=agent,
        reviewer=JobFunction(automation.reviewer),
        level=AutonomyLevel.L1,
        title=title,
        summary=summary + " Prepared by an automation; nothing has been sent or paid.",
        amount=amount,
        evidence=[
            EvidenceRef(label="Automation", source=f"automation:{automation.id}"),
            EvidenceRef(label="Source record", source=source),
        ],
    )


def _run_one(db, tenant_id: str, automation: Automation, as_of: dt.date) -> list[str]:
    actor = SimpleNamespace(tenant_id=tenant_id)
    created = []
    if automation.trigger == "invoice_overdue_days":
        board = collections.board(db, actor, as_of)
        for column in board.columns:
            if column.stage != "overdue":
                continue
            for card in column.cards:
                if card.days_overdue < automation.days:
                    continue
                if automation.action == "draft_reminder":
                    created.append(collections.propose_reminder(db, actor, card.ref, as_of))
                else:
                    created.append(
                        _ask(
                            db,
                            tenant_id,
                            automation,
                            "receivables",
                            f"{card.label} is {card.days_overdue} days overdue",
                            f"{_ringgit(card.amount)} from {card.customer_label} is past due.",
                            card.amount,
                            card.ref,
                        )
                    )
        return created
    basis = cashflow.basis_for(db, actor, as_of)
    forecast = cashflow_engine.build_forecast(basis, horizon_days=HORIZON_DAYS, as_of=as_of)
    if automation.trigger == "cash_shortfall_within_days":
        shortfall = forecast.shortfall
        if shortfall is not None and shortfall.day <= automation.days:
            created.append(
                _ask(
                    db,
                    tenant_id,
                    automation,
                    "cashflow",
                    f"Cash falls below your minimum in {shortfall.day} days",
                    f"Likely balance {_ringgit(shortfall.likely_balance)} on day {shortfall.day}, "
                    f"{_ringgit(shortfall.gap)} under the minimum.",
                    shortfall.gap,
                    "cashflow:forecast",
                )
            )
        return created
    for driver in forecast.drivers:
        day = driver.likely_day
        if driver.source_agent == "payables" and driver.kind == "outflow" and day is not None:
            if day <= automation.days:
                created.append(
                    _ask(
                        db,
                        tenant_id,
                        automation,
                        "payables",
                        f"Supplier bill due in {day} days: {driver.label}",
                        f"{_ringgit(driver.amount_myr)} falls due on day {day}.",
                        driver.amount_myr,
                        f"cash-signal:{driver.id}",
                    )
                )
    return created


def run(db, tenant_id: str, as_of: dt.date) -> list[str]:
    created: list[str] = []
    for automation in automations(db, tenant_id):
        if automation.enabled:
            created.extend(_run_one(db, tenant_id, automation, as_of))
    return list(dict.fromkeys(created))


def run_due(db, now_local: dt.datetime) -> int:
    """Every tenant with an automation; called with the 15-minute alert checks."""
    tenants = db.scalars(
        select(WorkflowAuditEntry.tenant_id)
        .where(WorkflowAuditEntry.event_type == SAVED)
        .distinct()
    ).all()
    total = 0
    for tenant_id in tenants:
        if tenant_id is not None:
            total += len(run(db, str(tenant_id), now_local.date()))
    return total
