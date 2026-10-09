from app.routes.trust import router
from app.schemas import UserRole
from tests.contract_support import client_for


def test_posture_summarises_controls_and_recent_attacks():
    body = client_for(router, role=UserRole.COMPLIANCE).get("/trust/posture").json()

    assert body["data_mode"] == "live"
    assert 0 <= body["score"] <= 100
    metrics = {metric["key"]: metric for metric in body["metrics"]}
    assert metrics["mfa_coverage"]["value"] == "4/4"
    assert metrics["inactive_users"]["status"] == "attention"
    assert {event["owasp_code"] for event in body["recent_events"]} == {"ASI01", "ASI03", "ASI09"}


def test_guardrail_feed_is_newest_first_and_limited():
    body = client_for(router).get("/trust/guardrail-events", params={"limit": 2}).json()

    assert [event["id"] for event in body["events"]] == ["ge_4", "ge_3"]


def test_guardrail_feed_limit_is_bounded():
    assert client_for(router).get("/trust/guardrail-events", params={"limit": 0}).status_code == 422


def test_finance_cannot_see_posture():
    response = client_for(router, role=UserRole.FINANCE_OPS).get("/trust/posture")

    assert response.status_code == 403
