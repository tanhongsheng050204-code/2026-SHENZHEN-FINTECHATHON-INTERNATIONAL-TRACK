import json

from app.contracts.common import JobFunction
from app.routes.agents import router
from app.schemas import UserRole
from tests.contract_support import client_for


def _sse_events(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        data_line = next(line for line in block.splitlines() if line.startswith("data: "))
        events.append(json.loads(data_line.removeprefix("data: ")))
    return events


def test_every_position_has_an_agent():
    body = client_for(router, role=UserRole.GENERAL_EMPLOYEE).get("/agents").json()

    agents = body["agents"]
    assert body["data_mode"] == "live"
    assert len(agents) == 14
    covered = {agent["job_function"] for agent in agents} - {None}
    assert covered == {job.value for job in JobFunction}
    designed = [agent["id"] for agent in agents if agent["build_status"] == "designed"]
    assert designed == ["production"]


def test_skills_are_available_in_wave_one_and_planned_in_wave_two():
    agents = {a["id"]: a for a in client_for(router).get("/agents").json()["agents"]}

    for agent in agents.values():
        for skill in agent["skills"]:
            expected = (
                "available"
                if agent["build_status"] == "built" and skill["wave"] == "W1"
                else "planned"
            )
            assert skill["availability"] == expected
    built = [a for a in agents.values() if a["build_status"] == "built" and a["job_function"]]
    assert all(any(s["wave"] == "W1" for s in a["skills"]) for a in built)
    assert all(s["availability"] == "planned" for s in agents["production"]["skills"])


def test_run_streams_progress_events_in_order():
    client = client_for(router)
    created = client.post("/agents/runs", json={"goal": "Can I cover payroll this month?"})

    assert created.status_code == 200
    run = created.json()
    assert run["run_id"].startswith("run_demo_")
    stream = client.get(run["events_url"])
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("text/event-stream")
    events = _sse_events(stream.text)
    assert [event["sequence"] for event in events] == list(range(1, 10))
    assert events[0]["type"] == "run_started"
    assert events[-1]["type"] == "run_completed"
    assert {event["action_id"] for event in events} - {None} == {
        "act_cashflow_alert",
        "act_reminders",
        "act_financing_pack",
    }


def test_unknown_run_is_not_found():
    response = client_for(router).get("/agents/runs/run_other_12345678/events")

    assert response.status_code == 404
    assert response.json()["detail"] == "run_not_found"


def test_general_employee_cannot_start_a_run():
    response = client_for(router, role=UserRole.GENERAL_EMPLOYEE).post(
        "/agents/runs", json={"goal": "x"}
    )

    assert response.status_code == 403


def test_owner_grants_scoped_autonomy_to_receivables_agent():
    response = client_for(router).post(
        "/agents/receivables/autonomy",
        json={"action": "send_reminder", "level": "L2", "max_amount": "5000.00"},
    )

    assert response.status_code == 200
    assert response.json()["agent"]["scoped_autonomy"] == [
        {"action": "send_reminder", "level": "L2", "max_amount": "5000.00"}
    ]


def test_promotion_without_recommendation_is_refused():
    response = client_for(router).post(
        "/agents/customer_service/autonomy", json={"action": "send_reply", "level": "L2"}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "promotion_not_recommended"


def test_l3_can_never_be_delegated():
    response = client_for(router).post(
        "/agents/receivables/autonomy", json={"action": "pay_supplier", "level": "L3"}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "l3_not_delegable"


def test_designed_unknown_and_supervisor_agents_cannot_be_promoted():
    client = client_for(router)

    designed = client.post("/agents/production/autonomy", json={"action": "plan", "level": "L1"})
    supervisor = client.post("/agents/supervisor/autonomy", json={"action": "x", "level": "L1"})
    unknown = client.post("/agents/nobody/autonomy", json={"action": "pay", "level": "L1"})

    assert (designed.status_code, designed.json()["detail"]) == (409, "agent_not_promotable")
    assert (supervisor.status_code, supervisor.json()["detail"]) == (409, "agent_not_promotable")
    assert (unknown.status_code, unknown.json()["detail"]) == (404, "agent_not_found")


def test_only_the_owner_changes_autonomy():
    response = client_for(router, role=UserRole.FINANCE_OPS).post(
        "/agents/receivables/autonomy", json={"action": "send_reminder", "level": "L2"}
    )

    assert response.status_code == 403


def test_compliance_engages_global_and_single_kill_switches():
    client = client_for(router, role=UserRole.COMPLIANCE)

    everything = client.post("/agents/kill-switch", json={"engaged": True}).json()
    client.post("/agents/kill-switch", json={"engaged": False})
    single = client.post(
        "/agents/kill-switch", json={"agent_id": "purchasing", "engaged": True}
    ).json()
    unknown = client.post("/agents/kill-switch", json={"agent_id": "nobody", "engaged": True})

    assert everything["global_kill_switch_engaged"] is True
    assert all(agent["kill_switch_engaged"] for agent in everything["agents"])
    assert single["global_kill_switch_engaged"] is False
    assert [a["id"] for a in single["agents"] if a["kill_switch_engaged"]] == ["purchasing"]
    assert unknown.status_code == 404


def test_journey_groups_agents_by_position():
    body = client_for(router, role=UserRole.GENERAL_EMPLOYEE).get("/agents/journey").json()

    functions = {f["job_function"]: f["agents"] for f in body["functions"]}
    assert list(functions) == [job.value for job in JobFunction]
    assert [a["agent_id"] for a in functions["owner"]] == ["cashflow", "financing"]
    assert [a["agent_id"] for a in functions["finance"]] == ["receivables", "payables"]
    receivables = functions["finance"][0]
    assert receivables["estimated_hours_saved"] == 11.75
    assert receivables["override_rate"] == 0.06
    assert functions["production"][0]["build_status"] == "designed"
    assert functions["production"][0]["estimated_hours_saved"] == 0.0
