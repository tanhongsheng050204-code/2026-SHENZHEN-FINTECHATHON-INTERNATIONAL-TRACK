"""Opt-in PostgreSQL integration checks against a disposable migrated database.

FINBRAIN_REVIEW_POSTGRES_URL must point at the local review database. Provider
authentication is covered separately with mocks; this exercises real database RLS.
"""

import os
from dataclasses import replace
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.contracts.customization import ImportMappingRequest
from app.db import set_rls_context
from app.models import AuthUserRole, BankTransaction, PayrollLine, Tenant, TokenVaultEntry
from app.schemas import UserRole
from app.security.keyring import ensure_active_key
from app.services.business_imports import commit_import
from app.services.import_mappings import save
from app.services.tenant_settings import initialize_settings
from seed.topic_e import datasets
from tests.auth_support import principal

DSN = os.environ.get("FINBRAIN_REVIEW_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="requires disposable migrated PostgreSQL")


def test_imports_and_tenant_isolation_under_application_rls():
    engine = create_engine(DSN)
    owner = replace(principal(UserRole.OWNER_DIRECTOR), user_id=uuid4(), tenant_id=uuid4())
    other_tenant = str(uuid4())
    tenant_id = str(owner.tenant_id)
    with Session(engine, expire_on_commit=False) as db:
        try:
            db.execute(text("insert into auth.users(id) values (:id)"), {"id": str(owner.user_id)})
            for tid in (tenant_id, other_tenant):
                db.add(Tenant(id=tid, name="SYNTHETIC PostgreSQL review", slug=f"review-{tid}"))
            db.flush()
            initialize_settings(db, tenant_id, "SYNTHETIC PostgreSQL review")
            ensure_active_key(db)
            set_rls_context(
                db,
                user_id=str(owner.user_id),
                user_role=owner.role.value,
                tenant_id=tenant_id,
                actor_ref=owner.actor_ref,
            )
            db.add(
                AuthUserRole(
                    user_id=str(owner.user_id),
                    tenant_id=tenant_id,
                    user_role="owner_director",
                    job_functions=["owner"],
                    active=True,
                )
            )
            db.flush()
            with pytest.raises(DBAPIError, match="last_owner_required"):
                with db.begin_nested():
                    db.execute(
                        text("update user_roles set active=false where tenant_id=:tid"),
                        {"tid": tenant_id},
                    )
            with pytest.raises(DBAPIError, match="security_may_only_tighten"):
                with db.begin_nested():
                    db.execute(
                        text("""update tenant_settings set version=version+1,
                        document=jsonb_set(document, '{security,session_idle_minutes}', '999')
                        where tenant_id=:tid"""),
                        {"tid": tenant_id},
                    )
            for schema, (headers, columns, csv_text) in datasets(date(2026, 10, 9)).items():
                mapping = save(
                    db,
                    owner,
                    ImportMappingRequest(
                        schema_name=schema,
                        name="Synthetic mapping",
                        headers=headers,
                        column_map=columns,
                    ),
                    commit=False,
                )
                result = commit_import(db, owner, schema, csv_text, mapping.id, commit=False)
                assert result.imported_rows > 0
            assert db.scalars(select(PayrollLine)).all()
            set_rls_context(
                db,
                user_id=str(owner.user_id),
                user_role="finance_ops",
                tenant_id=tenant_id,
                actor_ref=owner.actor_ref,
            )
            assert not db.scalars(select(PayrollLine)).all()
            assert not db.scalars(
                select(TokenVaultEntry).where(TokenVaultEntry.data_class == "employee_personal")
            ).all()
            set_rls_context(
                db,
                user_id=str(owner.user_id),
                user_role=owner.role.value,
                tenant_id=other_tenant,
                actor_ref=owner.actor_ref,
            )
            assert not db.scalars(select(BankTransaction)).all()
            assert not db.scalars(select(PayrollLine)).all()
        finally:
            db.rollback()
    engine.dispose()
