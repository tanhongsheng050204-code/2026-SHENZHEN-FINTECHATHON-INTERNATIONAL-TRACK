"""Sign-in activity under real PostgreSQL row-level security.

A sign-in is recorded before the person has a request identity, so the earlier
sign-ins are read on a worker session. Each person then sees only their own
sign-ins, and the owner sees the new-device warning in the security feed. Runs only
against a disposable migrated database, like tests/test_team_postgres.py.
"""

import os
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.db import set_rls_context
from app.models import AuthUserRole, Tenant, WorkflowAuditEntry
from app.schemas import UserRole
from app.services import security_activity
from app.services.tenant_settings import initialize_settings
from tests.auth_support import principal

DSN = os.environ.get("FINBRAIN_REVIEW_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="requires disposable migrated PostgreSQL")

CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0 Safari/537.36"
LAPTOP, PHONE = "L" * 32, "P" * 32


def _as(db, person):
    db.commit()
    set_rls_context(
        db,
        user_id=str(person.user_id),
        user_role=person.role.value,
        tenant_id=str(person.tenant_id),
        actor_ref=person.actor_ref,
    )


def _sign_in(db, person, device):
    row = SimpleNamespace(user_id=str(person.user_id), tenant_id=str(person.tenant_id))
    request = SimpleNamespace(
        headers={"user-agent": CHROME, "x-forwarded-for": "203.0.113.7"},
        client=SimpleNamespace(host="203.0.113.7"),
        cookies={security_activity.DEVICE_COOKIE: device},
    )
    new_device = security_activity.record_sign_in(db, row, request, None, method="password")
    db.commit()
    return new_device


def test_sign_ins_and_new_device_warnings_under_row_level_security():
    engine = create_engine(DSN)
    tenant = uuid4()
    owner = replace(principal(UserRole.OWNER_DIRECTOR), user_id=uuid4(), tenant_id=tenant)
    finance = replace(principal(UserRole.FINANCE_OPS), user_id=uuid4(), tenant_id=tenant)
    tid = str(tenant)
    with Session(engine, expire_on_commit=False) as db:
        db.add(Tenant(id=tid, name="SYNTHETIC sign-in review", slug=f"review-{tid}"))
        db.flush()
        initialize_settings(db, tid, "SYNTHETIC sign-in review")
        for person in (owner, finance):
            db.execute(text("insert into auth.users(id) values (:id)"), {"id": str(person.user_id)})
            db.add(
                AuthUserRole(
                    user_id=str(person.user_id),
                    tenant_id=tid,
                    user_role=person.role.value,
                    job_functions=list(person.job_functions),
                    active=True,
                )
            )
        db.commit()

        # Sign-ins are recorded before the request has an identity.
        assert _sign_in(db, finance, LAPTOP) is False
        assert _sign_in(db, finance, LAPTOP) is False
        assert _sign_in(db, finance, PHONE) is True
        assert _sign_in(db, owner, LAPTOP) is False

        payloads = [
            row.event_payload
            for row in db.scalars(
                select(WorkflowAuditEntry).where(
                    WorkflowAuditEntry.tenant_id == tid,
                    WorkflowAuditEntry.event_type.in_(security_activity.SIGN_INS),
                )
            )
        ]
        assert len(payloads) == 4
        assert all("203.0.113.7" not in str(p) and "Mozilla" not in str(p) for p in payloads)

        # Finance sees only their own sign-ins; the owner sees only theirs.
        _as(db, finance)
        mine = security_activity.sign_ins(db, tid, str(finance.user_id))
        assert len(mine) == 3
        _as(db, owner)
        assert len(security_activity.sign_ins(db, tid, str(owner.user_id))) == 1

        # The owner's security feed shows Finance's new device.
        feed = security_activity.feed(db, tid)
        assert any(event.kind == security_activity.NEW_DEVICE for event in feed)
        db.rollback()
