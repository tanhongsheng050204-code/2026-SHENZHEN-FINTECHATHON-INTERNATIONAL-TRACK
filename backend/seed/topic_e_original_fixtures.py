"""Give the synthetic Topic E tenant the original pages' demo fixtures.

seed/topic_e.py builds a dedicated synthetic tenant (bank, payables, payroll, pipeline)
for the cash-flow, financing and position pages. The original pages (e-Invoicing,
Data sources, Ask DuitDuit) read e-invoices and protected email/Telegram records,
which seed/seed_data.py only puts in the default tenant. Running this after
topic_e.py adds the same fixtures to the synthetic tenant, so one company tells
the whole story. Non-destructive and idempotent; refuses any non-synthetic tenant.

Two adjustments keep that one story consistent:
- The fixture bills are dated August, before the cash story's seed date. The opening
  bank balance on that date already reflects them, so unpaid ones are recorded as
  paid on their due date instead of showing as overdue next to the cash forecast.
- The synthetic company declares a registration date (as an owner would in Company
  settings), which is the source of months trading for financing.
- It also saves three alert rules an owner would set: low projected cash, stock below
  reorder level and a large overdue balance per customer.
"""

import argparse
import datetime as dt

from sqlalchemy import select

from app.db import SessionLocal, initialize_local_schema
from app.models import (
    SyntheticTenantSeed,
    Tenant,
    TenantSettingsRecord,
    TenantSettingsVersion,
    TokenizedContent,
)
from app.services.ingestion import ingest_canonical_record
from seed.sample_records import SAMPLE_RECORDS
from seed.seed_data import EINVOICE_SEED_RECORDS, adapt_seed_record, seed_einvoice_records

SYNTHETIC_SLUG_PREFIX = "synthetic-"
ORIGINAL_BUYER = "FINBRAIN Sdn Bhd"
SYNTHETIC_REGISTERED_ON = dt.date(2023, 8, 1)


def _synthetic_tenant(db, tenant_id: str) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or not tenant.slug.startswith(SYNTHETIC_SLUG_PREFIX):
        raise ValueError("not_a_synthetic_tenant")
    return tenant


def _scoped(tenant_id: str, source_record_id: str) -> str:
    # Source record ids are unique across tenants; prefix keeps the default copy intact.
    return f"t{tenant_id.replace('-', '')[:12]}:{source_record_id}"


def _declare_registration(db, tenant_id: str) -> None:
    row = db.get(TenantSettingsRecord, tenant_id)
    if row is None or row.document.get("profile", {}).get("registered_on"):
        return
    document = dict(row.document)
    document["profile"] = {
        **document["profile"],
        "registered_on": SYNTHETIC_REGISTERED_ON.isoformat(),
    }
    row.version += 1
    row.document = document
    db.add(TenantSettingsVersion(tenant_id=tenant_id, version=row.version, document=document))
    db.commit()


_DEMO_RULES = (
    ("projected_balance", "below", "50000", ["owner", "finance"], "in_app"),
    ("stock_below_reorder", "above", "0", ["procurement", "owner"], "in_app"),
    ("overdue_amount_per_customer", "above", "20000", ["finance", "owner"], "email"),
)


def _demo_alert_rules(db, tenant_id: str) -> bool:
    """Save the rules as the company's owner; False when it has no owner yet.

    A rule records who created it, and that must be a real signed-up user, so the
    rules wait until an owner account is attached (run this script again then).
    """
    from decimal import Decimal
    from uuid import UUID

    from app.auth.principal import AuthPrincipal
    from app.contracts.customization import AlertRuleRequest
    from app.models import AuthUserRole, TenantCustomization
    from app.schemas import UserRole
    from app.services.customization import create_rule

    exists = db.scalar(
        select(TenantCustomization.id).where(
            TenantCustomization.tenant_id == tenant_id,
            TenantCustomization.kind == "alert_rule",
        )
    )
    if exists is not None:
        return True
    owner_id = db.scalar(
        select(AuthUserRole.user_id)
        .where(
            AuthUserRole.tenant_id == tenant_id,
            AuthUserRole.user_role == UserRole.OWNER_DIRECTOR.value,
            AuthUserRole.active.is_(True),
        )
        .order_by(AuthUserRole.created_at)
        .limit(1)
    )
    if owner_id is None:
        return False
    owner = AuthPrincipal(
        user_id=UUID(str(owner_id)),
        email=None,
        role=UserRole.OWNER_DIRECTOR,
        tenant_id=UUID(tenant_id),
    )
    for metric, operator, threshold, recipients, channel in _DEMO_RULES:
        create_rule(
            db,
            owner,
            AlertRuleRequest(
                metric=metric,
                operator=operator,
                threshold=Decimal(threshold),
                recipients=recipients,
                channel=channel,
            ),
        )
    return True


# Sample items the review inbox shows for the demo story; the reminder send waits on
# the drafts being approved, so it is not seeded.
_NOT_SEEDED = {"act_send_reminders"}


def _demo_inbox(db, tenant_id: str) -> None:
    """Give the demo company the same open review items the sample inbox shows.

    Each becomes a real proposal on the company's chain, so it can be approved,
    edited, rejected and commented on. propose() skips an item that is already open,
    and the daily demo reset reopens decided ones, so running this again adds nothing.
    """
    from app.services import review_inbox
    from app.stubs.inbox import _INBOX

    for action in _INBOX:
        if action.id in _NOT_SEEDED:
            continue
        review_inbox.propose(
            db,
            tenant_id,
            agent_id=action.agent_id,
            reviewer=action.reviewer_job_function,
            title=action.title,
            summary=action.summary,
            amount=action.amount,
            evidence=action.evidence,
            draft=action.draft,
            level=action.autonomy_level,
        )


def seed_original_fixtures(db, tenant_id: str) -> bool:
    """Seed the fixtures; False when the alert rules still wait for an owner."""
    tenant = _synthetic_tenant(db, str(tenant_id))
    tenant_id = str(tenant.id)
    marker = db.get(SyntheticTenantSeed, tenant_id)

    invoices = []
    for fields in EINVOICE_SEED_RECORDS:
        record = dict(fields, tenant_id=tenant_id)
        if record.get("buyer_name") == ORIGINAL_BUYER:
            record["buyer_name"] = tenant.name
        due = record.get("due_date")
        if marker is not None and record.get("paid_at") is None and due and due < marker.as_of:
            record["paid_at"] = due
        invoices.append(record)
    seed_einvoice_records(db, invoices)
    _declare_registration(db, tenant_id)
    rules_saved = _demo_alert_rules(db, tenant_id)

    for record in SAMPLE_RECORDS:
        canonical = adapt_seed_record(record).model_copy(
            update={
                "tenant_id": tenant_id,
                "source_record_id": _scoped(tenant_id, record["source_record_id"]),
            }
        )
        exists = db.scalar(
            select(TokenizedContent.id).where(
                TokenizedContent.source_record_id == canonical.source_record_id
            )
        )
        if exists is None:
            ingest_canonical_record(db, canonical)
    _demo_inbox(db, tenant_id)
    return rules_saved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tenant-id", required=True, help="Tenant id printed by seed/topic_e.py")
    args = parser.parse_args()
    initialize_local_schema()
    # Runs on the operator's provisioning connection, like seed.seed_data: the
    # restricted worker role may not write e-invoices or protected content, and
    # seed_original_fixtures itself refuses any tenant that is not synthetic.
    with SessionLocal() as db:
        rules_saved = seed_original_fixtures(db, args.tenant_id)
    print(f"original fixtures ready in synthetic tenant {args.tenant_id}")
    if not rules_saved:
        print("alert rules skipped: attach an owner account, then run this again")


if __name__ == "__main__":
    main()
