"""Give the synthetic Topic E tenant the original pages' demo fixtures.

seed/topic_e.py builds a dedicated synthetic tenant (bank, payables, payroll, pipeline)
for the cash-flow, financing and position pages. The original pages (e-Invoicing,
Data sources, Ask DuitDuit) read e-invoices and protected email/Telegram records,
which seed/seed_data.py only puts in the default tenant. Running this after
topic_e.py adds the same fixtures to the synthetic tenant, so one company tells
the whole story. Non-destructive and idempotent; refuses any non-synthetic tenant.
"""

import argparse

from sqlalchemy import select

from app.db import SessionLocal, initialize_local_schema, set_worker_context
from app.models import Tenant, TokenizedContent
from app.services.ingestion import ingest_canonical_record
from seed.sample_records import SAMPLE_RECORDS
from seed.seed_data import EINVOICE_SEED_RECORDS, adapt_seed_record, seed_einvoice_records

SYNTHETIC_SLUG_PREFIX = "synthetic-"
ORIGINAL_BUYER = "FINBRAIN Sdn Bhd"


def _synthetic_tenant(db, tenant_id: str) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or not tenant.slug.startswith(SYNTHETIC_SLUG_PREFIX):
        raise ValueError("not_a_synthetic_tenant")
    return tenant


def _scoped(tenant_id: str, source_record_id: str) -> str:
    # Source record ids are unique across tenants; prefix keeps the default copy intact.
    return f"t{tenant_id.replace('-', '')[:12]}:{source_record_id}"


def seed_original_fixtures(db, tenant_id: str) -> None:
    tenant = _synthetic_tenant(db, str(tenant_id))
    tenant_id = str(tenant.id)

    invoices = []
    for fields in EINVOICE_SEED_RECORDS:
        record = dict(fields, tenant_id=tenant_id)
        if record.get("buyer_name") == ORIGINAL_BUYER:
            record["buyer_name"] = tenant.name
        invoices.append(record)
    seed_einvoice_records(db, invoices)

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
    with SessionLocal() as db:
        set_worker_context(db, tenant_id=args.tenant_id, actor_ref="synthetic-seed:original")
        seed_original_fixtures(db, args.tenant_id)
    print(f"original fixtures ready in synthetic tenant {args.tenant_id}")


if __name__ == "__main__":
    main()
