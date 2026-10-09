import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.contracts.common import DataMode, JobFunction
from app.schemas import UserRole
from app.services import agent_runtime, cash_basis, cashflow_engine, financing_profile
from app.services.cashflow_engine import CashBasis, Signal
from app.stubs import financing
from tests.auth_support import principal

AS_OF = dt.date(2026, 10, 9)
PLAN3 = cash_basis._plan3_deployed()
needs_plan3 = pytest.mark.skipif(not PLAN3, reason="Plan 3 business tables not deployed")


def test_uncertain_pipeline_counts_by_probability():
    basis = CashBasis(
        DataMode.LIVE,
        Decimal("100.00"),
        Decimal("0.00"),
        (
            Signal(
                "ORDER",
                "sales",
                JobFunction.SALES,
                "inflow",
                "Order",
                Decimal("10"),
                1,
                1,
                None,
                0.7,
            ),
            Signal(
                "QUOTE",
                "sales",
                JobFunction.SALES,
                "inflow",
                "Quote",
                Decimal("5"),
                1,
                None,
                None,
                0.3,
            ),
        ),
    )

    point = cashflow_engine.build_forecast(basis, horizon_days=30, as_of=AS_OF).points[1]

    assert (point.best, point.likely, point.worst) == (
        Decimal("115"),
        Decimal("110"),
        Decimal("100"),
    )


def test_a_fact_with_no_source_fails_its_rule_as_not_on_record():
    profile = financing.Profile(DataMode.LIVE, {"validated_einvoice_share": Decimal("0.9")})

    found = financing.matches("MY", profile)

    assert found.data_mode == "live"
    rules = {r.rule: r for m in found.matches for r in m.rules}
    assert rules["months_trading_min"].passed is False
    assert "not on record" in rules["months_trading_min"].detail
    assert rules["einvoice_share_min"].passed is True


@pytest.mark.skipif(PLAN3, reason="only meaningful before Plan 3 is deployed")
def test_no_live_basis_without_plan3_tables():
    assert cash_basis.load(None, "tenant", AS_OF) is None


# --- Live basis over Plan 3 records: the synthetic importer's day-23 story. ---

TENANT = "858f0c1c-42fa-52a2-91b3-80a19d816356"


def _day(offset: int) -> dt.date:
    return AS_OF + dt.timedelta(days=offset)


def _imported(model, n: int, **fields):
    return model(
        tenant_id=TENANT,
        source_record_id=f"src-{model.__name__}-{n}",
        record_hash="0" * 64,
        batch_id="batch",
        **fields,
    )


def _synthetic_tenant() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.Base.metadata.create_all(engine)
    db = Session(engine)
    m = models
    db.add(m.Tenant(id=TENANT, slug="synthetic-topic-e-v1-2026-10-09", name="SYNTHETIC importer"))
    db.add(
        _imported(
            m.BankTransaction,
            1,
            posted_on=AS_OF,
            description_token="TOK",
            direction="credit",
            amount=Decimal("116400.00"),
            balance=Decimal("116400.00"),
        )
    )
    for n, (amount, offset) in enumerate(
        [("14800.00", 6), ("14800.00", 36), ("48300.00", 58), ("14800.00", 66)]
    ):
        db.add(
            _imported(
                m.Payable,
                n,
                supplier_id=1,
                bill_no=f"B{n}",
                amount=Decimal(amount),
                currency="MYR",
                fx_rate=Decimal("1"),
                amount_myr=Decimal(amount),
                due_date=_day(offset),
                status="open",
            )
        )
    for n, (cny, myr, offset) in enumerate(
        [("98000.00", "61740.00", 23), ("60000.00", "37800.00", 75)]
    ):
        db.add(
            _imported(
                m.PurchaseOrder,
                n,
                supplier_id=2,
                po_no=f"P{n}",
                amount=Decimal(cny),
                currency="CNY",
                fx_rate=Decimal("0.63"),
                amount_myr=Decimal(myr),
                expected_delivery=_day(offset + 5),
                expected_payment=_day(offset),
                status="open",
            )
        )
    for n, offset in enumerate((23, 53, 83)):
        db.add(
            m.PayrollRun(
                tenant_id=TENANT,
                batch_id="batch",
                period=f"2026-{10 + n:02}"[:7],
                pay_date=_day(offset),
                total_gross=Decimal("50000.00"),
                employer_contributions=Decimal("12000.00"),
                status="approved",
            )
        )
    receipts = [
        (1, "24500.00", 11),
        (2, "18200.00", 21),
        (3, "31000.00", 30),
        (1, "42000.00", 38),
        (4, "38500.00", 43),
        (2, "27600.00", 54),
        (5, "44200.00", 61),
        (3, "35400.00", 70),
        (1, "52300.00", 80),
        (6, "39800.00", 87),
    ]
    for n, (customer, amount, offset) in enumerate(receipts):
        db.add(
            _imported(
                m.SalesPipeline,
                n,
                customer_id=customer,
                customer_token=f"CUST_TOKEN_{customer}",
                stage="invoiced",
                amount=Decimal(amount),
                expected_payment_date=_day(offset),
                probability=Decimal("1.00"),
            )
        )
    db.add(
        _imported(
            m.SalesPipeline,
            99,
            customer_id=7,
            customer_token="CUST_TOKEN_7",
            stage="order",
            amount=Decimal("26000.00"),
            expected_payment_date=_day(60),
            probability=Decimal("0.70"),
        )
    )
    db.add(
        _imported(
            m.MarketplacePayout,
            1,
            platform="TOK",
            payout_date=_day(26),
            gross=Decimal("10000.00"),
            fees=Decimal("600.00"),
            net=Decimal("9400.00"),
            status="expected",
        )
    )
    db.add(
        _imported(
            m.MarketingSpend,
            1,
            channel="TOK",
            campaign_label="TOK",
            spend=Decimal("5500.00"),
            period_start=_day(40),
            period_end=_day(46),
        )
    )
    db.commit()
    return db


@needs_plan3
def test_live_forecast_reconciles_the_importers_day_23_shortfall():
    db = _synthetic_tenant()

    basis = cash_basis.load(db, TENANT, AS_OF)
    forecast = cashflow_engine.build_forecast(basis, horizon_days=90, as_of=AS_OF)

    assert forecast.data_mode == "live"
    assert forecast.opening_balance == Decimal("116400.00")
    assert forecast.shortfall.day == 23
    assert forecast.shortfall.likely_balance == Decimal("20560.00")
    assert forecast.shortfall.gap == Decimal("29440.00")
    order = next(s for s in forecast.drivers if s.source_agent == "sales")
    assert (order.likely_day, order.worst_day) == (60, None)
    assert not any("CUST_TOKEN" in s.label for s in forecast.drivers)


@needs_plan3
def test_live_profile_is_computed_from_the_tenants_records():
    db = _synthetic_tenant()
    forecast = cashflow_engine.build_forecast(
        cash_basis.load(db, TENANT, AS_OF), horizon_days=90, as_of=AS_OF
    )

    values = financing_profile.compute(db, TENANT, forecast).values

    assert values["projected_shortfall_gap"] == Decimal("29440.00")
    assert values["import_payables_share"] == Decimal("0.52")
    assert values["top_customer_share"] == Decimal("0.31")
    assert values["receivables_over_90_share"] == Decimal("0.00")
    assert "months_trading" not in values


@needs_plan3
def test_live_agent_run_asks_for_early_payment_and_saves_proposals_once(monkeypatch):
    db = _synthetic_tenant()
    monkeypatch.setattr(agent_runtime, "_external_guard", lambda *a, **k: None)
    monkeypatch.setattr(
        agent_runtime.dt, "date", type("D", (dt.date,), {"today": staticmethod(lambda: AS_OF)})
    )
    owner = principal(UserRole.OWNER_DIRECTOR, tenant_id=__import__("uuid").UUID(TENANT))

    run = agent_runtime.start_run(db, owner, "Can I cover payroll this month?")
    events = agent_runtime.run_events(db, owner, run.run_id)

    proposals = {e.agent_id: e for e in events if e.type == "proposal_created"}
    assert "day 23" in proposals["cashflow"].message
    assert (
        "the invoice expected 08 Nov (RM31,000.00): asking for it before day 23 closes the gap"
        in (proposals["receivables"].message)
    )
    assert proposals["financing"].message.startswith("Nothing qualifies yet. Closest: ")
    # Decidable proposals are saved to the review inbox; "nothing qualifies" is advice.
    assert proposals["cashflow"].action_id.startswith("act_")
    assert proposals["receivables"].action_id.startswith("act_")
    assert proposals["financing"].action_id is None
    assert "2 items await your review" in events[-2].message

    again = agent_runtime.run_events(db, owner, run.run_id)
    assert {e.action_id for e in again if e.action_id} == {
        proposals["cashflow"].action_id,
        proposals["receivables"].action_id,
    }


@needs_plan3
def test_live_scorecard_scores_the_same_facts_the_financing_rules_read():
    db = _synthetic_tenant()
    forecast = cashflow_engine.build_forecast(
        cash_basis.load(db, TENANT, AS_OF), horizon_days=90, as_of=AS_OF
    )
    profile = financing_profile.compute(db, TENANT, forecast)

    card = financing.scorecard(profile, shortfall_day=forecast.shortfall.day, public=True)
    factors = {f.key: f for f in card.factors}

    assert card.data_mode == "live"
    assert (factors["cash_runway"].value, factors["cash_runway"].points) == (
        "Shortfall on day 23",
        20,
    )
    assert (factors["top_customer_share"].value, factors["top_customer_share"].points) == (
        "31%",
        45,
    )
    # No source yet: zero points, said plainly, never the demo value.
    assert (factors["months_trading"].value, factors["months_trading"].points) == (
        "Not on record",
        0,
    )
    assert (
        factors["bank_lines_matched_share"].value,
        factors["bank_lines_matched_share"].points,
    ) == ("Not measured", 0)
    assert card.score == card.base_points + sum(f.points for f in card.factors)


def test_live_scorecard_without_public_signals_scores_them_zero():
    profile = financing.Profile(DataMode.LIVE, {})

    card = financing.scorecard(profile, shortfall_day=None, public=False)
    reputation = next(f for f in card.factors if f.key == "public_reputation")

    assert (reputation.value, reputation.points) == ("Not connected", 0)
    assert card.public_signals == []
    assert next(f for f in card.factors if f.key == "cash_runway").points == 80


@needs_plan3
def test_months_trading_comes_from_the_declared_registration_date():
    from app.services.settings_catalog import default_settings

    db = _synthetic_tenant()
    settings = default_settings("SYNTHETIC importer")
    settings.profile.registered_on = dt.date(2023, 8, 1)
    document = settings.model_dump(mode="json")
    db.add(models.TenantSettingsRecord(tenant_id=TENANT, version=1, document=document))
    db.commit()
    forecast = cashflow_engine.build_forecast(
        cash_basis.load(db, TENANT, AS_OF), horizon_days=90, as_of=AS_OF
    )

    values = financing_profile.compute(db, TENANT, forecast).values

    assert values["months_trading"] == Decimal("38")


@needs_plan3
def test_chase_with_nobody_late_drafts_requests_for_invoices_due_before_the_gap(monkeypatch):
    from app.services import playbooks

    db = _synthetic_tenant()
    def on_seed_date(db, principal, *, horizon=90):
        basis = cash_basis.load(db, TENANT, AS_OF)
        return basis, cashflow_engine.build_forecast(basis, horizon_days=horizon, as_of=AS_OF)

    monkeypatch.setattr(playbooks, "_forecast", on_seed_date)
    owner = principal(UserRole.OWNER_DIRECTOR, tenant_id=__import__("uuid").UUID(TENANT))

    steps, ids, _, _ = playbooks._chase_late_payers(db, owner)

    # Nothing is past due on the seed date; invoices due by day 23 are the ones
    # worth asking about, one request per customer, each waiting for review.
    assert "No invoice is past due" in steps[0].text
    assert "due before the cash gap on day 23" in steps[0].text
    assert len(ids) == 2
