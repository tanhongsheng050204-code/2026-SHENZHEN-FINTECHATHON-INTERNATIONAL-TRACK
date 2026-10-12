"""Automations: "when this happens, prepare that for a person to review".

An automation pairs one trigger with one action:

- invoice_overdue_days N: a receivable is at least N days overdue;
- invoice_due_within_days N: a receivable falls due within N days (a courtesy note);
- cash_shortfall_within_days N: the likely balance falls below the minimum within N days;
- bill_due_within_days N: a supplier bill falls due within N days.

- draft_reminder (invoice triggers only): one reminder proposal per invoice, L2;
- reminder_sequence (overdue only): friendly, then firm, then a call, each after the
  last was approved; a rejected step stops the sequence for that invoice;
- ask_review: an L1 item asking the chosen position to look at it.

Invoices on hold (disputed, promised, customer paused) are skipped. Each run that
proposes something, or skips for a new reason, is kept as "automation_ran" with
action ids and skip counts, so the run history says what happened and why. The
scheduler only runs on working days (Monday to Friday); "Run now" runs any day.

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
from app.contracts.collaboration import Automation, AutomationRequest, AutomationRun
from app.contracts.common import AutonomyLevel, EvidenceRef, JobFunction
from app.models import WorkflowAuditEntry
from app.services import cashflow, cashflow_engine, collections, review_inbox
from app.services.workflow_audit import chain_scalars, write_workflow_event

SAVED, REMOVED, RAN = "automation_saved", "automation_removed", "automation_ran"
_INVOICE_TRIGGERS = ("invoice_overdue_days", "invoice_due_within_days")
RUNS_SHOWN = 20
# A collections sequence: (days after the automation's N, title, kind). Each step is
# proposed once per invoice, only after the previous one was decided.
SEQUENCE = (
    (0, "Friendly reminder for {label}", "reminder"),
    (7, "Firm reminder for {label}", "reminder"),
    (21, "Call the customer about {label}", "call"),
)
_DRAFTS = {
    "Friendly": "A gentle reminder that the invoice on your account is now due. Could you "
    "confirm when payment will be made? If it is already on its way, thank you.",
    "Firm": "Our records show the invoice on your account is still unpaid and now well past "
    "due. Please arrange payment this week or let us know of any issue with it.",
}
_COURTESY = (
    "A courtesy note that the invoice on your account falls due on {due:%d %b %Y}. "
    "If payment is already scheduled, thank you, and please ignore this message."
)
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
    for row in chain_scalars(
        db,
        select(WorkflowAuditEntry)
        .where(
            WorkflowAuditEntry.tenant_id == tenant_id,
            WorkflowAuditEntry.event_type.in_((SAVED, REMOVED)),
        )
        .order_by(WorkflowAuditEntry.id),
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
    if request.action == "reminder_sequence" and request.trigger != "invoice_overdue_days":
        raise AutomationError("reminders_need_an_overdue_trigger", 422)
    if request.action == "draft_reminder" and request.trigger not in _INVOICE_TRIGGERS:
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


def _cited(db, tenant_id: str, ref: str) -> list:
    """Every review item, in order, that cites this receivable."""
    return [
        item.action
        for item in review_inbox._replay(db, tenant_id).values()
        if any(evidence.source == ref for evidence in item.action.evidence)
    ]


def _sequence_step(
    db, tenant_id: str, automation: Automation, card
) -> tuple[str | None, str | None]:
    """Propose the next step for one overdue invoice: (proposal, why nothing was proposed)."""
    cited = _cited(db, tenant_id, card.ref)
    for index, (offset, title, kind) in enumerate(SEQUENCE):
        name = title.format(label=card.label)
        earlier = [action for action in cited if action.title == name]
        if earlier:
            status = earlier[-1].status
            if status == "rejected":
                return None, "stopped_after_rejection"  # a person said not to chase
            if status != "approved":
                return None, "waiting_for_decision"
            continue
        threshold = automation.days + offset
        if card.days_overdue < threshold:
            return None, None
        why = f" Why this step: {card.label} reached {threshold} days overdue" + (
            f" and step {index} was approved." if index else "."
        )
        evidence = [
            EvidenceRef(label="Automation", source=f"automation:{automation.id}"),
            EvidenceRef(label="Receivable record", source=card.ref),
        ]
        if kind == "call":
            return review_inbox.propose(
                db,
                tenant_id,
                agent_id="receivables",
                reviewer=JobFunction.FINANCE,
                level=AutonomyLevel.L1,
                title=name,
                summary=f"{card.label} is {card.days_overdue} days overdue after two reminders. "
                "Phone the customer and note what they say. Nothing is sent by DuitDuit." + why,
                amount=card.amount,
                evidence=evidence,
            ), None
        return review_inbox.propose(
            db,
            tenant_id,
            agent_id="receivables",
            reviewer=JobFunction.FINANCE,
            level=AutonomyLevel.L2,
            title=name,
            summary=f"Step {index + 1} of 3 for {card.label}, "
            f"{card.days_overdue} days overdue. Verify the recipient, balance and timing "
            "before sending. Nothing has been sent." + why,
            amount=card.amount,
            draft=_DRAFTS[title.split()[0]],
            evidence=evidence,
        ), None
    return None, None


def _courtesy(db, tenant_id: str, automation: Automation, card) -> str | None:
    """One courtesy note per invoice, a few days before it falls due."""
    name = f"Courtesy reminder for {card.label}"
    if any(action.title == name for action in _cited(db, tenant_id, card.ref)):
        return None
    return review_inbox.propose(
        db,
        tenant_id,
        agent_id="receivables",
        reviewer=JobFunction.FINANCE,
        level=AutonomyLevel.L2,
        title=name,
        summary=f"{card.label} from {card.customer_label} falls due on {card.due_date:%d %b}. "
        "A courtesy note before the due date. Verify the recipient and balance before "
        f"sending. Nothing has been sent. Why this step: it is due within {automation.days} days.",
        amount=card.amount,
        draft=_COURTESY.format(due=card.due_date),
        evidence=[
            EvidenceRef(label="Automation", source=f"automation:{automation.id}"),
            EvidenceRef(label="Receivable record", source=card.ref),
        ],
    )


def _invoices(db, tenant_id, automation, as_of, skipped) -> list[str]:
    actor = SimpleNamespace(tenant_id=tenant_id)
    created = []
    board = collections.board(db, actor, as_of)
    courtesy = automation.trigger == "invoice_due_within_days"
    for column in board.columns:
        for card in column.cards:
            if courtesy:
                due_in = (card.due_date - as_of).days if card.due_date else None
                reached = (
                    column.stage != "paid" and due_in is not None and 0 <= due_in <= automation.days
                )
            else:
                late = card.due_date is not None and card.due_date < as_of
                reached = late and column.stage != "paid" and card.days_overdue >= automation.days
            if not reached:
                continue
            if column.stage == "reminder":
                if automation.action != "ask_review":
                    skipped["waiting_for_decision"] = skipped.get("waiting_for_decision", 0) + 1
                continue
            if column.stage == "on_hold":
                skipped["on_hold"] = skipped.get("on_hold", 0) + 1
                continue
            if courtesy and automation.action == "draft_reminder":
                created.append(_courtesy(db, tenant_id, automation, card))
            elif automation.action == "draft_reminder":
                if any(
                    a.agent_id == "receivables" and a.title == f"Payment reminder for {card.label}"
                    for a in _cited(db, tenant_id, card.ref)
                ):
                    continue  # one reminder per invoice; the sequence does the follow-ups
                created.append(collections.propose_reminder(db, actor, card.ref, as_of))
            elif automation.action == "reminder_sequence":
                step, reason = _sequence_step(db, tenant_id, automation, card)
                if step is not None:
                    created.append(step)
                elif reason is not None:
                    skipped[reason] = skipped.get(reason, 0) + 1
            else:
                when = (
                    f"falls due on {card.due_date:%d %b}"
                    if courtesy
                    else f"is {card.days_overdue} days overdue"
                )
                created.append(
                    _ask(
                        db,
                        tenant_id,
                        automation,
                        "receivables",
                        f"{card.label} {when}",
                        f"{_ringgit(card.amount)} from {card.customer_label}.",
                        card.amount,
                        card.ref,
                    )
                )
    return [c for c in created if c is not None]


def _run_one(db, tenant_id: str, automation: Automation, as_of: dt.date, skipped) -> list[str]:
    actor = SimpleNamespace(tenant_id=tenant_id)
    created = []
    if automation.trigger in _INVOICE_TRIGGERS:
        return _invoices(db, tenant_id, automation, as_of, skipped)
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


def _runs(db, tenant_id: str, automation_id: str) -> list:
    return list(
        chain_scalars(
            db,
            select(WorkflowAuditEntry)
            .where(
                WorkflowAuditEntry.tenant_id == tenant_id,
                WorkflowAuditEntry.event_type == RAN,
                WorkflowAuditEntry.resource_id == automation_id,
            )
            .order_by(WorkflowAuditEntry.id.desc())
            .limit(RUNS_SHOWN),
        )
    )


def _record(db, tenant_id: str, automation_id: str, proposed: list[str], skipped: dict) -> None:
    """Keep a run that proposed something or skipped for a new reason; not the same twice."""
    last = _runs(db, tenant_id, automation_id)
    previous = last[0].event_payload.get("skipped", {}) if last else {}
    if not proposed and skipped == previous:
        return
    write_workflow_event(
        db,
        event_type=RAN,
        actor_role="automation",
        actor_ref=f"automation:{automation_id}",
        resource_type="automation",
        resource_id=automation_id,
        event_payload={"proposed": proposed, "skipped": skipped},
        tenant_id=tenant_id,
    )
    db.commit()


def runs(db, tenant_id: str, automation_id: str) -> list[AutomationRun]:
    if automation_id not in {a.id for a in automations(db, tenant_id)}:
        raise AutomationError("automation_not_found", 404)
    return [
        AutomationRun(
            at=row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=dt.UTC),
            proposed=row.event_payload["proposed"],
            skipped=row.event_payload["skipped"],
        )
        for row in _runs(db, tenant_id, automation_id)
    ]


def run(db, tenant_id: str, as_of: dt.date) -> list[str]:
    created: list[str] = []
    for automation in automations(db, tenant_id):
        if automation.enabled:
            skipped: dict[str, int] = {}
            proposed = list(dict.fromkeys(_run_one(db, tenant_id, automation, as_of, skipped)))
            _record(db, tenant_id, automation.id, proposed, skipped)
            created.extend(proposed)
    return list(dict.fromkeys(created))


def run_due(db, now_local: dt.datetime) -> int:
    """Every tenant with an automation; called with the 15-minute alert checks.

    Proposals wait for a working day, so nobody comes back to a weekend's worth.
    """
    if now_local.weekday() >= 5:
        return 0
    tenants = chain_scalars(
        db,
        select(WorkflowAuditEntry.tenant_id)
        .where(WorkflowAuditEntry.event_type == SAVED)
        .distinct(),
    )
    total = 0
    for tenant_id in tenants:
        if tenant_id is not None:
            total += len(run(db, str(tenant_id), now_local.date()))
    return total
