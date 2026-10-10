"""Business financial analysis from the company's own imported records.

Figures are on a cash basis: revenue when received, costs when paid. The synthetic
company's seed (seed/topic_e.py) carries July to September history; every expected
value below is computed by hand from that seed.
"""

import datetime as dt
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.auth.dependencies import get_current_user
from app.contracts.customization import ImportMappingRequest
from app.db import get_db
from app.schemas import UserRole
from app.services import cash_basis, cashflow_engine, financial_analysis
from app.services.business_imports import commit_import
from app.services.finance import revenue_summary
from app.services.import_mappings import save
from seed.topic_e import datasets
from tests.auth_support import principal

pytestmark = pytest.mark.skipif(
    not cash_basis._plan3_deployed(), reason="Plan 3 business tables not deployed"
)
TENANT = "00000000-0000-0000-0000-0000000000f1"
AS_OF = dt.date(2026, 10, 9)


def _person(role):
    return principal(role, tenant_id=UUID(TENANT))


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.Base.metadata.create_all(engine)
    owner = _person(UserRole.OWNER_DIRECTOR)
    with Session(engine, expire_on_commit=False) as session:
        session.add(models.Tenant(id=TENANT, slug="synthetic-analysis", name="SYNTHETIC co"))
        session.commit()
        for schema, (headers, columns, text) in datasets(AS_OF).items():
            mapping = save(
                session,
                owner,
                ImportMappingRequest(
                    schema_name=schema, name="Synthetic", headers=headers, column_map=columns
                ),
            )
            commit_import(session, owner, schema, text, mapping.id)
        yield session
    engine.dispose()


def _analysis(db):
    return financial_analysis.analyse(db, TENANT, AS_OF, months=3)


def test_paid_sales_never_enter_the_forecast(db):
    forecast = cashflow_engine.build_forecast(
        cash_basis.load(db, TENANT, AS_OF), horizon_days=90, as_of=AS_OF
    )

    assert (forecast.shortfall.day, forecast.shortfall.likely_balance) == (
        23,
        Decimal("20560.00"),
    )
    assert not any(s.label.startswith("Paid") for s in forecast.drivers)


def test_monthly_profit_and_loss_matches_the_seeded_records(db):
    months = {m.month: m for m in _analysis(db).months}

    september = months["2026-09"]
    assert september.revenue == Decimal("249400.00")
    assert september.purchases == Decimal("126000.00")
    assert september.payroll == Decimal("62000.00")
    assert september.rent_and_bills == Decimal("14800.00")
    assert september.marketing == Decimal("6000.00")
    assert september.marketplace_fees == Decimal("1400.00")
    assert september.total_costs == Decimal("210200.00")
    assert september.gross_profit == Decimal("123400.00")
    assert september.net_result == Decimal("39200.00")
    assert september.gross_margin == Decimal("49.5")
    assert september.net_margin == Decimal("15.7")
    assert months["2026-07"].net_result == Decimal("20000.00")
    assert months["2026-08"].net_result == Decimal("23800.00")
    assert list(months) == ["2026-07", "2026-08", "2026-09"]


def test_ratios_show_formula_value_and_sources(db):
    ratios = {r.key: r for r in _analysis(db).ratios}

    assert ratios["days_to_get_paid"].value == Decimal("46.0")
    assert ratios["days_to_pay_suppliers"].value == Decimal("42.9")
    assert ratios["marketing_return"].value == Decimal("4.21")
    assert ratios["largest_customer_share"].value == Decimal("29.3")
    assert ratios["payroll_share"].value == Decimal("26.9")
    assert ratios["cash_runway"].value == Decimal("23")
    assert all(r.formula and r.sources for r in ratios.values())
    assert all(r.status == "measured" for r in ratios.values())


def test_a_ratio_without_records_is_not_measured():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.Base.metadata.create_all(engine)
    with Session(engine) as empty:
        empty.add(models.Tenant(id=TENANT, slug="empty", name="Empty"))
        empty.commit()
        ratios = {r.key: r for r in financial_analysis.analyse(empty, TENANT, AS_OF).ratios}

    assert ratios["marketing_return"].status == "not_measured"
    assert ratios["marketing_return"].value is None


def test_what_changed_names_the_three_largest_movements(db):
    assert _analysis(db).changes == [
        "Revenue rose RM21,700.00 (+9.5%) in September 2026.",
        "Net result rose RM15,400.00 (+64.7%) in September 2026.",
        "Purchases rose RM5,000.00 (+4.1%) in September 2026.",
    ]


def _client(db, role):
    from app.routes.analysis import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: _person(role)
    return TestClient(app)


def test_route_serves_finance_roles_and_refuses_general_employees(db):
    allowed = _client(db, UserRole.COMPLIANCE).get("/analysis", params={"months": 3})
    refused = _client(db, UserRole.GENERAL_EMPLOYEE).get("/analysis")

    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["data_mode"] == "live"
    assert refused.status_code == 403


def test_payroll_appears_only_as_totals(db):
    body = _client(db, UserRole.OWNER_DIRECTOR).get("/analysis").text

    assert "Employee" not in body and "SYNTHETIC Employee" not in body


def test_receivables_summary_reads_the_sales_ledger(db):
    now = dt.datetime(2026, 10, 9, 12, tzinfo=dt.UTC)

    september = revenue_summary(db, TENANT, period="month", offset=-1, now=now)

    assert september.total_revenue == Decimal("249400.00")
    assert september.outstanding_ar == Decimal("353500.00")
    assert sum(b.total_amount for b in september.ar_aging) == Decimal("353500.00")


def test_receivables_tab_names_ledger_customers_for_finance(db):
    from app.routes.finance import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: _person(UserRole.FINANCE_OPS)

    body = TestClient(app).get("/finance/summary").json()

    assert body["top_customers"][0]["name"] == "SYNTHETIC Customer A"
