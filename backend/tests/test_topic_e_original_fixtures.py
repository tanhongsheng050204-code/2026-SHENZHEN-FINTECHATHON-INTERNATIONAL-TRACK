import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models import DEFAULT_TENANT_ID, Base, EInvoiceRecord, Tenant, TokenizedContent
from seed.sample_records import SAMPLE_RECORDS
from seed.seed_data import EINVOICE_SEED_RECORDS
from seed.topic_e_original_fixtures import seed_original_fixtures

SYNTHETIC_ID = "7d0c3f0e-1111-5222-8333-000000000e01"
SYNTHETIC_NAME = "SYNTHETIC Malaysian Home Goods Importer"


def _db() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(Tenant(id=DEFAULT_TENANT_ID, slug="default", name="Default"))
    db.add(Tenant(id=SYNTHETIC_ID, slug="synthetic-topic-e-v1-2026-10-08", name=SYNTHETIC_NAME))
    db.commit()
    return db


def _count(db, model, tenant_id):
    return db.scalar(select(func.count()).select_from(model).where(model.tenant_id == tenant_id))


def test_original_fixtures_land_in_the_synthetic_tenant_as_one_company():
    db = _db()

    seed_original_fixtures(db, SYNTHETIC_ID)

    invoices = db.scalars(
        select(EInvoiceRecord).where(EInvoiceRecord.tenant_id == SYNTHETIC_ID)
    ).all()
    assert len(invoices) == len(EINVOICE_SEED_RECORDS)
    assert "FINBRAIN Sdn Bhd" not in {i.buyer_name for i in invoices}
    assert SYNTHETIC_NAME in {i.buyer_name for i in invoices}
    # Fixtures that deliberately omit the buyer keep that flaw for the readiness demo.
    assert any(i.buyer_name is None for i in invoices)

    sources = db.scalars(
        select(TokenizedContent.source_system).where(TokenizedContent.tenant_id == SYNTHETIC_ID)
    ).all()
    assert {"email", "telegram"} <= set(sources)
    assert _count(db, EInvoiceRecord, DEFAULT_TENANT_ID) == 0


def test_seeding_twice_adds_nothing_new():
    db = _db()
    seed_original_fixtures(db, SYNTHETIC_ID)
    invoices = _count(db, EInvoiceRecord, SYNTHETIC_ID)
    content = _count(db, TokenizedContent, SYNTHETIC_ID)

    seed_original_fixtures(db, SYNTHETIC_ID)

    assert _count(db, EInvoiceRecord, SYNTHETIC_ID) == invoices
    assert _count(db, TokenizedContent, SYNTHETIC_ID) == content


def test_fixtures_do_not_collide_with_the_default_tenant_copy():
    db = _db()
    record = SAMPLE_RECORDS[0]
    from app.services.ingestion import ingest_canonical_record
    from seed.seed_data import adapt_seed_record

    ingest_canonical_record(db, adapt_seed_record(record))

    seed_original_fixtures(db, SYNTHETIC_ID)

    ids = db.scalars(
        select(TokenizedContent.source_record_id).where(TokenizedContent.tenant_id == SYNTHETIC_ID)
    ).all()
    assert record["source_record_id"] not in ids
    assert any(i.endswith(record["source_record_id"]) for i in ids)


@pytest.mark.parametrize("tenant_id", [DEFAULT_TENANT_ID, "00000000-0000-0000-0000-00000000dead"])
def test_refuses_tenants_that_are_not_synthetic(tenant_id):
    db = _db()

    with pytest.raises(ValueError, match="not_a_synthetic_tenant"):
        seed_original_fixtures(db, tenant_id)

    assert _count(db, EInvoiceRecord, tenant_id) == 0


def _with_seed_marker(db):
    import datetime as dt
    from decimal import Decimal

    from app.models import SyntheticTenantSeed
    from app.services.tenant_settings import initialize_settings

    initialize_settings(db, SYNTHETIC_ID, SYNTHETIC_NAME)
    db.add(
        SyntheticTenantSeed(
            tenant_id=SYNTHETIC_ID,
            version=1,
            as_of=dt.date(2026, 10, 9),
            annual_revenue_myr=Decimal("2600000.00"),
            manifest={"synthetic": True},
        )
    )
    db.commit()


def test_bills_due_before_the_cash_story_starts_are_already_paid():
    import datetime as dt

    db = _db()
    _with_seed_marker(db)

    seed_original_fixtures(db, SYNTHETIC_ID)

    # The opening bank balance on the seed date already reflects these August bills,
    # so none may still look overdue next to the cash forecast.
    unpaid_before = db.scalars(
        select(EInvoiceRecord).where(
            EInvoiceRecord.tenant_id == SYNTHETIC_ID,
            EInvoiceRecord.paid_at.is_(None),
            EInvoiceRecord.due_date < dt.date(2026, 10, 9),
        )
    ).all()
    assert unpaid_before == []


def test_the_synthetic_company_declares_its_registration_date_once():
    from app.models import TenantSettingsRecord, TenantSettingsVersion

    db = _db()
    _with_seed_marker(db)

    seed_original_fixtures(db, SYNTHETIC_ID)
    seed_original_fixtures(db, SYNTHETIC_ID)

    row = db.get(TenantSettingsRecord, SYNTHETIC_ID)
    assert row.document["profile"]["registered_on"] == "2023-08-01"
    assert row.version == 2
    assert _count(db, TenantSettingsVersion, SYNTHETIC_ID) == 2


OWNER_ID = "00000000-0000-4000-8000-0000000000a1"


def _with_owner(db):
    from app.models import AuthUserRole

    db.add(
        AuthUserRole(
            user_id=OWNER_ID,
            tenant_id=SYNTHETIC_ID,
            user_role="owner_director",
            job_functions=["owner"],
            active=True,
        )
    )
    db.commit()


def _rules(db):
    from app.models import TenantCustomization

    return db.scalars(
        select(TenantCustomization).where(
            TenantCustomization.tenant_id == SYNTHETIC_ID,
            TenantCustomization.kind == "alert_rule",
        )
    ).all()


def test_the_synthetic_company_has_three_demo_alert_rules_once():
    db = _db()
    _with_seed_marker(db)
    _with_owner(db)

    assert seed_original_fixtures(db, SYNTHETIC_ID) is True
    assert seed_original_fixtures(db, SYNTHETIC_ID) is True

    rules = _rules(db)
    assert sorted(r.document["metric"] for r in rules) == [
        "overdue_amount_per_customer",
        "projected_balance",
        "stock_below_reorder",
    ]
    # Saved as the company's real owner: the column references a signed-up user.
    assert {str(r.created_by) for r in rules} == {OWNER_ID}


def test_without_an_owner_the_rules_wait_and_the_records_still_arrive():
    # The rules once named a made-up user, which a real database refuses; the seed
    # then stopped before the protected records, leaving Ask DuitDuit empty.
    db = _db()
    _with_seed_marker(db)

    assert seed_original_fixtures(db, SYNTHETIC_ID) is False

    assert _rules(db) == []
    assert _count(db, TokenizedContent, SYNTHETIC_ID) >= len(SAMPLE_RECORDS)


def test_the_demo_company_gets_its_review_inbox_story_once():
    from app.models import WorkflowAuditEntry
    from app.services import review_inbox

    db = _db()
    seed_original_fixtures(db, SYNTHETIC_ID)
    seed_original_fixtures(db, SYNTHETIC_ID)

    items = {i.action.title: i.action for i in review_inbox._replay(db, SYNTHETIC_ID).values()}
    assert "Supplier bank-account change (quarantined)" in items
    assert items["Approve the October payroll run"].autonomy_level.value == "L3"
    assert items["Review 3 reminder drafts"].draft
    proposals = db.scalars(
        select(WorkflowAuditEntry).where(
            WorkflowAuditEntry.tenant_id == SYNTHETIC_ID,
            WorkflowAuditEntry.event_type == "agent_proposal_created",
        )
    ).all()
    assert len(proposals) == len(items)  # the second run added nothing


def test_customer_c_complains_about_inv_1047_and_needs_attention_once():
    from app.contracts.customization import normalize_header
    from app.models import Customer, CustomerRecordLink
    from app.services.business_imports import digest
    from app.services.customer_attention import latest_attention

    db = _db()
    customer = Customer(
        tenant_id=SYNTHETIC_ID,
        normalized_name=digest(SYNTHETIC_ID, "customer", normalize_header("SYNTHETIC Customer C")),
        canonical_name="[ORG_1]",
        primary_name_token="[ORG_1]",
        profile_origin="manual",
    )
    db.add(customer)
    db.commit()

    seed_original_fixtures(db, SYNTHETIC_ID)
    seed_original_fixtures(db, SYNTHETIC_ID)

    links = db.scalars(
        select(CustomerRecordLink).where(CustomerRecordLink.customer_id == customer.id)
    ).all()
    assert len(links) == 2
    assert {link.match_status for link in links} == {"verified"}
    attention = latest_attention(db, SYNTHETIC_ID, customer.id)
    assert attention is not None and attention.priority != "healthy"
