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


def seed_original_fixtures(db, tenant_id: str) -> None:
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tenant-id", required=True, help="Tenant id printed by seed/topic_e.py")
    args = parser.parse_args()
    initialize_local_schema()
    # Runs on the operator's provisioning connection, like seed.seed_data: the
    # restricted worker role may not write e-invoices or protected content, and
    # seed_original_fixtures itself refuses any tenant that is not synthetic.
    with SessionLocal() as db:
        seed_original_fixtures(db, args.tenant_id)
    print(f"original fixtures ready in synthetic tenant {args.tenant_id}")


if __name__ == "__main__":
    main()
