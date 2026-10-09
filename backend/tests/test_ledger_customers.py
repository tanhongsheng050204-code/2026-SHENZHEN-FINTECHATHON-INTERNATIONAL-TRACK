"""Customers imported from the company's own sales ledger read as one story with the cash view."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.contracts.customization import ImportMappingRequest
from app.models import Base, Tenant
from app.routes.customers import _authorized_customer_summary
from app.schemas import UserRole
from app.services import cash_basis
from app.services.business_imports import commit_import
from app.services.customer_intelligence import list_customers
from app.services.import_mappings import save
from seed.topic_e import datasets
from tests.auth_support import principal

pytestmark = pytest.mark.skipif(
    not cash_basis._plan3_deployed(), reason="Plan 3 business tables not deployed"
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def _import_sales(db, owner, as_of):
    db.add(Tenant(id=str(owner.tenant_id), name="SYNTHETIC ledger", slug="synthetic-ledger"))
    db.flush()
    headers, columns, text = datasets(as_of)["sales_pipeline_v1"]
    mapping = save(
        db,
        owner,
        ImportMappingRequest(
            schema_name="sales_pipeline_v1", name="Sales", headers=headers, column_map=columns
        ),
    )
    commit_import(db, owner, "sales_pipeline_v1", text, mapping.id)


def test_ledger_customers_carry_their_open_invoices(db):
    owner = principal(UserRole.OWNER_DIRECTOR)
    as_of = date.today() - timedelta(days=15)
    _import_sales(db, owner, as_of)

    rows = list_customers(db, str(owner.tenant_id))
    totals = sorted(row.outstanding_total for row in rows)

    # Customer A has three invoices: 24,500 + 42,000 + 52,300.
    assert totals[-1] == Decimal("118800.00")
    # A's first invoice was expected on day 11 of a ledger that started 15 days ago.
    assert max(row.overdue_total for row in rows) == Decimal("24500.00")
    assert sum(row.invoice_count for row in rows) == 10


def test_owner_reads_ledger_customer_names_and_each_read_is_recorded(db):
    from sqlalchemy import func, select

    from app.models import AuditLogEntry as AuditLog

    owner = principal(UserRole.OWNER_DIRECTOR)
    _import_sales(db, owner, date.today())
    before = db.scalar(select(func.count()).select_from(AuditLog)) or 0

    names = {
        _authorized_customer_summary(db, owner, row).name
        for row in list_customers(db, str(owner.tenant_id))
    }

    assert "SYNTHETIC Customer A" in names
    assert (db.scalar(select(func.count()).select_from(AuditLog)) or 0) > before
