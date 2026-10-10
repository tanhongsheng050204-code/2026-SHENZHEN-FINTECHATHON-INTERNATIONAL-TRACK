"""Passport sharing under real PostgreSQL row-level security (known risk 5).

Runs only against a disposable migrated database (FINBRAIN_REVIEW_POSTGRES_URL),
like tests/test_plan23_postgres.py.
"""

import os
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.contracts.passports import GrantRequest
from app.db import set_rls_context
from app.models import AuthUserRole, Tenant
from app.schemas import UserRole
from app.security.keyring import ensure_active_key
from app.services import external_grants, passports
from app.services.tenant_settings import initialize_settings
from tests.auth_support import principal

DSN = os.environ.get("FINBRAIN_REVIEW_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="requires disposable migrated PostgreSQL")


def _owner():
    return replace(principal(UserRole.OWNER_DIRECTOR), user_id=uuid4(), tenant_id=uuid4())


def _as(db, person):
    set_rls_context(
        db,
        user_id=str(person.user_id),
        user_role=person.role.value,
        tenant_id=str(person.tenant_id),
        actor_ref=person.actor_ref,
    )


def test_passport_sharing_is_tenant_scoped_under_rls():
    engine = create_engine(DSN)
    owner_a, owner_b = _owner(), _owner()
    with Session(engine, expire_on_commit=False) as db:
        for person in (owner_a, owner_b):
            tid = str(person.tenant_id)
            db.execute(text("insert into auth.users(id) values (:id)"), {"id": str(person.user_id)})
            db.add(Tenant(id=tid, name="SYNTHETIC passport review", slug=f"review-{tid}"))
            db.flush()
            initialize_settings(db, tid, "SYNTHETIC passport review")
            db.add(
                AuthUserRole(
                    user_id=str(person.user_id),
                    tenant_id=tid,
                    user_role="owner_director",
                    job_functions=["owner"],
                    active=True,
                )
            )
        ensure_active_key(db)
        db.commit()

        # Owner A issues a Passport and a lender link as the restricted app role.
        _as(db, owner_a)
        passport = passports.issue(db, owner_a)
        grant = external_grants.create(
            db,
            owner_a,
            "lender",
            passport.id,
            GrantRequest(grantee_email="lender@bank.example", expires_in_days=7),
        )
        token = grant.share_path.rsplit("/", 1)[1]

        # Owner B asking for A's records by A's own ids sees nothing.
        _as(db, owner_b)
        assert passports.list_for(db, str(owner_a.tenant_id)) == []
        assert external_grants.list_for(db, str(owner_a.tenant_id), "lender", passport.id) == []
        db.commit()

    # A lender opens the link with no session; the view runs scoped to A only.
    with Session(engine, expire_on_commit=False) as public:
        opened = external_grants.open_link(public, "lender", token)
        assert opened.tenant_id == str(owner_a.tenant_id)
        role = public.execute(text("select current_user")).scalar()
        assert role == "finbrain_worker"
        assert passports.list_for(public, str(owner_b.tenant_id)) == []
        assert passports._issued(public, tenant_id=opened.tenant_id, passport_id=passport.id)
        public.commit()

    with Session(engine, expire_on_commit=False) as public:
        tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
        with pytest.raises(LookupError):
            external_grants.open_link(public, "lender", tampered)

    with Session(engine, expire_on_commit=False) as db:
        _as(db, owner_a)
        external_grants.revoke(db, owner_a, "lender", passport.id, grant.id)
    with Session(engine, expire_on_commit=False) as public:
        with pytest.raises(external_grants.GrantClosed):
            external_grants.open_link(public, "lender", token)
    engine.dispose()
