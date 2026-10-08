import json

import pytest
from fastapi import HTTPException

from app.routes.agent_runs import router
from app.schemas import UserRole
from app.services import agent_runtime
from tests.auth_support import TENANT_B, principal
from tests.contract_support import _client, client_for


@pytest.fixture(autouse=True)
def _no_persistent_guardrails(monkeypatch):
    # These clients have no database; the persistent kill switch has its own tests.
    monkeypatch.setattr(agent_runtime, "_external_guard", lambda *args, **kwargs: None)


def _sse_events(text: str) -> list[dict]:
    return [
        json.loads(line.removeprefix("data: "))
        for block in text.strip().split("\n\n")
        for line in block.splitlines()
        if line.startswith("data: ")
    ]


def _run(goal: str, client=None) -> list[dict]:
    client = client or client_for(router)
    created = client.post("/agents/runs", json={"goal": goal})
    assert created.status_code == 200
    stream = client.get(created.json()["events_url"])
    assert stream.status_code == 200
    return _sse_events(stream.text)


def test_payroll_goal_runs_forecast_collections_and_financing_on_real_numbers():
    events = _run("Can I cover payroll this month?")

    assert [e["sequence"] for e in events] == list(range(1, len(events) + 1))
    assert events[0]["type"] == "run_started"
    assert events[-1]["type"] == "run_completed"
    tools = [(e["agent_id"], e["message"]) for e in events if e["type"] == "tool_called"]
    assert [agent for agent, _ in tools] == ["cashflow", "receivables", "financing"]
    assert "match_products(gap=29440.00)" in tools[2][1]

    proposals = {e["agent_id"]: e for e in events if e["type"] == "proposal_created"}
    assert "day 23" in proposals["cashflow"]["message"]
    assert "RM29,440.00" in proposals["cashflow"]["message"]
    # Collecting INV-1041, INV-1043 and INV-1047 on their due dates closes the gap.
    assert "INV-1041, INV-1043, INV-1047" in proposals["receivables"]["message"]
    assert "closes the gap" in proposals["receivables"]["message"]
    assert "Invoice financing" in proposals["financing"]["message"]
    assert {p["action_id"] for p in proposals.values()} == {
        "act_cashflow_alert",
        "act_reminders",
        "act_financing_pack",
    }
    assert events[-2]["type"] == "waiting_for_review"
    assert "3 items" in events[-2]["message"]


def test_goal_outside_every_agent_is_answered_honestly():
    events = _run("What will the weather be tomorrow?")

    assert [e["type"] for e in events] == ["run_started", "run_completed"]
    assert all(e["action_id"] is None for e in events)
    assert "cash, collections or financing" in events[-1]["message"]


def test_financing_goal_skips_collections():
    events = _run("Which loans can we apply for?")

    tools = [e["agent_id"] for e in events if e["type"] == "tool_called"]
    assert tools == ["cashflow", "financing"]


def test_malay_and_chinese_goals_are_routed():
    for goal in ("Boleh bayar gaji bulan ini?", "这个月够发工资吗？"):
        tools = [e["agent_id"] for e in _run(goal) if e["type"] == "tool_called"]
        assert tools[0] == "cashflow"


def test_tampered_run_id_is_not_found():
    client = client_for(router)
    run = client.post("/agents/runs", json={"goal": "Can I cover payroll?"}).json()
    forged = run["run_id"][:-1] + ("0" if run["run_id"][-1] != "0" else "1")

    assert client.get(f"/agents/runs/{forged}/events").status_code == 404
    assert client.get("/agents/runs/run_demo_12345678/events").status_code == 404


def test_run_cannot_be_read_by_another_tenant():
    run = client_for(router).post("/agents/runs", json={"goal": "Can I cover payroll?"}).json()
    other = _client(router, principal(UserRole.OWNER_DIRECTOR, tenant_id=TENANT_B))

    assert other.get(run["events_url"]).status_code == 404


def test_general_employee_cannot_start_a_run():
    response = client_for(router, role=UserRole.GENERAL_EMPLOYEE).post(
        "/agents/runs", json={"goal": "Can I cover payroll?"}
    )

    assert response.status_code == 403


def test_every_tool_call_is_authorized_against_the_manifest(monkeypatch):
    calls = []
    monkeypatch.setattr(
        agent_runtime, "_external_guard", lambda *args, **kwargs: calls.append(kwargs)
    )

    _run("Can I cover payroll this month?")

    assert [(c["agent_id"], c["skill_id"], c["side_effect"]) for c in calls] == [
        ("supervisor", "route_goal", "read"),
        ("cashflow", "forecast", "read"),
        ("receivables", "rank_overdue", "read"),
        ("financing", "match_products", "read"),
    ]


def test_refused_tool_stops_the_run_before_streaming(monkeypatch):
    stopped = {"cashflow"}

    def guard(*args, agent_id, **kwargs):
        if agent_id in stopped:
            raise HTTPException(409, "kill_switch_engaged")

    monkeypatch.setattr(agent_runtime, "_external_guard", guard)
    client = client_for(router)
    run = client.post("/agents/runs", json={"goal": "Can I cover payroll?"}).json()

    response = client.get(run["events_url"])

    assert response.status_code == 409
    assert response.json()["detail"] == "kill_switch_engaged"

    stopped.add("supervisor")
    refused = client.post("/agents/runs", json={"goal": "Can I cover payroll?"})
    assert refused.status_code == 409


def test_skill_outside_the_manifest_is_refused():
    with pytest.raises(HTTPException) as refused:
        agent_runtime.authorize(
            None, principal(UserRole.OWNER_DIRECTOR), "cashflow", "pay_supplier"
        )

    assert refused.value.status_code == 403
    assert refused.value.detail == "tool_not_allowed"
