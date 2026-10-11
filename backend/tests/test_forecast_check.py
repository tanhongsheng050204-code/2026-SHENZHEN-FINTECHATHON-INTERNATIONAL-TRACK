"""Forecast check: each day's forecast is kept, then scored against the bank balance."""

import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.contracts.common import DataMode
from app.models import BankTransaction, Base, Tenant, WorkflowAuditEntry
from app.services import cashflow_engine, forecast_check
from app.services.cashflow_engine import CashBasis, Signal

TENANT = "00000000-0000-0000-0000-0000000000aa"
DAY0 = dt.date(2026, 9, 1)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Tenant(id=TENANT, slug="pilot", name="Pilot Co"))
    session.commit()
    return session


def _forecast(as_of=DAY0, data_mode=DataMode.LIVE):
    # 100,000 today; a 30,000 bill on day 5; a 20,000 receipt likely on day 10,
    # day 3 at best and day 24 at worst.
    basis = CashBasis(
        data_mode,
        Decimal("100000.00"),
        Decimal("10000.00"),
        (
            Signal("B1", "payables", "finance", "outflow", "Bill", Decimal("30000"), 5, 5, 5),
            Signal(
                "R1", "receivables", "finance", "inflow", "Invoice", Decimal("20000"), 3, 10, 24
            ),
        ),
    )
    return cashflow_engine.build_forecast(basis, horizon_days=30, as_of=as_of)


def _bank(db, posted_on: dt.date, balance: str, n: int):
    db.add(
        BankTransaction(
            id=n,
            tenant_id=TENANT,
            source_record_id=f"r{n}",
            record_hash="0" * 64,
            batch_id="b1",
            posted_on=posted_on,
            description_token="tok",
            direction="credit",
            amount=Decimal("1.00"),
            balance=Decimal(balance),
        )
    )
    db.commit()


def test_a_live_forecast_is_kept_once_a_day_on_the_chain(db):
    forecast_check.record(db, TENANT, _forecast())
    forecast_check.record(db, TENANT, _forecast())

    rows = db.scalars(
        select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "forecast_snapshot")
    ).all()
    assert len(rows) == 1
    targets = rows[0].event_payload["targets"]
    assert [t["horizon_days"] for t in targets] == [7, 14, 30]
    # Day 7: 100,000 - 30,000, the receipt not yet in the likely case.
    assert targets[0]["likely"] == "70000.00"
    assert targets[0]["date"] == "2026-09-08"


def test_synthetic_and_back_dated_forecasts_are_not_kept(db):
    forecast_check.record(db, TENANT, _forecast(data_mode=DataMode.STUB))
    count = db.scalar(select(func.count()).select_from(WorkflowAuditEntry))
    assert count == 0


def test_nothing_is_measured_until_the_bank_statement_covers_a_target_day(db):
    forecast_check.record(db, TENANT, _forecast())
    _bank(db, dt.date(2026, 9, 5), "70000.00", 1)

    report = forecast_check.report(db, TENANT, DataMode.LIVE)

    assert report.status == "not_measured"
    assert report.forecasts_kept == 1
    assert report.compared == 0
    assert report.first_comparison_on == dt.date(2026, 9, 8)


def test_each_covered_target_is_scored_against_the_balance_that_day(db):
    forecast_check.record(db, TENANT, _forecast())
    # Day 7 ends at 72,000 (likely 70,000, best 90,000); day 14 at 95,000, above the best.
    _bank(db, dt.date(2026, 9, 8), "72000.00", 1)
    _bank(db, dt.date(2026, 9, 15), "95000.00", 2)

    report = forecast_check.report(db, TENANT, DataMode.LIVE)

    assert report.status == "measured"
    assert report.compared == 2
    by = {h.horizon_days: h for h in report.by_horizon}
    assert by[7].mean_abs_error_myr == Decimal("2000.00")
    assert by[7].within_range == 1
    assert by[14].mean_abs_error_myr == Decimal("5000.00")
    assert by[14].within_range == 0
    assert report.within_range == 1
    assert by[30].compared == 0


def test_the_demo_company_says_why_it_is_not_measured(db):
    report = forecast_check.report(db, TENANT, DataMode.STUB)

    assert report.status == "not_measured"
    assert report.reason == "synthetic_company"
