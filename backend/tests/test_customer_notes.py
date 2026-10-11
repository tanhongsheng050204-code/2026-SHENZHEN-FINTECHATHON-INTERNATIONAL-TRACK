"""Risk notes written by rules from records, and the money side of the timeline."""

from app.models import Customer
from app.schemas import UserRole
from app.services import collections
from app.services.customer_intelligence import customer_detail, list_customers
from tests.auth_support import TENANT_A, principal
from tests.test_collections_board import TODAY, live_db  # noqa: F401  (fixture)


def test_the_risk_note_names_the_overdue_amount_and_its_source(live_db):  # noqa: F811
    [row] = list_customers(live_db, str(TENANT_A))

    assert row.risk_note == "RM24,500.00 overdue across 1 invoice; the oldest is 20 days late."
    assert row.risk_sources == ["Sales ledger"]


def test_a_customer_with_nothing_open_says_so(live_db):  # noqa: F811
    live_db.add(
        Customer(id=8, tenant_id=str(TENANT_A), canonical_name="Kedai B", normalized_name="kedai b")
    )
    live_db.commit()

    notes = {row.id: row.risk_note for row in list_customers(live_db, str(TENANT_A))}
    assert notes[8] == "Nothing outstanding."


def test_the_timeline_shows_invoices_payments_and_reminders(live_db):  # noqa: F811
    collections.propose_reminder(live_db, principal(UserRole.FINANCE_OPS), "pipeline:1", TODAY)

    timeline = customer_detail(live_db, str(TENANT_A), 7).timeline
    kinds = [item.event_type for item in timeline]

    assert kinds.count("invoice_open") == 3
    assert kinds.count("payment_received") == 2
    assert kinds.count("reminder_proposed") == 1
    reminder = next(item for item in timeline if item.event_type == "reminder_proposed")
    assert reminder.protected_summary == "Reminder proposed, waiting for approval"
    # Newest first.
    dates = [item.occurred_at for item in timeline if item.occurred_at]
    assert dates == sorted(dates, reverse=True)
