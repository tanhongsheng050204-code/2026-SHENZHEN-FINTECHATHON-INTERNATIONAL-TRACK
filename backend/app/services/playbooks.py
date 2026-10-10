"""Repeatable, tenant-scoped playbooks. External work stays in the review inbox.

No provider, sender, grant issuer or payment executor is called here. Forecasts
and scenarios are read-only; drafts are generic and identify records by id so
personal data and the person's words never enter the workflow audit chain.
"""

import datetime as dt
import re
import secrets
from collections import defaultdict
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select

from app.auth.principal import AuthPrincipal
from app.contracts.assistant import PlaybookId, PlaybookResult, PlaybookStep
from app.contracts.cashflow import EventShift
from app.contracts.common import AutonomyLevel, DataMode, EvidenceRef, JobFunction
from app.models import (
    BusinessImportBatch,
    Customer,
    EInvoiceRecord,
    SalesPipeline,
    SyntheticTenantSeed,
)
from app.schemas import UserRole
from app.services import (
    agent_runtime,
    bank_matching,
    cashflow,
    cashflow_engine,
    einvoice_readiness,
    financing_profile,
    overdue_reminders,
    review_inbox,
)
from app.services.workflow_audit import write_workflow_event
from app.stubs.financing import _METRICS

TITLES: dict[PlaybookId, str] = {
    "bank_meeting": "Bank meeting pack",
    "chase_late_payers": "Late payer reminders",
    "pay_everyone": "Pay everyone",
    "month_end": "Month-end checklist",
}
_WORK = (UserRole.OWNER_DIRECTOR, UserRole.FINANCE_OPS)
_READ = (*_WORK, UserRole.COMPLIANCE)
_ROLES = {
    "bank_meeting": _WORK,
    "chase_late_payers": _WORK,
    "pay_everyone": _READ,
    "month_end": _READ,
}
_PHRASES = {
    "bank_meeting": r"\b(prepare (me |us )?for (the |a )?bank meeting|bank pack|loan meeting)\b",
    "chase_late_payers": r"\b(chase (the )?late payers|chase (the )?overdue|who owes us)\b",
    "pay_everyone": r"\b(can (i|we) pay everyone this month|can (i|we) make payroll)\b",
    "month_end": r"\b(close the month|month[ -]end( checklist)?)\b",
}
_ZERO = Decimal("0.00")
_BEFORE_GAP = "invoices due before the cash gap"


def match(text: str) -> PlaybookId | None:
    return next((key for key, pattern in _PHRASES.items() if re.search(pattern, text, re.I)), None)


def allowed(principal: AuthPrincipal, playbook_id: str) -> bool:
    return principal.role in _ROLES.get(playbook_id, ())


def _step(label, status, text) -> PlaybookStep:
    return PlaybookStep(label=label, status=status, text=text)


def _money(amount: Decimal) -> str:
    return f"RM{amount:,.2f}"


def _forecast(db, principal, *, horizon=90):
    today = dt.date.today()
    basis = cashflow.basis_for(db, principal, today)
    return basis, cashflow_engine.build_forecast(basis, horizon_days=horizon, as_of=today)


def _cash_step(forecast):
    shortfall = forecast.shortfall
    if shortfall:
        return _step(
            "Cash forecast",
            "attention",
            f"Day {shortfall.day} ({shortfall.date:%d %b %Y}): likely balance "
            f"{_money(shortfall.likely_balance)}, a gap of {_money(shortfall.gap)} "
            f"against the {_money(shortfall.minimum_balance)} minimum.",
        )
    return _step(
        "Cash forecast", "done", f"Cash stays above the minimum for {forecast.horizon_days} days."
    )


def _bank_meeting(db, principal):
    _, forecast = _forecast(db, principal)
    profile = financing_profile.compute(db, str(principal.tenant_id), forecast)
    missing = [_METRICS[key][0] for key in _METRICS if key not in profile.values]
    item_id = review_inbox.propose(
        db,
        str(principal.tenant_id),
        agent_id="financing",
        reviewer=JobFunction.FINANCE,
        level=AutonomyLevel.L2,
        title="Bank meeting: review lender sharing",
        summary="Review a lender Passport share link. No link has been issued or shared.",
        draft="After reviewing this proposal, the owner selects a Passport, lender and expiry "
        "on Financing & Passport and confirms with an authenticator code. Nothing is sent here.",
        evidence=[EvidenceRef(label="Passport sharing controls", source="passports:lender-grants")],
    )
    facts = []
    for key, (label, unit, _) in _METRICS.items():
        value = profile.values.get(key)
        if value is not None:
            rendered = (
                _money(value)
                if unit == "money"
                else (f"{value * 100:.0f}%" if unit == "share" else str(value))
            )
            facts.append(f"{label}: {rendered}")
    return (
        [
            _cash_step(forecast),
            _step("Financing profile", "done", "; ".join(facts)),
            _step(
                "Missing facts",
                "attention" if missing else "done",
                "Not on record: " + "; ".join(missing)
                if missing
                else "All financing-rule facts are available in this profile. "
                "This is not a credit decision.",
            ),
            _step(
                "Lender sharing",
                "attention",
                "An L2 proposal awaits the owner's review. "
                "No share link has been created. "
                "Issue and share a Passport from Financing & Passport.",
            ),
        ],
        [item_id],
        "financing",
        forecast.data_mode,
    )


def _reminder_groups(db, principal, forecast):
    tenant_id = str(principal.tenant_id)
    groups: dict[str, list[str]] = defaultdict(list)
    # Share the worker's read-only selection, never its possibly auto-approved queue.
    invoices = overdue_reminders.due_invoices(db, tenant_id, forecast.as_of)
    for invoice in invoices:
        customer = db.scalar(
            select(Customer).where(
                Customer.tenant_id == tenant_id,
                Customer.id == invoice.buyer_customer_id,
            )
        )
        if customer is not None:
            groups[f"customer:{customer.id}"].append(f"einvoice:{invoice.id}")
    if invoices:
        return groups, "overdue invoices"
    late = agent_runtime._late_receivables(forecast)
    if forecast.data_mode == DataMode.STUB:
        # Fixture identities only, never infer a live customer's identity from a label.
        fixture_customers = {
            "R1": "A",
            "R2": "B",
            "R3": "C",
            "R4": "A",
            "R5": "D",
            "R6": "B",
            "R7": "E",
            "R8": "C",
            "R9": "A",
            "R10": "F",
        }
        for signal in late:
            customer = fixture_customers.get(signal.id)
            if customer:
                groups[f"synthetic-customer:{customer}"].append(f"cash-signal:{signal.id}")
    else:
        rows = db.scalars(
            select(SalesPipeline).where(
                SalesPipeline.tenant_id == tenant_id,
                SalesPipeline.stage == "invoiced",
                SalesPipeline.expected_payment_date < forecast.as_of,
            )
        ).all()
        for row in rows:
            groups[f"customer:{row.customer_id}"].append(f"pipeline:{row.id}")
        if not rows and forecast.shortfall:
            # Nobody is late yet. The invoices that land before the gap are the ones
            # worth a polite request to confirm payment dates.
            due = db.scalars(
                select(SalesPipeline).where(
                    SalesPipeline.tenant_id == tenant_id,
                    SalesPipeline.stage == "invoiced",
                    SalesPipeline.expected_payment_date >= forecast.as_of,
                    SalesPipeline.expected_payment_date <= forecast.shortfall.date,
                )
            ).all()
            for row in due:
                groups[f"customer:{row.customer_id}"].append(f"pipeline:{row.id}")
            return groups, _BEFORE_GAP
    return (
        groups,
        "late-payment risks" if forecast.data_mode == DataMode.STUB else "overdue pipeline",
    )


def _customer_label(ref: str) -> str:
    """Ids only (titles live on the audit chain); the inbox links to the record."""
    kind, _, key = ref.partition(":")
    return f"synthetic customer {key}" if kind == "synthetic-customer" else f"customer #{key}"


def _chase_late_payers(db, principal):
    _, forecast = _forecast(db, principal)
    groups, source = _reminder_groups(db, principal, forecast)
    ids = []
    for customer_ref, record_refs in sorted(groups.items()):
        ids.append(
            review_inbox.propose(
                db,
                str(principal.tenant_id),
                agent_id="receivables",
                reviewer=JobFunction.FINANCE,
                level=AutonomyLevel.L2,
                title=f"Payment reminder for {_customer_label(customer_ref)}",
                summary=f"Review one reminder covering {len(record_refs)} {source}. "
                "Verify the recipient, balance and timing before sending. Nothing has been sent.",
                draft="Please confirm the payment date for the outstanding invoices "
                "on your account. "
                "If payment has already been arranged, please let us know. Thank you.",
                evidence=[
                    EvidenceRef(label="Customer record", source=customer_ref),
                    *[EvidenceRef(label="Receivable record", source=ref) for ref in record_refs],
                ],
            )
        )
    return (
        [
            _step(
                "Receivables",
                "attention" if groups else "done",
                f"No invoice is past due. {len(groups)} customers have {source} "
                f"on day {forecast.shortfall.day}; asking them to confirm payment dates "
                "helps cover it."
                if source == _BEFORE_GAP
                else f"{len(groups)} customers with {source} found.",
            ),
            _step(
                "Reminder drafts",
                "attention" if ids else "done",
                f"{len(ids)} L2 inbox items await the owner's review; one per customer. "
                "No email, Telegram message or sendable outreach action was created.",
            ),
        ],
        ids,
        "inbox",
        forecast.data_mode,
    )


def _pay_everyone(db, principal):
    basis, forecast = _forecast(db, principal, horizon=30)
    # State the rolling window explicitly; demo day 23 can cross a calendar month.
    payroll = sum(
        (
            s.amount_myr
            for s in forecast.drivers
            if s.kind == "outflow"
            and s.source_agent == "hr_payroll"
            and s.likely_day is not None
            and s.likely_day <= 30
        ),
        _ZERO,
    )
    outflows = sum(
        (
            s.amount_myr
            for s in forecast.drivers
            if s.kind == "outflow" and s.likely_day is not None and s.likely_day <= 30
        ),
        _ZERO,
    )
    inflows = sum(
        (
            s.amount_myr
            for s in forecast.drivers
            if s.kind == "inflow" and s.likely_day is not None and s.likely_day <= 30
        ),
        _ZERO,
    )
    shortfall = forecast.shortfall
    spare = min(p.likely for p in forecast.points) - forecast.minimum_balance
    answer = (
        f"Short by {_money(shortfall.gap)} around day {shortfall.day} "
        f"({shortfall.date:%d %b %Y}); likely balance {_money(shortfall.likely_balance)}. "
        "This is the gap to your cash minimum, not an overdraft."
        if shortfall
        else f"Yes, {_money(spare)} spare above your cash minimum at the lowest point."
    )
    steps = [
        _step(
            "Planning window",
            "done",
            f"Next 30 days from {forecast.as_of:%d %b %Y}. "
            "This is a rolling forecast, not a completed calendar-month reconciliation.",
        ),
        _step(
            "Inflows and outflows",
            "done",
            f"Likely inflows {_money(inflows)}; outflows "
            f"{_money(outflows)}, including payroll {_money(payroll)}. "
            "Only records represented in the forecast are included.",
        ),
        _step("Can we pay?", "attention" if shortfall else "done", answer),
    ]
    if shortfall:
        early = agent_runtime._early_receivables(forecast)
        if early:
            shifts = [
                EventShift(event_id=s.id, shift_days=shortfall.day - 1 - s.likely_day)
                for s in early
            ]
            scenario = cashflow_engine.build_forecast(
                basis, horizon_days=30, as_of=forecast.as_of, shifts=shifts
            )
            at_day = scenario.points[shortfall.day].likely
            remaining = max(_ZERO, forecast.minimum_balance - at_day)
            steps.append(
                _step(
                    "Collect earlier",
                    "attention",
                    f"Illustrative scenario: collect {len(early)} later "
                    f"receivable{'s' if len(early) != 1 else ''} "
                    f"before day {shortfall.day}. Gap on that day becomes "
                    f"{_money(remaining)}. No receipt date was changed.",
                )
            )
        payable = next(
            (
                s
                for s in forecast.drivers
                if s.kind == "outflow"
                and s.source_agent in ("payables", "purchasing")
                and s.likely_day == shortfall.day
            ),
            None,
        )
        if payable:
            scenario = cashflow_engine.build_forecast(
                basis,
                horizon_days=30,
                as_of=forecast.as_of,
                shifts=[EventShift(event_id=payable.id, shift_days=7)],
            )
            steps.append(
                _step(
                    "Discuss payment timing",
                    "attention",
                    "Illustrative scenario: agree a seven-day delay on one supplier "
                    f"payment. Day {shortfall.day} balance becomes "
                    f"{_money(scenario.points[shortfall.day].likely)}. "
                    "The payment still falls due later; no schedule was changed.",
                )
            )
        if not early and not payable:
            steps.append(
                _step(
                    "Options",
                    "not_measured",
                    "No eligible receipt or supplier shift is on record for this gap.",
                )
            )
    return steps, [], "cashflow", forecast.data_mode


def _today() -> dt.date:
    return dt.date.today()


def _reconciliation_step(db, tenant_id: str):
    result = bank_matching.match(db, tenant_id, _today())
    if not result.lines:
        return _step(
            "Bank reconciliation",
            "not_measured",
            f"Bank reconciliation: not measured. No bank lines for {result.label} are on record.",
        )
    text = (
        f"{result.label}: {result.matched} of {result.lines} bank lines match a record "
        f"(same amount, within {bank_matching.WINDOW_DAYS} days)."
    )
    if result.unmatched:
        shown = "; ".join(
            f"{_money(u.amount)} {'out' if u.direction == 'debit' else 'in'} "
            f"on {u.posted_on:%d %b}"
            for u in result.unmatched[:3]
        )
        more = len(result.unmatched) - 3
        text += f" No record yet for: {shown}" + (f" and {more} more." if more > 0 else ".")
    return _step("Bank reconciliation", "attention" if result.unmatched else "done", text)


def _month_end(db, principal):
    tenant_id = str(principal.tenant_id)
    latest = db.scalar(
        select(func.max(BusinessImportBatch.created_at)).where(
            BusinessImportBatch.tenant_id == tenant_id,
        )
    )
    if latest is None:
        imported = _step("Recent import", "not_measured", "No business import is on record.")
    else:
        latest = latest.replace(tzinfo=dt.UTC) if latest.tzinfo is None else latest
        age = dt.datetime.now(dt.UTC) - latest
        fresh = dt.timedelta(0) <= age <= dt.timedelta(days=7)
        imported = _step(
            "Recent import",
            "done" if fresh else "attention",
            f"Last import: {latest:%d %b %Y}. "
            + ("Within seven days." if fresh else "Outside the seven-day window."),
        )
    readiness = einvoice_readiness.compute_readiness(
        db,
        role=principal.role,
        actor_ref=str(principal.user_id),
        tenant_id=tenant_id,
    )
    unresolved = (
        db.scalar(
            select(func.count()).where(
                EInvoiceRecord.tenant_id == tenant_id,
                EInvoiceRecord.status.in_(("pending", "rejected", "review")),
            )
        )
        or 0
    )
    _, inbox = review_inbox.inbox(db, principal, None)
    opened = sum(a.status in ("pending", "awaiting_second_approval", "edited") for a in inbox)
    # Only real tenant records for closing; synthetic sample inbox items aren't books.
    steps = [
        imported,
        _step(
            "e-Invoices",
            "not_measured"
            if not readiness.total_records
            else "attention"
            if unresolved or readiness.critical.count or readiness.warning.count
            else "done",
            f"{readiness.total_records} records; {unresolved} pending, rejected "
            f"or in review; {readiness.critical.count} critical and "
            f"{readiness.warning.count} warning readiness issues.",
        ),
        _step(
            "Open inbox items",
            "attention" if opened else "done",
            f"{opened} item{'s' if opened != 1 else ''} still open in your review inbox.",
        ),
        _reconciliation_step(db, tenant_id),
    ]
    return steps, [], "inbox", None


def run(db, principal: AuthPrincipal, playbook_id: str) -> PlaybookResult:
    if playbook_id not in TITLES:
        raise HTTPException(404, "playbook_not_found")
    if not allowed(principal, playbook_id):
        raise HTTPException(403, "playbook_not_allowed")
    if db is None:
        raise HTTPException(503, "playbook_storage_unavailable")
    tools = {
        "bank_meeting": [
            ("cashflow", "forecast"),
            ("financing", "match_products"),
            ("financing", "readiness_passport"),
        ],
        "chase_late_payers": [
            ("cashflow", "forecast"),
            ("receivables", "rank_overdue"),
            ("receivables", "draft_reminders"),
        ],
        "pay_everyone": [("cashflow", "forecast"), ("cashflow", "scenarios")],
        "month_end": [],
    }
    for agent, skill in tools[playbook_id]:
        agent_runtime.authorize(db, principal, agent, skill)
    handlers = {
        "bank_meeting": _bank_meeting,
        "chase_late_payers": _chase_late_payers,
        "pay_everyone": _pay_everyone,
        "month_end": _month_end,
    }
    steps, ids, screen, mode = handlers[playbook_id](db, principal)
    synthetic = (
        mode == DataMode.STUB or db.get(SyntheticTenantSeed, str(principal.tenant_id)) is not None
    )
    note = (
        "Cash forecast and financing profile use synthetic demo data. "
        "Record checks use only this tenant's records."
        if mode == DataMode.STUB
        else "Computed from this company's records."
        if synthetic
        else "Computed from this tenant's records."
    )
    write_workflow_event(
        db,
        event_type="assistant_playbook",
        actor_role=principal.role.value,
        actor_ref=str(principal.user_id),
        resource_type="assistant_playbook",
        resource_id="pb_" + secrets.token_hex(6),
        tenant_id=str(principal.tenant_id),
        event_payload={"playbook": playbook_id, "inbox_item_ids": ids},
    )
    db.commit()
    return PlaybookResult(
        playbook=playbook_id,
        title=TITLES[playbook_id],
        steps=steps,
        inbox_item_ids=ids,
        next_screen=screen,
        synthetic=synthetic,
        data_note=note,
    )
