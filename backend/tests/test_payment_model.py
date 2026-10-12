"""The payment-delay model: learn how late each customer pays, and use it for the worst case."""

import datetime as dt
from decimal import Decimal

from app.models import Customer, EInvoiceRecord, SalesPipeline
from app.services import cash_basis, payment_model
from tests.auth_support import TENANT_A
from tests.test_collections_board import TODAY, _client, live_db  # noqa: F401


def _paid(db, customer_id: int, days_late: list[int], start: int = 0):
    for n, late in enumerate(days_late):
        due = TODAY - dt.timedelta(days=120 + start + n)
        db.add(
            EInvoiceRecord(
                tenant_id=str(TENANT_A),
                supplier_name="SYNTHETIC supplier",
                buyer_customer_id=customer_id,
                invoice_no=f"EI-{customer_id}-{start + n}",
                due_date=due,
                total_amount=Decimal("1000.00"),
                status="validated",
                paid_at=due + dt.timedelta(days=late),
            )
        )
    db.commit()


def test_without_history_the_worst_case_keeps_the_default(live_db):  # noqa: F811
    model = payment_model.fit(live_db, str(TENANT_A))

    assert model.extra_days(7) == cash_basis.WORST_CASE_EXTRA_DAYS
    assert model.basis(7) == "default"


def test_a_customer_with_history_gets_its_own_spread(live_db):  # noqa: F811
    # Usually 5 days late, sometimes 25: the spread beyond the usual is 20 days.
    _paid(live_db, 7, [3, 4, 5, 5, 5, 6, 6, 7, 25, 25])

    model = payment_model.fit(live_db, str(TENANT_A))
    learned = model.customers[7]
    assert (learned.paid_invoices, learned.median_days_late) == (10, 5)
    assert model.basis(7) == "customer"
    # Shrunk towards the company figure: with only this customer the two agree.
    assert model.extra_days(7) == 20


def test_few_invoices_lean_on_the_company_figure(live_db):  # noqa: F811
    live_db.add(Customer(id=8, tenant_id=str(TENANT_A), canonical_name="B", normalized_name="b"))
    live_db.commit()
    _paid(live_db, 7, [2, 2, 2, 2, 2, 2, 2, 2, 12, 12], start=0)  # spread 10
    _paid(live_db, 8, [0, 0, 40], start=50)  # spread 40, but only three invoices

    model = payment_model.fit(live_db, str(TENANT_A))
    assert model.basis(8) == "customer"
    # Between its own 40 and the company's spread, pulled towards the company.
    assert model.company_extra_days < model.extra_days(8) < 40


def test_the_forecast_uses_the_learned_worst_case(live_db, monkeypatch):  # noqa: F811
    _paid(live_db, 7, [3, 4, 5, 5, 5, 6, 6, 7, 25, 25])
    monkeypatch.setattr(cash_basis, "_plan3_deployed", lambda: True)
    monkeypatch.setattr(cash_basis, "_opening_balance", lambda *a: Decimal("100000.00"))

    basis = cash_basis.load(live_db, str(TENANT_A), TODAY)
    signal = next(s for s in basis.signals if s.id == "INV-2")  # due in 5 days
    assert (signal.likely_day, signal.worst_day) == (5, 25)


def test_the_backtest_measures_coverage_on_past_invoices(live_db):  # noqa: F811
    _paid(live_db, 7, [3, 4, 5, 5, 5, 6, 6, 7, 25, 25])

    report = payment_model.report(live_db, str(TENANT_A))
    assert report.learned_from == 10
    assert report.backtest is not None and report.backtest.checked == 10
    assert 0 <= report.backtest.within <= 10
    assert report.backtest.coverage_pct == round(100 * report.backtest.within / 10, 1)


def test_the_route_shows_what_was_learned_to_money_roles(live_db):  # noqa: F811
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.auth.dependencies import get_current_user
    from app.db import get_db
    from app.routes.cashflow import router
    from app.schemas import UserRole
    from tests.auth_support import principal

    _paid(live_db, 7, [3, 4, 5, 5, 5, 6, 6, 7, 25, 25])

    def client(role):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_db] = lambda: live_db
        app.dependency_overrides[get_current_user] = lambda: principal(role)
        return TestClient(app)

    body = client(UserRole.FINANCE_OPS).get("/cashflow/payment-model").json()
    [row] = body["customers"]
    assert (row["customer_id"], row["label"], row["worst_extra_days"]) == (7, "Kedai A", 20)
    assert client(UserRole.GENERAL_EMPLOYEE).get("/cashflow/payment-model").status_code == 403


def test_unused_sales_pipeline_rows_do_not_count(live_db):  # noqa: F811
    # The model learns from paid e-invoices only: the sales ledger keeps no paid date.
    assert live_db.query(SalesPipeline).count() == 5
    assert payment_model.fit(live_db, str(TENANT_A)).learned_from == 0
