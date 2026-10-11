"""Automations prepare proposals for people; they never send, pay or change records."""

import datetime as dt

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models import WorkflowAuditEntry
from app.routes.collaboration import router
from app.schemas import UserRole
from app.services import automations, review_inbox
from tests.auth_support import TENANT_A, principal
from tests.test_collections_board import TODAY, live_db  # noqa: F401  (fixture)


def _client(db, role=UserRole.OWNER_DIRECTOR) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: principal(role)
    return TestClient(app)


def _open(db):
    return {
        item_id: item.action
        for item_id, item in review_inbox._replay(db, str(TENANT_A)).items()
        if item.action.status == "pending"
    }


def test_an_overdue_invoice_gets_a_reminder_proposal_once(live_db):  # noqa: F811
    owner = _client(live_db)
    saved = owner.post(
        "/automations",
        json={"trigger": "invoice_overdue_days", "days": 14, "action": "draft_reminder"},
    )
    assert saved.status_code == 200

    first = owner.post("/automations/run").json()["proposals"]
    again = owner.post("/automations/run").json()["proposals"]

    # The invoice now sits in "Reminder", so the second run prepares nothing new.
    assert len(first) == 1 and again == []
    assert len(_open(live_db)) == 1
    action = _open(live_db)[first[0]]
    assert action.title == "Payment reminder for INV-1"
    assert action.autonomy_level.value == "L2"


def test_a_threshold_that_nothing_reaches_creates_nothing(live_db):  # noqa: F811
    owner = _client(live_db)
    owner.post(
        "/automations",
        json={"trigger": "invoice_overdue_days", "days": 30, "action": "ask_review"},
    )

    assert owner.post("/automations/run").json()["proposals"] == []


def test_ask_review_goes_to_the_chosen_position(live_db):  # noqa: F811
    owner = _client(live_db)
    owner.post(
        "/automations",
        json={
            "trigger": "invoice_overdue_days",
            "days": 7,
            "action": "ask_review",
            "reviewer": "owner",
        },
    )
    [proposal] = owner.post("/automations/run").json()["proposals"]

    action = _open(live_db)[proposal]
    assert action.reviewer_job_function.value == "owner"
    assert action.autonomy_level.value == "L1"
    assert "nothing has been sent or paid" in action.summary


def test_reminders_only_follow_an_overdue_trigger(live_db):  # noqa: F811
    response = _client(live_db).post(
        "/automations",
        json={"trigger": "cash_shortfall_within_days", "days": 30, "action": "draft_reminder"},
    )

    assert (response.status_code, response.json()["detail"]) == (
        422,
        "reminders_need_an_overdue_trigger",
    )


def test_only_the_owner_creates_or_removes_automations(live_db):  # noqa: F811
    body = {"trigger": "invoice_overdue_days", "days": 14, "action": "draft_reminder"}
    finance = _client(live_db, UserRole.FINANCE_OPS)

    assert finance.post("/automations", json=body).status_code == 403
    automation_id = _client(live_db).post("/automations", json=body).json()["id"]
    assert finance.delete(f"/automations/{automation_id}").status_code == 403
    assert finance.get("/automations").json()["automations"][0]["id"] == automation_id

    assert _client(live_db).delete(f"/automations/{automation_id}").status_code == 204
    assert _client(live_db).get("/automations").json()["automations"] == []


def test_automations_live_on_the_chain_with_kinds_and_numbers(live_db):  # noqa: F811
    _client(live_db).post(
        "/automations",
        json={"trigger": "bill_due_within_days", "days": 10, "action": "ask_review"},
    )

    event = live_db.scalar(
        select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "automation_saved")
    )
    assert set(event.event_payload) == {"trigger", "days", "action", "reviewer", "enabled"}


def test_the_scheduler_runs_every_tenant_with_automations(live_db):  # noqa: F811
    _client(live_db).post(
        "/automations",
        json={"trigger": "invoice_overdue_days", "days": 14, "action": "draft_reminder"},
    )

    assert automations.run_due(live_db, dt.datetime.combine(TODAY, dt.time(9))) == 1
