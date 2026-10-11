"""The collections board: every receivable in one of five columns.

Later → Due soon (within DUE_SOON_DAYS) → Overdue → Reminder waiting for approval
→ Paid (in the last PAID_WINDOW_DAYS). A receivable is an invoiced line of the
company's sales ledger or a validated e-invoice; "Reminder" means an open
reminder proposal in the review inbox cites it.

The board only shows where money is. Moving a card to "Reminder" asks the
Collections agent for a reminder proposal, which a person approves in the review
inbox like any other: nothing is sent from the board. Customers appear as the
masked name the customer list shows, never restored here.

The synthetic demo company, which has no ledger, shows its sample receivables.
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from app.auth.principal import AuthPrincipal
from app.contracts.collaboration import BoardCard, BoardColumn, CollectionsBoardResponse
from app.contracts.common import AutonomyLevel, DataMode, EvidenceRef, JobFunction
from app.models import Customer, EInvoiceRecord, ProtectedTokenRegistry, SalesPipeline
from app.services import cashflow, review_inbox

DUE_SOON_DAYS = 14
PAID_WINDOW_DAYS = 30
STAGES = ("later", "due_soon", "overdue", "reminder", "paid")
_OPEN = ("pending", "awaiting_second_approval", "edited")
ZERO = Decimal("0.00")


class BoardError(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _customer_labels(db, tenant_id: str, ids: set[int]) -> dict[int, str]:
    labels = {}
    for customer in db.scalars(
        select(Customer).where(Customer.tenant_id == tenant_id, Customer.id.in_(ids))
    ):
        registry = (
            db.get(ProtectedTokenRegistry, customer.primary_name_token)
            if customer.primary_name_token
            else None
        )
        labels[customer.id] = registry.masked_value if registry else customer.canonical_name
    return labels


def _reminded(db, tenant_id: str) -> dict[str, str]:
    """Receivable ref → the open reminder proposal that cites it."""
    cited = {}
    for item_id, item in review_inbox._replay(db, tenant_id).items():
        action = item.action
        if action.agent_id == "receivables" and action.status in _OPEN:
            for evidence in action.evidence:
                cited.setdefault(evidence.source, item_id)
    return cited


def _stage(due: dt.date | None, paid: bool, as_of: dt.date) -> str | None:
    if paid:
        return "paid"
    if due is None:
        return "later"
    if due < as_of:
        return "overdue"
    return "due_soon" if (due - as_of).days <= DUE_SOON_DAYS else "later"


def _label(source_record_id: str) -> str:
    return source_record_id.rsplit(":", 1)[-1]


def _live_cards(db, tenant_id: str, as_of: dt.date) -> list[BoardCard]:
    paid_since = as_of - dt.timedelta(days=PAID_WINDOW_DAYS)
    raw = []
    for row in db.scalars(
        select(SalesPipeline).where(
            SalesPipeline.tenant_id == tenant_id, SalesPipeline.stage.in_(("invoiced", "paid"))
        )
    ):
        paid = row.stage == "paid"
        if paid and not (paid_since <= row.expected_payment_date <= as_of):
            continue
        raw.append(
            (
                f"pipeline:{row.id}",
                _label(row.source_record_id),
                row.customer_id,
                Decimal(row.amount),
                row.expected_payment_date,
                paid,
            )
        )
    for row in db.scalars(
        select(EInvoiceRecord).where(
            EInvoiceRecord.tenant_id == tenant_id, EInvoiceRecord.status == "validated"
        )
    ):
        paid = row.paid_at is not None
        if paid and not (paid_since <= row.paid_at <= as_of):
            continue
        raw.append(
            (
                f"einvoice:{row.id}",
                row.invoice_no or f"E-invoice {row.id}",
                row.buyer_customer_id,
                Decimal(row.total_amount),
                row.due_date,
                paid,
            )
        )
    labels = _customer_labels(db, tenant_id, {r[2] for r in raw if r[2] is not None})
    return [
        BoardCard(
            ref=ref,
            label=label,
            customer_id=customer_id,
            customer_label=labels.get(customer_id, "Customer") if customer_id else "Customer",
            amount=amount,
            due_date=due,
            days_overdue=max(0, (as_of - due).days) if due and not paid else 0,
            stage=_stage(due, paid, as_of),
        )
        for ref, label, customer_id, amount, due, paid in raw
    ]


def _demo_cards(as_of: dt.date, basis) -> list[BoardCard]:
    cards = []
    for signal in basis.signals:
        if signal.agent != "receivables" or signal.kind != "inflow":
            continue
        invoice, _, customer = signal.label.partition(" · ")
        # The sample receivables are due on their likely day, counted from today.
        due = as_of + dt.timedelta(days=signal.likely_day or signal.best_day)
        cards.append(
            BoardCard(
                ref=f"cash-signal:{signal.id}",
                label=invoice,
                customer_id=None,
                customer_label=f"Synthetic {customer.lower()}" if customer else "Customer",
                amount=signal.amount,
                due_date=due,
                days_overdue=0,
                stage=_stage(due, False, as_of),
            )
        )
    return cards


def board(db, principal: AuthPrincipal, as_of: dt.date) -> CollectionsBoardResponse:
    tenant_id = str(principal.tenant_id)
    basis = cashflow.basis_for(db, principal, as_of)
    live = basis.data_mode == DataMode.LIVE and db is not None
    cards = _live_cards(db, tenant_id, as_of) if live else _demo_cards(as_of, basis)
    if db is not None:
        reminded = _reminded(db, tenant_id)
        cards = [
            card.model_copy(update={"stage": "reminder", "reminder_action_id": reminded[card.ref]})
            if card.ref in reminded and card.stage != "paid"
            else card
            for card in cards
        ]
    columns = []
    for stage in STAGES:
        chosen = sorted(
            (card for card in cards if card.stage == stage),
            key=lambda card: (card.due_date or as_of, card.ref),
        )
        columns.append(
            BoardColumn(stage=stage, total=sum((c.amount for c in chosen), ZERO), cards=chosen)
        )
    return CollectionsBoardResponse(
        data_mode=DataMode.LIVE if live else DataMode.STUB, as_of=as_of, columns=columns
    )


def propose_reminder(db, principal: AuthPrincipal, ref: str, as_of: dt.date) -> str:
    """Moving a card to "Reminder": one reminder proposal for that receivable."""
    current = board(db, principal, as_of)
    card = next((c for column in current.columns for c in column.cards if c.ref == ref), None)
    if card is None:
        raise BoardError("receivable_not_found", 404)
    if card.stage == "paid":
        raise BoardError("receivable_already_paid", 409)
    if card.stage == "reminder":
        return card.reminder_action_id
    customer_ref = f"customer:{card.customer_id}" if card.customer_id else None
    when = (
        f"{card.days_overdue} days overdue" if card.days_overdue else f"due {card.due_date:%d %b}"
    )
    return review_inbox.propose(
        db,
        str(principal.tenant_id),
        agent_id="receivables",
        reviewer=JobFunction.FINANCE,
        level=AutonomyLevel.L2,
        title=f"Payment reminder for {card.label}",
        summary=f"Review one reminder for {card.label}, {when}. Verify the recipient, "
        "balance and timing before sending. Nothing has been sent.",
        amount=card.amount,
        draft="Please confirm the payment date for the outstanding invoice on your account. "
        "If payment has already been arranged, please let us know. Thank you.",
        evidence=[
            *([EvidenceRef(label="Customer record", source=customer_ref)] if customer_ref else []),
            EvidenceRef(label="Receivable record", source=ref),
        ],
    )
