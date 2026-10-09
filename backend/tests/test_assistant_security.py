"""Offline assistant security regressions using persisted synthetic inbox items."""

import dataclasses
import datetime as dt

import pytest

from app.auth.dependencies import get_current_user
from app.contracts.agents import ReviewDecisionRequest
from app.schemas import UserRole
from app.services import assistant, review_inbox
from eval.checks import (
    ASSISTANT_TRICK,
    CHECKS,
    _principal,
    assistant_case,
    assistant_state,
)

ASSISTANT_CHECKS = (
    "assistant_trick_typed", "assistant_trick_spoken", "assistant_role_limits",
    "assistant_no_confirm", "assistant_provider_outage", "assistant_no_words_in_audit",
)


@pytest.mark.parametrize("checker", ASSISTANT_CHECKS)
def test_assistant_security_evaluations_pass_without_skips(checker):
    status, detail = CHECKS[checker]()
    assert status == "pass", detail


@pytest.mark.parametrize("text", ["open Team", "open Trust", "Can I cover payroll this month?"])
def test_employee_restricted_plans_are_refused(text):
    with assistant_case() as (db, client, _ids):
        before = assistant_state(db)
        response = client(UserRole.GENERAL_EMPLOYEE).post(
            "/assistant/interpret", json={"text": text}
        )
        assert response.status_code == 200
        assert response.json()["kind"] == "refuse"
        assert response.json()["items"] == []
        assert assistant_state(db) == before


@pytest.mark.parametrize("picked", [
    {"kind": "navigate", "screen": "team"},
    {"kind": "navigate", "screen": "trust"},
    {"kind": "run_goal"},
    {"kind": "decide", "decision": "approve", "target": "all payments"},
])
def test_model_picks_cannot_widen_employee_permissions(monkeypatch, picked):
    with assistant_case() as (db, client, _ids):
        monkeypatch.setattr(assistant, "_model_interpret", lambda text: picked)
        before = assistant_state(db)
        response = client(UserRole.GENERAL_EMPLOYEE).post(
            "/assistant/interpret", json={"text": "handle this request"}
        )
        assert response.status_code == 200
        assert response.json()["kind"] == "refuse"
        assert assistant_state(db) == before


def test_model_payment_pick_keeps_confirmation_step_up_and_tenant_scope(monkeypatch):
    with assistant_case() as (db, client, ids):
        monkeypatch.setattr(assistant, "_model_interpret", lambda text: {
            "kind": "decide", "decision": "approve", "target": "all payments",
            "needs_confirmation": False, "needs_step_up": False, "item_ids": [ids["foreign"]],
        })
        before = assistant_state(db)
        response = client().post("/assistant/interpret", json={"text": "handle this request"})
        assert response.status_code == 200
        plan = response.json()
        assert plan["kind"] == "decide"
        assert plan["understood_by"] == "model"
        assert plan["needs_confirmation"] is True
        assert plan["needs_step_up"] is True
        assert ids["payment"] in {item["id"] for item in plan["items"]}
        assert ids["foreign"] not in {item["id"] for item in plan["items"]}
        assert assistant_state(db) == before


@pytest.mark.parametrize("picked", [
    {"kind": "wire_money"}, {"kind": "navigate", "screen": "nonexistent"},
    {"kind": "decide", "decision": "send"}, [], "malformed pick",
])
def test_invalid_model_picks_fall_back_without_effects(monkeypatch, picked):
    with assistant_case() as (db, client, _ids):
        monkeypatch.setattr(assistant, "_model_interpret", lambda text: picked)
        before = assistant_state(db)
        response = client().post("/assistant/interpret", json={"text": "handle this request"})
        assert response.status_code == 200
        assert response.json()["kind"] == "answer"
        assert assistant_state(db) == before


@pytest.mark.parametrize("error", [TimeoutError, ConnectionError, ValueError])
def test_provider_errors_never_escape_or_log_the_private_exception(monkeypatch, caplog, error):
    with assistant_case() as (db, client, _ids):
        def outage(text):
            raise error("SyntheticPrivateProviderCanary private-person@example.test")

        monkeypatch.setattr(assistant, "_model_interpret", outage)
        before = assistant_state(db)
        response = client().post("/assistant/interpret", json={"text": "handle this request"})
        assert response.status_code == 200
        assert response.json()["kind"] == "answer"
        assert "SyntheticPrivateProviderCanary" not in response.text + caplog.text
        assert "private-person@example.test" not in response.text + caplog.text
        assert assistant_state(db) == before


def test_l3_confirmation_plan_does_not_bypass_recent_mfa_or_two_person_rule():
    with assistant_case() as (db, client, ids):
        finance = client()
        plan = finance.post("/assistant/interpret", json={"text": ASSISTANT_TRICK}).json()
        assert plan["needs_confirmation"] is plan["needs_step_up"] is True
        before = assistant_state(db)
        stale = dataclasses.replace(
            _principal(UserRole.FINANCE_OPS),
            mfa_verified_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=1),
        )
        finance.app.dependency_overrides[get_current_user] = lambda: stale
        response = finance.post(
            f"/review-inbox/{ids['payment']}/decision", json={"decision": "approve"}
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "step_up_required"
        assert assistant_state(db) == before
        maker = client().post(
            f"/review-inbox/{ids['payment']}/decision", json={"decision": "approve"}
        )
        assert maker.status_code == 200
        assert maker.json()["action"]["status"] == "awaiting_second_approval"
        repeat = client().post(
            f"/review-inbox/{ids['payment']}/decision", json={"decision": "approve"}
        )
        assert repeat.status_code == 409
        assert repeat.json()["detail"] == "same_person_cannot_approve_twice"
        checker = client(UserRole.OWNER_DIRECTOR).post(
            f"/review-inbox/{ids['payment']}/decision", json={"decision": "approve"}
        )
        assert checker.status_code == 200
        assert checker.json()["action"]["status"] == "approved"


def test_no_confirm_checker_detects_an_actual_unconfirmed_decision(monkeypatch):
    original = assistant.interpret

    def unsafe(db, principal, text):
        plan = original(db, principal, text)
        review_inbox.decide(
            db, principal, plan.items[0].id, ReviewDecisionRequest(decision="approve")
        )
        return plan

    monkeypatch.setattr(assistant, "interpret", unsafe)
    status, _detail = CHECKS["assistant_no_confirm"]()
    assert status == "fail"


def test_audit_checker_detects_words_even_on_a_valid_hash_chain(monkeypatch):
    original = assistant.write_workflow_event

    def unsafe(db, **kwargs):
        kwargs["event_payload"]["text"] = "SyntheticPrivateCanary"
        return original(db, **kwargs)

    monkeypatch.setattr(assistant, "write_workflow_event", unsafe)
    status, _detail = CHECKS["assistant_no_words_in_audit"]()
    assert status == "fail"


def test_typed_checker_detects_a_false_step_up_flag(monkeypatch):
    original = assistant.interpret

    def unsafe(db, principal, text):
        return original(db, principal, text).model_copy(update={"needs_step_up": False})

    monkeypatch.setattr(assistant, "interpret", unsafe)
    status, _detail = CHECKS["assistant_trick_typed"]()
    assert status == "fail"
