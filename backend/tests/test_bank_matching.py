"""Bank lines matched to the company's own records, for the last completed month."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.contracts.customization import ImportMappingRequest
from app.schemas import UserRole
from app.services import bank_matching, cash_basis
from app.services.business_imports import commit_import
from app.services.import_mappings import save
from seed.topic_e import datasets
from tests.auth_support import principal

pytestmark = pytest.mark.skipif(
    not cash_basis._plan3_deployed(), reason="Plan 3 business tables not deployed"
)
TENANT = "00000000-0000-0000-0000-0000000000b1"
AS_OF = date(2026, 10, 9)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.add(models.Tenant(id=TENANT, slug="synthetic-bank", name="SYNTHETIC bank"))
        session.commit()
        yield session
    engine.dispose()


def _row(model, n, **fields):
    return model(
        tenant_id=TENANT,
        source_record_id=f"{model.__name__}-{n}",
        record_hash=f"{n:064d}",
        batch_id="batch",
        **fields,
    )


def _bank(n, day, direction, amount):
    return _row(
        models.BankTransaction,
        n,
        posted_on=day,
        description_token="TOK",
        direction=direction,
        amount=Decimal(amount),
        balance=None,
    )


def _bill(n, day, amount, status="paid"):
    return _row(
        models.Payable,
        n,
        supplier_id=1,
        bill_no=f"B{n}",
        amount=Decimal(amount),
        currency="MYR",
        fx_rate=Decimal("1"),
        amount_myr=Decimal(amount),
        due_date=day,
        status=status,
    )


def test_last_month_lines_match_paid_records_one_to_one_within_three_days(db):
    db.add_all(
        [
            _bank(1, date(2026, 9, 7), "debit", "14800.00"),
            _bank(2, date(2026, 9, 8), "debit", "14800.00"),  # second bill, none on record
            _bank(3, date(2026, 9, 20), "debit", "500.00"),  # 6 days from its bill
            _bank(4, date(2026, 10, 2), "debit", "999.00"),  # this month: not in scope
            _bill(1, date(2026, 9, 5), "14800.00"),
            _bill(2, date(2026, 9, 14), "500.00"),
            _bill(3, date(2026, 9, 7), "14800.00", status="open"),  # unpaid bills never match
        ]
    )
    db.commit()

    result = bank_matching.match(db, TENANT, AS_OF)

    assert (result.period, result.lines, result.matched) == ("2026-09", 3, 1)
    assert result.share == Decimal("0.33")
    assert [(u.posted_on, u.amount) for u in result.unmatched] == [
        (date(2026, 9, 8), Decimal("14800.00")),
        (date(2026, 9, 20), Decimal("500.00")),
    ]


def test_no_bank_lines_last_month_is_not_measured(db):
    result = bank_matching.match(db, TENANT, AS_OF)

    assert (result.lines, result.share) == (0, None)


def test_the_synthetic_company_matches_four_of_five_september_lines(db):
    owner = principal(UserRole.OWNER_DIRECTOR, tenant_id=__import__("uuid").UUID(TENANT))
    for schema, (headers, columns, text) in datasets(AS_OF).items():
        mapping = save(
            db,
            owner,
            ImportMappingRequest(
                schema_name=schema, name="Synthetic", headers=headers, column_map=columns
            ),
        )
        commit_import(db, owner, schema, text, mapping.id)

    result = bank_matching.match(db, TENANT, AS_OF)

    assert (result.lines, result.matched, result.share) == (5, 4, Decimal("0.80"))
    assert [(u.direction, u.amount) for u in result.unmatched] == [
        ("debit", Decimal("1250.00"))
    ]
    # September's history leaves the October cash story untouched.
    forecast = cash_basis.load(db, TENANT, AS_OF)
    from app.services import cashflow_engine

    shortfall = cashflow_engine.build_forecast(forecast, horizon_days=90, as_of=AS_OF).shortfall
    assert (shortfall.day, shortfall.gap) == (23, Decimal("29440.00"))


def test_matching_feeds_the_scorecard_and_the_month_end_check(db, monkeypatch):
    from app.services import financing_profile, playbooks
    from app.stubs import financing

    db.add_all(
        [
            _bank(1, date(2026, 9, 7), "out", "14800.00"),
            _bank(2, date(2026, 9, 27), "out", "1250.00"),
            _bill(1, date(2026, 9, 7), "14800.00"),
        ]
    )
    db.commit()
    owner = principal(UserRole.OWNER_DIRECTOR, tenant_id=__import__("uuid").UUID(TENANT))
    monkeypatch.setattr(playbooks, "_today", lambda: AS_OF)

    values = financing_profile.compute(
        db, TENANT, type("F", (), {"data_mode": "live", "as_of": AS_OF, "shortfall": None})()
    ).values
    card = financing.scorecard(financing.Profile("live", values), shortfall_day=None)
    steps, *_ = playbooks._month_end(db, owner)
    bank = next(s for s in steps if s.label == "Bank reconciliation")

    assert values["bank_lines_matched_share"] == Decimal("0.50")
    assert next(f for f in card.factors if f.key == "bank_lines_matched_share").value == "50%"
    assert bank.status == "attention"
    assert "September 2026: 1 of 2 bank lines match a record" in bank.text
    assert "RM1,250.00 out on 27 Sep" in bank.text
