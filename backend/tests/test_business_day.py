"""The synthetic demo company is read on its seed day, so its story does not drift."""

import datetime as dt
from decimal import Decimal
from uuid import UUID

from app import models
from app.contracts.customization import ImportMappingRequest
from app.routes.cashflow import cashflow_forecast
from app.schemas import UserRole
from app.services import business_day, playbooks
from app.services.business_imports import commit_import
from app.services.import_mappings import save
from seed.topic_e import datasets
from tests.auth_support import principal
from tests.test_bank_matching import AS_OF, TENANT, db  # noqa: F401


def _seed(db):  # noqa: F811
    owner = principal(UserRole.OWNER_DIRECTOR, tenant_id=UUID(TENANT))
    for schema, (headers, columns, text) in datasets(AS_OF).items():
        mapping = save(
            db,
            owner,
            ImportMappingRequest(
                schema_name=schema, name="Synthetic", headers=headers, column_map=columns
            ),
        )
        commit_import(db, owner, schema, text, mapping.id)
    return owner


def _mark_synthetic(db):  # noqa: F811
    db.add(
        models.SyntheticTenantSeed(
            tenant_id=TENANT,
            as_of=AS_OF,
            annual_revenue_myr=Decimal("2600000.00"),
            manifest={"synthetic": True},
        )
    )
    db.commit()


def test_a_real_company_is_read_for_today(db):  # noqa: F811
    assert business_day.today(db, TENANT) == dt.date.today()
    assert business_day.today(None, TENANT) == dt.date.today()


def test_the_demo_company_keeps_its_cash_gap_on_day_23_whatever_the_date(db):  # noqa: F811
    owner = _seed(db)
    _mark_synthetic(db)

    assert business_day.today(db, TENANT) == AS_OF
    forecast = cashflow_forecast(horizon_days=90, as_of=None, principal=owner, db=db)
    assert forecast.as_of == AS_OF
    assert (forecast.shortfall.day, forecast.shortfall.gap) == (23, Decimal("29440.00"))
    _, playbook_forecast = playbooks._forecast(db, owner)
    assert playbook_forecast.shortfall.day == 23
