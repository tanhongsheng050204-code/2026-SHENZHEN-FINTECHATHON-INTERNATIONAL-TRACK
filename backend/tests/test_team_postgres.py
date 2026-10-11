"""Team features under real PostgreSQL row-level security.

The application role reads only the chain entries a person wrote, unless they are
the owner or Compliance. The review inbox, comments, mentions, saved views and
automations are replayed from entries others wrote, so Finance and staff must still
see them. Runs only against a disposable migrated database, like
tests/test_passports_postgres.py.
"""

import os
from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.contracts.agents import ReviewDecisionRequest
from app.contracts.collaboration import AutomationRequest, SavedViewFilters, SavedViewRequest
from app.contracts.common import AutonomyLevel, JobFunction
from app.db import set_rls_context
from app.models import AuthUserRole, Tenant
from app.schemas import UserRole
from app.security.keyring import ensure_active_key
from app.services import automations, review_comments, review_inbox, saved_views
from app.services.tenant_settings import initialize_settings
from app.services.workflow_audit import write_workflow_event
from tests.auth_support import principal

DSN = os.environ.get("FINBRAIN_REVIEW_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DSN, reason="requires disposable migrated PostgreSQL")


def _as(db, person):
    db.commit()
    set_rls_context(
        db,
        user_id=str(person.user_id),
        user_role=person.role.value,
        tenant_id=str(person.tenant_id),
        actor_ref=person.actor_ref,
    )


def _team():
    tenant = uuid4()
    return {
        role: replace(principal(role), user_id=uuid4(), tenant_id=tenant)
        for role in (UserRole.OWNER_DIRECTOR, UserRole.FINANCE_OPS, UserRole.GENERAL_EMPLOYEE)
    }


def test_finance_and_staff_see_the_work_others_wrote():
    engine = create_engine(DSN)
    team = _team()
    owner = team[UserRole.OWNER_DIRECTOR]
    finance = team[UserRole.FINANCE_OPS]
    staff = team[UserRole.GENERAL_EMPLOYEE]
    tid = str(owner.tenant_id)
    with Session(engine, expire_on_commit=False) as db:
        db.add(Tenant(id=tid, name="SYNTHETIC team review", slug=f"review-{tid}"))
        db.flush()
        initialize_settings(db, tid, "SYNTHETIC team review")
        for person in team.values():
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
        ensure_active_key(db)
        db.commit()

        # An agent's proposal for Finance, written during the owner's request.
        _as(db, owner)
        action_id = review_inbox.propose(
            db,
            tid,
            agent_id="receivables",
            reviewer=JobFunction.FINANCE,
            title="Review 3 reminder drafts",
            summary="Three invoices are past due.",
            level=AutonomyLevel.L1,
        )
        automations.save(
            db,
            owner,
            AutomationRequest(trigger="invoice_overdue_days", days=14, action="draft_reminder"),
        )

        # Finance sees the agent's item, comments on it and saves a shared view.
        _as(db, finance)
        _, actions = review_inbox.inbox(db, finance, None)
        assert [a.id for a in actions] == [action_id]
        review_comments.add(db, finance, action_id, "Owner, please check this.", ["owner"])
        decided = review_inbox.decide(
            db, finance, action_id, ReviewDecisionRequest(decision="approve")
        )
        assert decided.status == "approved"
        saved_views.save(
            db,
            finance,
            SavedViewRequest(
                screen="customers", filters=SavedViewFilters(priorities=["urgent"]), shared=True
            ),
        )
        assert [a.trigger for a in automations.automations(db, tid)] == ["invoice_overdue_days"]

        # The owner sees Finance's comment and mention.
        _as(db, owner)
        assert [c.text for c in review_comments.comments(db, owner, action_id)] == [
            "Owner, please check this."
        ]
        assert [m.action_id for m in review_comments.mentions_for(db, owner)] == [action_id]

        # Staff see the shared view, but not Finance's review item.
        _as(db, staff)
        assert len(saved_views.views(db, staff, "customers")) == 1
        _, staff_actions = review_inbox.inbox(db, staff, None)
        assert staff_actions == []
        db.rollback()


def test_a_delegated_decision_keeps_the_inbox_locked_until_its_transaction_ends():
    engine = create_engine(DSN)
    team = _team()
    owner, finance = team[UserRole.OWNER_DIRECTOR], team[UserRole.FINANCE_OPS]
    tid = str(owner.tenant_id)
    key = {"key": f"finbrain:review-inbox:{tid}"}
    with Session(engine, expire_on_commit=False) as db, Session(engine) as other:
        db.add(Tenant(id=tid, name="SYNTHETIC lock review", slug=f"review-{tid}"))
        db.commit()
        _as(db, finance)
        review_inbox._lock(db, tid)
        # An agent's entry: Finance cannot read it back, so it goes via the worker.
        write_workflow_event(
            db,
            event_type="review_decision",
            actor_role="finance_ops",
            actor_ref=str(finance.user_id),
            resource_type="agent_action",
            resource_id="act_lock_review",
            event_payload={"decision": "approve"},
            tenant_id=tid,
        )
        assert other.scalar(text("select pg_try_advisory_lock(hashtext(:key))"), key) is False
        db.rollback()
        assert other.scalar(text("select pg_try_advisory_lock(hashtext(:key))"), key) is True
        other.execute(text("select pg_advisory_unlock(hashtext(:key))"), key)


def test_an_mcp_key_reads_its_own_company_under_rls():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.db import get_db
    from app.routes.mcp import router
    from app.security import rate_limit
    from app.services import api_keys

    rate_limit.reset()
    engine = create_engine(DSN)
    team = _team()
    owner = team[UserRole.OWNER_DIRECTOR]
    tid = str(owner.tenant_id)
    with Session(engine, expire_on_commit=False) as db:
        db.execute(text("insert into auth.users(id) values (:id)"), {"id": str(owner.user_id)})
        db.add(Tenant(id=tid, name="SYNTHETIC mcp review", slug=f"review-{tid}"))
        db.flush()
        initialize_settings(db, tid, "SYNTHETIC mcp review")
        db.commit()
        _as(db, owner)
        _, secret = api_keys.create(db, owner)

    app = FastAPI()
    app.include_router(router)

    def fresh_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = fresh_session
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {secret}"}
    for name in ("get_review_inbox", "get_collections_board", "get_forecast_check"):
        response = client.post(
            "/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name}},
        )
        assert response.status_code == 200, response.text
        assert response.json()["result"]["isError"] is False, name
