"""The incident register: record a breach, work the PDPA checklist, draft notices for a person."""

import datetime as dt

import pytest
from sqlalchemy import select

from app.models import AuthUserRole, WorkflowAuditEntry
from app.schemas import UserRole
from app.services import review_inbox
from tests.auth_support import TENANT_A, principal
from tests.test_security_activity import _client, db  # noqa: F401  (fixture)

TODAY = dt.date.today()
BREACH = {
    "kind": "data_sent_to_wrong_person",
    "data_kinds": ["contact_details", "financial_records"],
    "people_affected": 12,
    "significant_harm": True,
    "detected_on": TODAY.isoformat(),
}


@pytest.fixture
def team(db):  # noqa: F811
    for role in (UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE, UserRole.FINANCE_OPS):
        person = principal(role)
        db.add(
            AuthUserRole(
                user_id=str(person.user_id),
                tenant_id=str(TENANT_A),
                user_role=role.value,
                job_functions=list(person.job_functions),
                active=True,
                email_masked=f"{role.value[0]}***@example.test",
            )
        )
    db.commit()
    return db


def _open(client) -> dict:
    response = client.post("/security/incidents", json=BREACH)
    assert response.status_code == 200, response.text
    return response.json()


def test_compliance_records_an_incident_and_gets_the_pdpa_checklist(db):  # noqa: F811
    incident = _open(_client(db, UserRole.COMPLIANCE))

    assert incident["status"] == "open"
    steps = {s["step"]: s for s in incident["checklist"]}
    assert list(steps) == [
        "contained",
        "assessed",
        "commissioner_notified",
        "individuals_notified",
        "closed",
    ]
    # Significant harm is likely, so the people affected must be told too.
    assert steps["individuals_notified"]["required"] is True
    assert not any(s["done"] for s in incident["checklist"])


def test_without_significant_harm_individuals_need_not_be_told(db):  # noqa: F811
    client = _client(db, UserRole.COMPLIANCE)
    incident = client.post("/security/incidents", json={**BREACH, "significant_harm": False}).json()

    steps = {s["step"]: s for s in incident["checklist"]}
    assert steps["individuals_notified"]["required"] is False
    assert steps["commissioner_notified"]["required"] is True


def test_steps_are_recorded_and_closing_waits_for_the_required_ones(db):  # noqa: F811
    client = _client(db, UserRole.COMPLIANCE)
    incident_id = _open(client)["id"]

    for step in ("contained", "assessed", "commissioner_notified"):
        assert (
            client.post(f"/security/incidents/{incident_id}/steps", json={"step": step}).status_code
            == 200
        )
    refused = client.post(f"/security/incidents/{incident_id}/steps", json={"step": "closed"})
    assert (refused.status_code, refused.json()["detail"]) == (409, "required_steps_open")

    client.post(f"/security/incidents/{incident_id}/steps", json={"step": "individuals_notified"})
    closed = client.post(f"/security/incidents/{incident_id}/steps", json={"step": "closed"}).json()
    assert closed["status"] == "closed"
    assert all(s["done"] for s in closed["checklist"] if s["required"])


def test_a_notice_is_a_draft_for_a_person_never_sent(db):  # noqa: F811
    client = _client(db, UserRole.COMPLIANCE)
    incident_id = _open(client)["id"]

    response = client.post(
        f"/security/incidents/{incident_id}/notices", json={"audience": "commissioner"}
    )
    action_id = response.json()["action_id"]
    action = review_inbox._replay(db, str(TENANT_A))[action_id].action
    assert action.status == "pending"
    assert action.reviewer_job_function.value == "compliance"
    assert "Nothing has been sent" in action.summary
    assert "12" in action.draft and "contact details" in action.draft


def test_who_can_record_incidents(db):  # noqa: F811
    assert (
        _client(db, UserRole.OWNER_DIRECTOR).post("/security/incidents", json=BREACH).status_code
        == 200
    )
    assert (
        _client(db, UserRole.FINANCE_OPS).post("/security/incidents", json=BREACH).status_code
        == 403
    )
    assert _client(db, UserRole.GENERAL_EMPLOYEE).get("/security/incidents").status_code == 403


def test_incidents_are_kinds_and_numbers_on_the_chain(db):  # noqa: F811
    _open(_client(db, UserRole.COMPLIANCE))

    event = db.scalar(
        select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "incident_opened")
    )
    assert set(event.event_payload) == set(BREACH)
    assert _client(db).get("/security/activity").json()["events"][0]["severity"] == "critical"


def test_incident_fields_are_checked(db):  # noqa: F811
    client = _client(db, UserRole.COMPLIANCE)
    future = (TODAY + dt.timedelta(days=1)).isoformat()

    assert (
        client.post("/security/incidents", json={**BREACH, "detected_on": future}).status_code
        == 422
    )
    assert client.post("/security/incidents", json={**BREACH, "data_kinds": []}).status_code == 422
    assert client.post("/security/incidents", json={**BREACH, "kind": "gossip"}).status_code == 422
    assert (
        client.post("/security/incidents/inc_missing/steps", json={"step": "assessed"}).status_code
        == 404
    )


def test_the_owner_names_a_data_protection_officer_from_the_team(team):
    owner = _client(team)
    compliance_id = str(principal(UserRole.COMPLIANCE).user_id)

    assert owner.get("/security/dpo").json()["officer"] is None
    assert owner.put("/security/dpo", json={"user_id": compliance_id}).status_code == 200
    officer = _client(team, UserRole.FINANCE_OPS).get("/security/dpo").json()["officer"]
    assert (officer["user_id"], officer["role"], officer["email_masked"]) == (
        compliance_id,
        "compliance",
        "c***@example.test",
    )
    # Only the owner names the officer, and only someone on the team.
    assert (
        _client(team, UserRole.COMPLIANCE)
        .put("/security/dpo", json={"user_id": compliance_id})
        .status_code
        == 403
    )
    stranger = "99999999-0000-0000-0000-000000000009"
    assert owner.put("/security/dpo", json={"user_id": stranger}).status_code == 404
