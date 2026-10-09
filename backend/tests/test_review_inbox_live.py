import datetime as dt
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.auth.principal import AuthPrincipal
from app.contracts.common import AutonomyLevel, DataMode, JobFunction
from app.db import get_db
from app.models import Base, Tenant
from app.routes.agent_runs import router as runs_router
from app.routes.agents_live import router
from app.schemas import UserRole
from app.services import agent_runtime, cashflow, review_inbox
from app.services.cashflow_engine import CashBasis
from app.stubs import cashflow as demo
from tests.auth_support import TENANT_A, USER_IDS

LIVE = CashBasis(DataMode.LIVE, demo.OPENING_BALANCE, demo.MINIMUM_BALANCE, demo.BASIS.signals)
JOBS = {
    UserRole.OWNER_DIRECTOR: ("owner",),
    UserRole.FINANCE_OPS: ("finance", "hr"),
    UserRole.COMPLIANCE: ("compliance",),
    UserRole.GENERAL_EMPLOYEE: ("sales", "customer_service"),
}


def _principal(role: UserRole) -> AuthPrincipal:
    extra = {}
    if "job_functions" in AuthPrincipal.__dataclass_fields__:
        extra = {
            "job_functions": JOBS[role],
            "aal": "aal2",
            "mfa_verified_at": dt.datetime.now(dt.UTC),
        }
    return AuthPrincipal(user_id=USER_IDS[role], email=None, role=role, tenant_id=TENANT_A, **extra)


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Tenant(id=str(TENANT_A), slug="tenant-a", name="Tenant A"))
    session.commit()
    # This tenant runs on its own records: the demo signals, marked live.
    monkeypatch.setattr(cashflow, "basis_for", lambda *args: LIVE)
    monkeypatch.setattr(agent_runtime, "_external_guard", lambda *args, **kwargs: None)
    return session


def _client(db, role=UserRole.OWNER_DIRECTOR) -> TestClient:
    app = FastAPI()
    app.include_router(runs_router)
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: _principal(role)
    return TestClient(app)


def _run(client, goal="Can I cover payroll this month?") -> list[dict]:
    import json

    run = client.post("/agents/runs", json={"goal": goal}).json()
    text = client.get(run["events_url"]).text
    return [
        json.loads(line.removeprefix("data: "))
        for line in text.splitlines()
        if line.startswith("data: ")
    ]


def test_run_proposals_land_in_the_persisted_inbox_once(db):
    owner = _client(db)
    events = _run(owner)
    ids = {e["action_id"] for e in events if e["action_id"]}

    inbox = owner.get("/review-inbox").json()
    assert inbox["data_mode"] == "live"
    assert {a["id"] for a in inbox["actions"]} == ids
    # No financing facts on record here, so financing advises instead of proposing.
    assert {a["agent_id"] for a in inbox["actions"]} == {"cashflow", "receivables"}
    assert "2 items await your review" in events[-2]["message"]

    _run(owner)
    assert len(owner.get("/review-inbox").json()["actions"]) == 2


def test_reviewer_decides_once_and_the_decision_is_recorded(db):
    _run(_client(db))
    finance = _client(db, UserRole.FINANCE_OPS)
    item = next(
        a for a in finance.get("/review-inbox").json()["actions"] if a["agent_id"] == "receivables"
    )
    assert item["can_decide"] is True

    approved = finance.post(f"/review-inbox/{item['id']}/decision", json={"decision": "approve"})
    again = finance.post(f"/review-inbox/{item['id']}/decision", json={"decision": "approve"})

    assert approved.json()["action"]["status"] == "approved"
    assert (again.status_code, again.json()["detail"]) == (409, "already_decided")
    record = review_inbox.metrics(db, str(TENANT_A))["receivables"]
    assert (record.proposals, record.approved_unedited) == (1, 1)


def test_compliance_reads_everything_and_decides_nothing(db):
    _run(_client(db))
    compliance = _client(db, UserRole.COMPLIANCE)
    actions = compliance.get("/review-inbox").json()["actions"]

    assert len(actions) == 2
    assert not any(a["can_decide"] for a in actions)
    refused = compliance.post(
        f"/review-inbox/{actions[0]['id']}/decision", json={"decision": "approve"}
    )
    assert (refused.status_code, refused.json()["detail"]) == (403, "read_only_role")


def test_staff_outside_the_position_see_and_decide_nothing(db):
    owner_view = _run(_client(db))
    staff = _client(db, UserRole.GENERAL_EMPLOYEE)

    assert staff.get("/review-inbox").json()["actions"] == []
    item = next(e["action_id"] for e in owner_view if e["action_id"])
    refused = staff.post(f"/review-inbox/{item}/decision", json={"decision": "approve"})
    assert refused.status_code == 403


def test_money_movement_needs_a_maker_then_a_different_checker(db):
    action_id = review_inbox.propose(
        db,
        str(TENANT_A),
        agent_id="payables",
        reviewer=JobFunction.FINANCE,
        title="Pay supplier bill",
        summary="RM14,800.00 rent",
        amount=Decimal("14800.00"),
        level=AutonomyLevel.L3,
    )
    owner, finance = _client(db), _client(db, UserRole.FINANCE_OPS)
    url = f"/review-inbox/{action_id}/decision"

    first = owner.post(url, json={"decision": "approve"})
    edit = finance.post(url, json={"decision": "edit", "edited_draft": "Pay less"})
    maker = finance.post(url, json={"decision": "approve"})
    twice = finance.post(url, json={"decision": "approve"})
    checker = owner.post(url, json={"decision": "approve"})

    assert first.json()["detail"] == "maker_approval_required"
    assert edit.json()["detail"] == "edit_not_allowed_at_l3"
    assert maker.json()["action"]["status"] == "awaiting_second_approval"
    assert twice.json()["detail"] == "same_person_cannot_approve_twice"
    assert checker.json()["action"]["status"] == "approved"
    assert len(checker.json()["action"]["approvals"]) == 2


def test_autonomy_is_earned_from_the_review_record_and_persisted(db):
    owner = _client(db)
    grant = {"action": "send_reminder", "level": "L2", "max_amount": "5000.00"}

    early = owner.post("/agents/receivables/autonomy", json=grant)
    assert (early.status_code, early.json()["detail"]) == (409, "promotion_not_recommended")

    finance = _principal(UserRole.FINANCE_OPS)
    for n in range(review_inbox.PROMOTION_MIN_SAMPLE):
        action_id = review_inbox.propose(
            db,
            str(TENANT_A),
            agent_id="receivables",
            reviewer=JobFunction.FINANCE,
            title=f"Reminder {n}",
            summary="Draft",
        )
        review_inbox.decide(
            db, finance, action_id, review_inbox.ReviewDecisionRequest(decision="approve")
        )

    granted = owner.post("/agents/receivables/autonomy", json=grant)
    assert granted.status_code == 200
    assert granted.json()["data_mode"] == "live"
    card = next(a for a in owner.get("/agents").json()["agents"] if a["id"] == "receivables")
    assert card["metrics"]["proposals"] == 30
    assert card["metrics"]["promotion_recommended"] is True
    assert card["scoped_autonomy"][0]["level"] == "L2"
    l3 = owner.post("/agents/receivables/autonomy", json={**grant, "level": "L3"})
    assert l3.json()["detail"] == "l3_not_delegable"


def test_position_workspace_is_computed_from_the_records(db):
    owner = _client(db)
    _run(owner)

    finance = owner.get("/positions/finance/workspace").json()
    procurement = owner.get("/positions/procurement/workspace").json()
    hr = owner.get("/positions/hr/workspace").json()

    assert finance["data_mode"] == "live"
    results = {r["skill_id"]: r for r in finance["skill_results"]}
    assert results["rank_overdue"]["value"] == "RM73,700.00"
    assert finance["inbox_count"] == 1
    orders = {r["skill_id"]: r for r in procurement["skill_results"]}["committed_outflows"]
    assert orders["value"] == "RM99,540.00"
    assert orders["status"] == "attention"
    payroll = {r["skill_id"]: r for r in hr["skill_results"]}["payroll_cash_plan"]
    assert (payroll["value"], payroll["status"]) == ("RM62,000.00", "risk")
    staff = _client(db, UserRole.GENERAL_EMPLOYEE).get("/positions/finance/workspace")
    assert staff.status_code == 403
