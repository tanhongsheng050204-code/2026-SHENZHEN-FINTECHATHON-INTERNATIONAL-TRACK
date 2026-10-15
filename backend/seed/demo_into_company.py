"""Load the synthetic demo story into one existing, empty company, on its owner's request.

For presenting from a real sign-in: the company keeps its name, owner and settings,
and gets the same synthetic records as the demo company (bank, bills, payroll,
pipeline, e-invoices, messages, the review inbox story, rules and automations).

Guards, so real records are never mixed with made-up ones:
- the company name must be typed exactly, so a wrong id cannot be loaded by mistake;
- a company that already has imports, e-invoices or protected records is refused;
- the company is marked synthetic, so every screen labels its figures as demo data.
Running it again adds nothing. Usage, inside the backend container:
    python -m seed.demo_into_company --tenant-id <id> --company-name "<exact name>"
"""

import argparse
import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select

from app.auth.principal import AuthPrincipal
from app.contracts.customization import ImportMappingRequest
from app.db import SessionLocal, initialize_local_schema, set_worker_context
from app.models import (
    DEFAULT_TENANT_ID,
    BusinessImportBatch,
    EInvoiceRecord,
    SyntheticTenantSeed,
    Tenant,
    TokenizedContent,
)
from app.schemas import UserRole
from app.security.keyring import ensure_active_key
from app.services.business_imports import commit_import
from app.services.import_mappings import save
from seed.topic_e import SEED_ACTOR, SEED_VERSION, datasets
from seed.topic_e_original_fixtures import seed_original_fixtures


class DemoLoadError(ValueError):
    pass


def _has_records(db, tenant_id: str) -> bool:
    """Business records only: review comments are kept as protected records too."""
    from app.services.query_filters import REVIEW_COMMENT_SOURCE

    for model in (BusinessImportBatch, EInvoiceRecord, TokenizedContent):
        query = select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
        if model is TokenizedContent:
            query = query.where(TokenizedContent.source_system != REVIEW_COMMENT_SOURCE)
        if db.scalar(query):
            return True
    return False


def load_demo_story(db, tenant_id: str, company_name: str, as_of: dt.date) -> None:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant_id == DEFAULT_TENANT_ID:
        raise DemoLoadError("company_not_found")
    if tenant.name != company_name:
        raise DemoLoadError("company_name_mismatch")
    marker = db.get(SyntheticTenantSeed, tenant_id)
    if marker is None:
        if _has_records(db, tenant_id):
            raise DemoLoadError("company_has_records")
        db.add(
            SyntheticTenantSeed(
                tenant_id=tenant_id,
                version=SEED_VERSION,
                as_of=as_of,
                annual_revenue_myr=Decimal("2600000.00"),
                manifest={
                    "synthetic": True,
                    "seed_version": SEED_VERSION,
                    "loaded_into_existing_company": True,
                },
            )
        )
        db.commit()
    else:
        as_of = marker.as_of

    ensure_active_key(db)
    db.flush()
    set_worker_context(db, tenant_id=tenant_id, actor_ref=f"synthetic-seed:{tenant_id}")
    seeder = AuthPrincipal(
        user_id=SEED_ACTOR,
        email=None,
        role=UserRole.OWNER_DIRECTOR,
        tenant_id=UUID(tenant_id),
        job_functions=("owner",),
        aal="aal2",
    )
    for schema, (headers, column_map, text) in datasets(as_of).items():
        mapping = save(
            db,
            seeder,
            ImportMappingRequest(
                schema_name=schema,
                name=f"SYNTHETIC {schema}"[:60],
                headers=headers,
                column_map=column_map,
            ),
            commit=False,
        )
        commit_import(db, seeder, schema, text, mapping.id, commit=False)
    db.commit()
    # The imports ran as the restricted worker; e-invoices and protected records are
    # written on the provisioning connection, as seed.topic_e_original_fixtures does.
    from sqlalchemy.orm import Session

    with Session(db.get_bind()) as fixtures:
        seed_original_fixtures(fixtures, tenant_id)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--company-name", required=True, help="Exactly as the company is named")
    parser.add_argument("--as-of", type=dt.date.fromisoformat, default=dt.date(2026, 10, 9))
    args = parser.parse_args()
    initialize_local_schema()
    with SessionLocal() as db:
        try:
            load_demo_story(db, args.tenant_id, args.company_name, args.as_of)
        except DemoLoadError as error:
            raise SystemExit(f"Not loaded: {error}") from error
    print(f"Synthetic demo story loaded into {args.company_name}. Its screens say demo data.")


if __name__ == "__main__":
    main()
