"""Benchmarks across companies with differential privacy: no company's figure can be worked out."""

import datetime as dt
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import Base, Customer, EInvoiceRecord, Tenant
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


def _company(db, days_late: list[int], tenant: str | None = None, *, bills: bool = False) -> str:
    """Paid sales e-invoices to one customer; bills=True records them as the company's own
    supplier bills instead (no customer), which say nothing about how customers pay."""
    tenant = tenant or str(uuid.uuid4())
    if db.get(Tenant, tenant) is None:
        db.add(Tenant(id=tenant, slug=f"t-{tenant[:8]}", name="SYNTHETIC peer"))
    customer = None
    if not bills:
        customer = Customer(tenant_id=tenant, canonical_name="Buyer", normalized_name="buyer")
        db.add(customer)
        db.flush()
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
                buyer_customer_id=customer.id if customer else None,
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


def test_one_release_per_day_whatever_changes_during_the_day(db):
    _company(db, [10, 10], str(TENANT_A))
    for late in (5, 15, 20, 25):
        _company(db, [late])
    first = benchmarks.report(db, str(TENANT_A), TODAY)

    # A company joins and another's figure moves: still the day's one release, so
    # no two answers can be compared to cancel the noise or average it away.
    _company(db, [80])
    _company(db, [90])
    later = benchmarks.report(db, str(TENANT_A), TODAY)
    assert later.metrics[0].peer_value == first.metrics[0].peer_value
    assert later.metrics[0].noise_scale == first.metrics[0].noise_scale

    # The next day is a new release, with the new data.
    tomorrow = benchmarks.report(db, str(TENANT_A), TODAY + dt.timedelta(days=1))
    assert tomorrow.metrics[0].noise_scale == round(90 / 7, 2)


def test_the_release_is_kept_on_the_chain_as_figures_only(db):
    from sqlalchemy import select

    from app.models import WorkflowAuditEntry

    _company(db, [10, 10], str(TENANT_A))
    for late in (5, 15, 20, 25):
        _company(db, [late])
    benchmarks.report(db, str(TENANT_A), TODAY)

    event = db.scalar(
        select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "benchmark_released")
    )
    assert event.resource_id == TODAY.isoformat()
    assert set(event.event_payload) == {"metric", "peer_value", "noise_scale", "epsilon"}


def test_the_company_s_own_paid_bills_are_not_its_customers_paying(db):
    _company(db, [3, 40, 40], str(TENANT_A), bills=True)
    for late in (5, 15, 20, 25, 30):
        _company(db, [late])

    report = benchmarks.report(db, str(TENANT_A), TODAY)
    assert report.metrics[0].your_value is None
