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


def test_employees_do_not_see_invoices_payments_or_reminders_on_the_timeline(
    live_db,  # noqa: F811
    monkeypatch,
):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.auth.dependencies import get_current_user
    from app.config import get_settings
    from app.db import get_db
    from app.routes.customers import router

    monkeypatch.setattr(get_settings(), "customer_intelligence_enabled", True)
    collections.propose_reminder(live_db, principal(UserRole.FINANCE_OPS), "pipeline:1", TODAY)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: live_db

    def timeline(role):
        app.dependency_overrides[get_current_user] = lambda: principal(role)
        return TestClient(app).get("/customers/7").json()["timeline"]

    assert len(timeline(UserRole.FINANCE_OPS)) == 6
    assert timeline(UserRole.GENERAL_EMPLOYEE) == []


def test_only_the_money_roles_read_risk_notes(live_db, monkeypatch):  # noqa: F811
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.auth.dependencies import get_current_user
    from app.config import get_settings
    from app.db import get_db
    from app.routes.customers import router

    monkeypatch.setattr(get_settings(), "customer_intelligence_enabled", True)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: live_db

    def rows(role, path):
        app.dependency_overrides[get_current_user] = lambda: principal(role)
        body = TestClient(app).get(path).json()
        return body["customers"] if path == "/briefing" else body

    assert rows(UserRole.FINANCE_OPS, "/customers")[0]["risk_note"].startswith("RM24,500.00")
    for path in ("/customers", "/briefing"):
        assert rows(UserRole.GENERAL_EMPLOYEE, path)[0]["risk_note"] is None
    assert rows(UserRole.GENERAL_EMPLOYEE, "/customers/7")["risk_note"] is None
    assert rows(UserRole.GENERAL_EMPLOYEE, "/customers/7")["risk_band"] is None


def _paid_einvoices(db, days_late: list[int]):
    import datetime as dt
    from decimal import Decimal

    from app.models import EInvoiceRecord

    for n, late in enumerate(days_late):
        due = TODAY - dt.timedelta(days=90 + n)
        db.add(
            EInvoiceRecord(
                tenant_id=str(TENANT_A),
                supplier_name="SYNTHETIC supplier",
                buyer_customer_id=7,
                invoice_no=f"EI-{n}",
                due_date=due,
                total_amount=Decimal("1000.00"),
                status="validated",
                paid_at=due + dt.timedelta(days=late),
            )
        )
    db.commit()


def test_a_customer_gets_a_band_from_fixed_rules(live_db):  # noqa: F811
    # INV-1 is 20 days late: beyond the grace period, not yet 30 days.
    [row] = list_customers(live_db, str(TENANT_A))
    assert row.risk_band == "medium"


def test_a_few_days_late_is_within_the_grace_period(live_db):  # noqa: F811
    import datetime as dt

    from app.models import SalesPipeline

    live_db.get(SalesPipeline, 1).expected_payment_date = TODAY - dt.timedelta(days=2)
    live_db.commit()

    [row] = list_customers(live_db, str(TENANT_A))
    assert row.risk_note.startswith("RM24,500.00 due 2 days ago, within the 3-day grace period")
    assert row.risk_band == "low"


def test_long_overdue_is_high(live_db):  # noqa: F811
    import datetime as dt

    from app.models import SalesPipeline

    live_db.get(SalesPipeline, 1).expected_payment_date = TODAY - dt.timedelta(days=45)
    live_db.commit()

    [row] = list_customers(live_db, str(TENANT_A))
    assert row.risk_band == "high"


def test_payment_history_and_slower_than_usual(live_db):  # noqa: F811
    _paid_einvoices(live_db, [2, 4, 6])

    [row] = list_customers(live_db, str(TENANT_A))
    assert "Usually pays 4 days late (3 paid e-invoices)" in row.risk_note
    # 20 days late now against a usual 4: more than two weeks slower.
    assert "Slower than usual." in row.risk_note
    assert "Validated e-invoices" in row.risk_sources


def test_too_little_history_is_not_measured(live_db):  # noqa: F811
    _paid_einvoices(live_db, [4, 6])

    [row] = list_customers(live_db, str(TENANT_A))
    assert "Usually pays" not in row.risk_note
    assert "Slower than usual" not in row.risk_note
