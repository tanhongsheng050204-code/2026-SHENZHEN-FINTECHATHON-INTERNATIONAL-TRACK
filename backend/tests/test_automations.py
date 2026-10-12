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

    assert automations.run_due(live_db, dt.datetime.combine(_weekday(TODAY), dt.time(9))) == 1


def _weekday(day: dt.date) -> dt.date:
    while day.weekday() >= 5:
        day += dt.timedelta(days=1)
    return day


def test_the_scheduler_waits_for_a_working_day(live_db):  # noqa: F811
    _client(live_db).post(
        "/automations",
        json={"trigger": "invoice_overdue_days", "days": 14, "action": "draft_reminder"},
    )
    saturday = TODAY + dt.timedelta(days=(5 - TODAY.weekday()) % 7)

    assert automations.run_due(live_db, dt.datetime.combine(saturday, dt.time(9))) == 0
    assert (
        automations.run_due(live_db, dt.datetime.combine(saturday + dt.timedelta(2), dt.time(9)))
        == 1
    )


def _sequence(db):
    _client(db).post(
        "/automations",
        json={"trigger": "invoice_overdue_days", "days": 7, "action": "reminder_sequence"},
    )


def _decide(db, action_id, decision="approve"):
    from app.contracts.agents import ReviewDecisionRequest

    review_inbox.decide(
        db, principal(UserRole.OWNER_DIRECTOR), action_id, ReviewDecisionRequest(decision=decision)
    )


def test_a_sequence_moves_from_friendly_to_firm_one_step_at_a_time(live_db):  # noqa: F811
    _sequence(live_db)
    owner = _client(live_db)

    [friendly] = owner.post("/automations/run").json()["proposals"]
    assert _open(live_db)[friendly].title == "Friendly reminder for INV-1"
    # Nothing new while the friendly reminder waits for approval.
    assert owner.post("/automations/run").json()["proposals"] == []

    _decide(live_db, friendly)
    [firm] = owner.post("/automations/run").json()["proposals"]
    assert _open(live_db)[firm].title == "Firm reminder for INV-1"
    assert _open(live_db)[firm].autonomy_level.value == "L2"

    # INV-1 is 20 days overdue: the call step (7 + 21 = 28 days) is not due yet.
    _decide(live_db, firm)
    assert owner.post("/automations/run").json()["proposals"] == []


def test_the_call_step_asks_finance_to_phone_the_customer(live_db):  # noqa: F811
    from app.models import SalesPipeline

    # INV-1 becomes 30 days overdue: every step of a 0-day sequence is due.
    live_db.get(SalesPipeline, 1).expected_payment_date = TODAY - dt.timedelta(days=30)
    live_db.commit()
    _client(live_db).post(
        "/automations",
        json={"trigger": "invoice_overdue_days", "days": 0, "action": "reminder_sequence"},
    )
    owner = _client(live_db)
    for _ in range(2):
        [step] = owner.post("/automations/run").json()["proposals"]
        _decide(live_db, step)

    [call] = owner.post("/automations/run").json()["proposals"]
    action = _open(live_db)[call]
    assert action.title == "Call the customer about INV-1"
    assert (action.autonomy_level.value, action.reviewer_job_function.value) == ("L1", "finance")
    assert action.draft is None


def test_sequences_only_follow_an_overdue_trigger(live_db):  # noqa: F811
    response = _client(live_db).post(
        "/automations",
        json={"trigger": "bill_due_within_days", "days": 7, "action": "reminder_sequence"},
    )
    assert response.status_code == 422


def test_a_rejected_step_stops_the_sequence_for_that_invoice(live_db):  # noqa: F811
    from app.models import SalesPipeline

    live_db.get(SalesPipeline, 1).expected_payment_date = TODAY - dt.timedelta(days=40)
    live_db.commit()
    _sequence(live_db)
    owner = _client(live_db)
    [friendly] = owner.post("/automations/run").json()["proposals"]

    _decide(live_db, friendly, "reject")

    # 40 days overdue, so the firm step would be due; a rejection means "don't chase".
    assert owner.post("/automations/run").json()["proposals"] == []


def test_each_step_says_why_it_was_proposed(live_db):  # noqa: F811
    _sequence(live_db)
    owner = _client(live_db)
    [friendly] = owner.post("/automations/run").json()["proposals"]
    assert "Why this step: INV-1 reached 7 days overdue" in _open(live_db)[friendly].summary

    _decide(live_db, friendly)
    [firm] = owner.post("/automations/run").json()["proposals"]
    assert "Why this step: INV-1 reached 14 days overdue and step 1 was approved" in (
        _open(live_db)[firm].summary
    )


def test_a_sequence_skips_an_invoice_on_hold(live_db):  # noqa: F811
    _sequence(live_db)
    owner = _client(live_db)
    finance = _client(live_db, UserRole.FINANCE_OPS)
    finance.put("/collections/holds/pipeline:1", json={"kind": "disputed"})

    assert owner.post("/automations/run").json()["proposals"] == []


def test_a_courtesy_reminder_goes_before_the_due_date(live_db):  # noqa: F811
    owner = _client(live_db)
    saved = owner.post(
        "/automations",
        json={"trigger": "invoice_due_within_days", "days": 7, "action": "draft_reminder"},
    )
    assert saved.status_code == 200

    # INV-2 is due in 5 days; INV-3 in 40 days is not yet in reach.
    [courtesy] = owner.post("/automations/run").json()["proposals"]
    action = _open(live_db)[courtesy]
    assert action.title == "Courtesy reminder for INV-2"
    assert action.autonomy_level.value == "L2"
    assert "falls due on" in action.draft
    assert owner.post("/automations/run").json()["proposals"] == []


def test_a_courtesy_trigger_cannot_run_a_sequence(live_db):  # noqa: F811
    response = _client(live_db).post(
        "/automations",
        json={"trigger": "invoice_due_within_days", "days": 7, "action": "reminder_sequence"},
    )
    assert response.status_code == 422


def test_run_history_shows_what_was_proposed_and_what_was_skipped(live_db):  # noqa: F811
    _sequence(live_db)
    owner = _client(live_db)
    automation_id = owner.get("/automations").json()["automations"][0]["id"]
    [friendly] = owner.post("/automations/run").json()["proposals"]
    owner.post("/automations/run")  # the friendly step still waits: skipped, once

    runs = owner.get(f"/automations/{automation_id}/runs").json()["runs"]
    assert [run["proposed"] for run in runs] == [[], [friendly]]
    assert runs[0]["skipped"] == {"waiting_for_decision": 1}
    assert runs[1]["skipped"] == {}
    # The same outcome again is not written twice.
    owner.post("/automations/run")
    assert len(owner.get(f"/automations/{automation_id}/runs").json()["runs"]) == 2


def test_run_history_is_kinds_and_ids_only(live_db):  # noqa: F811
    _sequence(live_db)
    owner = _client(live_db)
    owner.post("/automations/run")

    event = live_db.scalar(
        select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "automation_ran")
    )
    assert set(event.event_payload) == {"proposed", "skipped"}
    assert owner.get("/automations/auto_missing/runs").status_code == 404


def test_an_approved_reminder_is_not_proposed_again(live_db):  # noqa: F811
    owner = _client(live_db)
    owner.post(
        "/automations",
        json={"trigger": "invoice_overdue_days", "days": 14, "action": "draft_reminder"},
    )
    [reminder] = owner.post("/automations/run").json()["proposals"]
    _decide(live_db, reminder)

    # INV-1 leaves the Reminder column once approved; one reminder per invoice is enough.
    assert owner.post("/automations/run").json()["proposals"] == []
