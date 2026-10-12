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


def test_each_horizon_has_an_accuracy_and_the_biggest_differences_are_explained(db):
    forecast_check.record(db, TENANT, _forecast())
    _bank(db, dt.date(2026, 9, 8), "72000.00", 1)
    _bank(db, dt.date(2026, 9, 15), "95000.00", 2)

    report = forecast_check.report(db, TENANT, DataMode.LIVE)
    by = {h.horizon_days: h for h in report.by_horizon}

    # 1 - |forecast - actual| / actual: 1 - 2,000/72,000 and 1 - 5,000/95,000.
    assert by[7].accuracy_pct == Decimal("97.2")
    assert by[14].accuracy_pct == Decimal("94.7")
    assert by[30].accuracy_pct is None

    first, second = report.largest_differences
    assert (first.date, first.difference_myr, first.within_range) == (
        dt.date(2026, 9, 15),
        Decimal("5000.00"),
        False,
    )
    # By day 14 the forecast expected the 20,000 receipt and the 30,000 bill.
    assert (first.expected_in_myr, first.expected_out_myr) == (
        Decimal("20000.00"),
        Decimal("30000.00"),
    )
    assert (second.expected_in_myr, second.expected_out_myr) == (
        Decimal("0.00"),
        Decimal("30000.00"),
    )


def test_the_snapshot_keeps_amounts_only(db):
    forecast_check.record(db, TENANT, _forecast())

    row = db.scalar(select(WorkflowAuditEntry))
    assert set(row.event_payload["targets"][0]) == {
        "horizon_days",
        "date",
        "likely",
        "best",
        "worst",
        "expected_in",
        "expected_out",
    }


def test_a_calibrated_range_needs_five_comparisons_then_covers_eighty_percent(db):
    from app.services.forecast_check import MIN_CALIBRATION

    # Seven days' forecasts, each scored 7 days later against a bank balance.
    balances = ["71000.00", "69000.00", "74000.00", "66000.00", "70500.00", "62000.00"]
    for n, balance in enumerate(balances):
        forecast_check.record(db, TENANT, _forecast(as_of=DAY0 + dt.timedelta(days=n)))
        _bank(db, DAY0 + dt.timedelta(days=n + 7), balance, n + 1)
    report = forecast_check.report(db, TENANT, DataMode.LIVE)
    week = next(h for h in report.by_horizon if h.horizon_days == 7)

    # The likely day-7 balance is 70,000 each time; misses 1,000 1,000 4,000 4,000 500 8,000.
    assert week.compared == 6 and MIN_CALIBRATION == 5
    # Split conformal at 80%: the ceil(7 * 0.8) = 6th smallest miss.
    assert week.calibrated_80_myr == Decimal("8000.00")
    assert week.calibration_needs == 0


def test_too_few_comparisons_say_how_many_are_still_needed(db):
    forecast_check.record(db, TENANT, _forecast())
    _bank(db, dt.date(2026, 9, 8), "72000.00", 1)

    week = next(
        h
        for h in forecast_check.report(db, TENANT, DataMode.LIVE).by_horizon
        if h.horizon_days == 7
    )
    assert week.calibrated_80_myr is None and week.calibration_needs == 4
