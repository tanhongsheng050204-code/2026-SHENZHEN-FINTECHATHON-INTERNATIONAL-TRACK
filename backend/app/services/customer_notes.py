"""Per-customer risk notes and the money side of a customer's timeline.

The risk note is a short text written by fixed rules from the customer's own
receivables (sales ledger lines and validated e-invoices) and attention signals:
code computes it, no language model is involved, and it names the records it read.
It never contains a person's name or contact details.

The rules, so anyone can check a band by hand:
- an invoice up to GRACE_DAYS late is "within the grace period", not overdue;
- payment history is the average days late of paid e-invoices (the sales ledger
  keeps no separate paid date), shown only with at least MIN_HISTORY of them;
- "slower than usual": the oldest overdue invoice is more than SLOWER_BY days later
  than the customer's usual;
- high: anything more than HIGH_DAYS late, or a usual lateness above HIGH_DAYS;
- medium: anything overdue beyond the grace period, slower than usual, or warning
  signs in linked messages; low: everything else.

The timeline adds invoices issued, payments received and reminder proposals to the
protected messages a customer already shows, newest first.
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from app.models import CustomerAttentionSignal, EInvoiceRecord, SalesPipeline
from app.schemas import CustomerTimelineItemResponse

SOURCE_LEDGER = "Sales ledger"
SOURCE_EINVOICE = "Validated e-invoices"
SOURCE_SIGNALS = "Attention signals"
GRACE_DAYS = 3
MIN_HISTORY = 3
SLOWER_BY = 14
HIGH_DAYS = 30


def _money(amount: Decimal) -> str:
    return f"RM{amount:,.2f}"


def _open_items(db, tenant_id: str, customer_id: int) -> tuple[list, set[str]]:
    """(due date, amount) for each open receivable, and the sources that had any."""
    items, sources = [], set()
    for row in db.scalars(
        select(SalesPipeline).where(
            SalesPipeline.tenant_id == tenant_id,
            SalesPipeline.customer_id == customer_id,
            SalesPipeline.stage == "invoiced",
        )
    ):
        items.append((row.expected_payment_date, Decimal(row.amount)))
        sources.add(SOURCE_LEDGER)
    for row in db.scalars(
        select(EInvoiceRecord).where(
            EInvoiceRecord.tenant_id == tenant_id,
            EInvoiceRecord.buyer_customer_id == customer_id,
            EInvoiceRecord.status == "validated",
            EInvoiceRecord.paid_at.is_(None),
        )
    ):
        items.append((row.due_date, Decimal(row.total_amount)))
        sources.add(SOURCE_EINVOICE)
    return items, sources


def _usual_lateness(db, tenant_id: str, customer_id: int) -> tuple[int, int] | None:
    """(average days late, how many) over paid e-invoices; None below MIN_HISTORY."""
    lates = [
        max(0, (row.paid_at - row.due_date).days)
        for row in db.scalars(
            select(EInvoiceRecord).where(
                EInvoiceRecord.tenant_id == tenant_id,
                EInvoiceRecord.buyer_customer_id == customer_id,
                EInvoiceRecord.status == "validated",
                EInvoiceRecord.paid_at.is_not(None),
                EInvoiceRecord.due_date.is_not(None),
            )
        )
    ]
    if len(lates) < MIN_HISTORY:
        return None
    return round(sum(lates) / len(lates)), len(lates)


def _days(n: int) -> str:
    return f"{n} day{'s' if n != 1 else ''}"


def risk_note(
    db, tenant_id: str, customer_id: int, snapshot_id: int | None, as_of: dt.date
) -> tuple[str, list[str], str]:
    """(note, sources read, band) for one customer."""
    items, sources = _open_items(db, tenant_id, customer_id)
    late = [
        ((as_of - due).days, amount) for due, amount in items if due is not None and due < as_of
    ]
    overdue = [(days, amount) for days, amount in late if days > GRACE_DAYS]
    in_grace = [(days, amount) for days, amount in late if days <= GRACE_DAYS]
    warnings = 0
    if snapshot_id is not None:
        warnings = len(
            db.scalars(
                select(CustomerAttentionSignal.id).where(
                    CustomerAttentionSignal.snapshot_id == snapshot_id,
                    CustomerAttentionSignal.points > 0,
                )
            ).all()
        )
    oldest = max((days for days, _ in overdue), default=0)
    if overdue:
        total = sum((amount for _, amount in overdue), Decimal(0))
        count = len(overdue)
        note = (
            f"{_money(total)} overdue across {count} invoice{'s' if count != 1 else ''}; "
            f"the oldest is {_days(oldest)} late."
        )
    elif in_grace:
        days = max(days for days, _ in in_grace)
        total = sum((amount for _, amount in in_grace), Decimal(0))
        note = f"{_money(total)} due {_days(days)} ago, within the {GRACE_DAYS}-day grace period."
    elif items:
        total = sum((amount for _, amount in items), Decimal(0))
        upcoming = [due for due, _ in items if due is not None]
        note = f"{_money(total)} outstanding, none overdue"
        note += f"; next due in {(min(upcoming) - as_of).days} days." if upcoming else "."
    else:
        note = "Nothing outstanding."
    usual = _usual_lateness(db, tenant_id, customer_id)
    slower = False
    if usual is not None:
        average, count = usual
        note += f" Usually pays {_days(average)} late ({count} paid e-invoices)."
        sources.add(SOURCE_EINVOICE)
        slower = bool(overdue) and oldest > average + SLOWER_BY
        if slower:
            note += " Slower than usual."
    if warnings:
        note += f" {warnings} warning sign{'s' if warnings != 1 else ''} in linked messages."
        sources.add(SOURCE_SIGNALS)
    if oldest > HIGH_DAYS or (usual is not None and usual[0] > HIGH_DAYS):
        band = "high"
    elif overdue or slower or warnings:
        band = "medium"
    else:
        band = "low"
    return note, sorted(sources), band


def money_timeline(db, tenant_id: str, customer_id: int) -> list[CustomerTimelineItemResponse]:
    from app.services import review_inbox
    from app.services.collections import invoice_label

    items = []

    def at(day: dt.date | None) -> dt.datetime | None:
        return dt.datetime.combine(day, dt.time(9), tzinfo=dt.UTC) if day else None

    refs = {f"customer:{customer_id}"}
    for row in db.scalars(
        select(SalesPipeline).where(
            SalesPipeline.tenant_id == tenant_id, SalesPipeline.customer_id == customer_id
        )
    ):
        label = invoice_label(row.source_record_id, row.expected_payment_date)
        # A ledger line without a reference is already named by its due date.
        named = "" if label.startswith("Invoice due") else f" {label}"
        refs.add(f"pipeline:{row.id}")
        if row.stage == "paid":
            event = "payment_received"
            text = f"Payment received for invoice{named}, {_money(row.amount)}"
        elif row.stage == "invoiced":
            event = "invoice_open"
            text = (
                f"Invoice{named} open, {_money(row.amount)}, "
                f"due {row.expected_payment_date:%d %b %Y}"
            )
        else:
            continue
        items.append(
            CustomerTimelineItemResponse(
                event_id=f"pipeline:{row.id}",
                event_type=event,
                source_system="sales_ledger",
                occurred_at=at(row.expected_payment_date),
                protected_summary=text,
            )
        )
    for row in db.scalars(
        select(EInvoiceRecord).where(
            EInvoiceRecord.tenant_id == tenant_id, EInvoiceRecord.buyer_customer_id == customer_id
        )
    ):
        label = row.invoice_no or f"E-invoice {row.id}"
        refs.add(f"einvoice:{row.id}")
        items.append(
            CustomerTimelineItemResponse(
                event_id=f"einvoice:{row.id}",
                event_type="invoice_issued",
                source_system="einvoice",
                occurred_at=at(row.issue_date),
                protected_summary=f"E-invoice {label} issued, {_money(row.total_amount)}",
                einvoice_record_id=row.id,
            )
        )
        if row.paid_at:
            items.append(
                CustomerTimelineItemResponse(
                    event_id=f"einvoice-paid:{row.id}",
                    event_type="payment_received",
                    source_system="einvoice",
                    occurred_at=at(row.paid_at),
                    protected_summary=f"Payment received: {label}, {_money(row.total_amount)}",
                    einvoice_record_id=row.id,
                )
            )
    words = {
        "pending": "waiting for approval",
        "awaiting_second_approval": "waiting for a second approval",
        "edited": "edited and approved",
        "approved": "approved",
        "rejected": "rejected",
    }
    for item_id, item in review_inbox._replay(db, tenant_id).items():
        action = item.action
        if action.agent_id != "receivables":
            continue
        if not refs & {evidence.source for evidence in action.evidence}:
            continue
        items.append(
            CustomerTimelineItemResponse(
                event_id=f"review:{item_id}",
                event_type="reminder_proposed",
                source_system="review_inbox",
                occurred_at=action.created_at,
                protected_summary=f"Reminder proposed, {words.get(action.status, action.status)}",
            )
        )
    return items
