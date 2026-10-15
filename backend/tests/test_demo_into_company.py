"""Loading the synthetic demo story into one existing, empty company on request."""

import datetime as dt

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.services import cash_basis
from app.services.tenant_settings import initialize_settings
from seed.demo_into_company import DemoLoadError, load_demo_story

pytestmark = pytest.mark.skipif(
    not cash_basis._plan3_deployed(), reason="Plan 3 business tables not deployed"
)
COMPANY = "eafc5787-8b41-4d65-8303-18ead169b94e"
NAME = "TANHS SDN BHD"
OWNER = "10000000-0000-0000-0000-0000000000aa"


def _db() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(models.Tenant(id=models.DEFAULT_TENANT_ID, slug="default", name="Default"))
    db.add(models.Tenant(id=COMPANY, slug="tanhs-sdn-bhd", name=NAME))
    db.flush()
    initialize_settings(db, COMPANY, NAME)
    db.add(
        models.AuthUserRole(
            user_id=OWNER,
            tenant_id=COMPANY,
            user_role="owner_director",
            job_functions=["owner"],
            active=True,
        )
    )
    db.commit()
    return db


def _count(db, model) -> int:
    return db.scalar(select(func.count()).select_from(model).where(model.tenant_id == COMPANY))


def test_the_story_lands_in_the_named_company_labelled_synthetic_and_only_once():
    db = _db()

    load_demo_story(db, COMPANY, NAME, dt.date(2026, 10, 9))
    batches, invoices = _count(db, models.BusinessImportBatch), _count(db, models.EInvoiceRecord)
    load_demo_story(db, COMPANY, NAME, dt.date(2026, 10, 9))

    marker = db.get(models.SyntheticTenantSeed, COMPANY)
    assert marker is not None and marker.manifest["synthetic"] is True
    assert db.get(models.Tenant, COMPANY).name == NAME
    assert batches > 0 and invoices > 0
    assert _count(db, models.EInvoiceRecord) == invoices
    assert _count(db, models.BankTransaction) > 0


def test_the_company_name_must_match():
    db = _db()
    with pytest.raises(DemoLoadError, match="company_name_mismatch"):
        load_demo_story(db, COMPANY, "TANHS", dt.date(2026, 10, 9))
    assert db.get(models.SyntheticTenantSeed, COMPANY) is None


def test_a_company_with_its_own_records_is_never_mixed_with_demo_data():
    db = _db()
    db.add(
        models.EInvoiceRecord(
            tenant_id=COMPANY,
            supplier_name="Real supplier",
            total_amount="10.00",
            status="review",
        )
    )
    db.commit()
    with pytest.raises(DemoLoadError, match="company_has_records"):
        load_demo_story(db, COMPANY, NAME, dt.date(2026, 10, 9))
    assert db.get(models.SyntheticTenantSeed, COMPANY) is None
