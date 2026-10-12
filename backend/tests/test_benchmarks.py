"""Benchmarks across companies with differential privacy: no company's figure can be worked out."""

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, EInvoiceRecord, Tenant
from app.services import benchmarks
from tests.auth_support import TENANT_A

TODAY = dt.date(2026, 10, 12)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Tenant(id=str(TENANT_A), slug="tenant-a", name="Tenant A"))
    session.commit()
    return session


def _company(db, days_late: list[int], tenant: str | None = None) -> str:
    tenant = tenant or str(uuid.uuid4())
    if db.get(Tenant, tenant) is None:
        db.add(Tenant(id=tenant, slug=f"t-{tenant[:8]}", name="SYNTHETIC peer"))
    for n, late in enumerate(days_late):
        due = TODAY - dt.timedelta(days=60 + n)
        db.add(
            EInvoiceRecord(
                tenant_id=tenant,
                supplier_name="SYNTHETIC",
                total_amount=Decimal("1000.00"),
                status="validated",
                due_date=due,
                paid_at=due + dt.timedelta(days=late),
            )
        )
    db.commit()
    return tenant


def test_fewer_than_five_companies_release_nothing(db):
    _company(db, [10, 10], str(TENANT_A))
    for late in (5, 15, 20):
        _company(db, [late])

    report = benchmarks.report(db, str(TENANT_A), TODAY)
    metric = report.metrics[0]
    assert report.status == "not_enough_companies"
    assert metric.peer_value is None
    assert metric.your_value == 10


def test_enough_companies_release_a_noisy_average_that_stays_fixed_for_the_day(db):
    _company(db, [10, 10], str(TENANT_A))
    for late in (5, 15, 20, 25, 30):
        _company(db, [late])

    first = benchmarks.report(db, str(TENANT_A), TODAY)
    again = benchmarks.report(db, str(TENANT_A), TODAY)
    assert first.status == "measured" and first.epsilon == 1.0
    assert first.metrics[0].peer_value == again.metrics[0].peer_value
    # The true average of the six companies is 17.5 days; clipped to 0-90.
    assert 0 <= first.metrics[0].peer_value <= 90
    # The noise scale is published: sensitivity (90 / 6 companies) / epsilon.
    assert first.metrics[0].noise_scale == pytest.approx(15.0)


def test_the_noise_is_laplace_with_the_published_scale():
    draws = [benchmarks.laplace(1.0, f"seed-{n}") for n in range(4000)]
    mean_abs = sum(abs(x) for x in draws) / len(draws)
    # For Laplace(0, b) the mean absolute value is b.
    assert 0.9 < mean_abs < 1.1
    assert abs(sum(draws) / len(draws)) < 0.1


def test_a_company_without_paid_invoices_is_not_counted(db):
    _company(db, [], str(TENANT_A))
    for late in (5, 15, 20, 25):
        _company(db, [late])

    report = benchmarks.report(db, str(TENANT_A), TODAY)
    assert report.status == "not_enough_companies"
    assert report.metrics[0].your_value is None


def test_a_changed_cohort_gets_fresh_noise_so_differences_reveal_nothing(db, monkeypatch):
    seeds = []
    real = benchmarks.laplace

    def recording(scale, seed):
        seeds.append(seed)
        return real(scale, seed)

    monkeypatch.setattr(benchmarks, "laplace", recording)
    _company(db, [10, 10], str(TENANT_A))
    for late in (5, 15, 20, 25):
        _company(db, [late])
    benchmarks.report(db, str(TENANT_A), TODAY)
    benchmarks.report(db, str(TENANT_A), TODAY)  # same data: same noise
    _company(db, [30])  # a company joins the same day
    benchmarks.report(db, str(TENANT_A), TODAY)

    assert seeds[0] == seeds[1]
    assert seeds[2] != seeds[0]
