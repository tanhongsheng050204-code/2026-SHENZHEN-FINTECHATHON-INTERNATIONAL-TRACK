"""Sign-in activity and the security feed: who changed what that matters, kinds only."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models import Base, Tenant, WorkflowAuditEntry
from app.schemas import UserRole
from app.services import security_activity
from app.services.workflow_audit import write_workflow_event
from tests.auth_support import TENANT_A, principal

CHROME_WINDOWS = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
SAFARI_IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Tenant(id=str(TENANT_A), slug="tenant-a", name="Tenant A"))
    session.commit()
    return session


def _request(agent: str, address: str):
    return SimpleNamespace(headers={"user-agent": agent}, client=SimpleNamespace(host=address))


def _signed_in(db, person, agent=CHROME_WINDOWS, address="203.0.113.7"):
    row = SimpleNamespace(user_id=str(person.user_id), tenant_id=str(person.tenant_id))
    return security_activity.record_sign_in(db, row, _request(agent, address), method="password")


def _client(db, role=UserRole.OWNER_DIRECTOR) -> TestClient:
    from app.routes.security import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: principal(role)
    return TestClient(app)


def test_a_sign_in_keeps_the_device_kind_and_never_the_address(db):
    owner = principal(UserRole.OWNER_DIRECTOR)
    _signed_in(db, owner)

    event = db.scalar(
        select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "sign_in_recorded")
    )
    payload = event.event_payload
    assert (payload["browser"], payload["system"], payload["method"]) == (
        "Chrome",
        "Windows",
        "password",
    )
    assert "203.0.113.7" not in str(payload) and "Mozilla" not in str(payload)
    assert len(payload["device"]) == 16
    assert event.resource_id == str(owner.user_id)


def test_only_a_device_never_seen_before_counts_as_new(db):
    owner = principal(UserRole.OWNER_DIRECTOR)

    assert _signed_in(db, owner) is False  # the first sign-in sets the baseline
    assert _signed_in(db, owner) is False
    assert _signed_in(db, owner, SAFARI_IPHONE, "198.51.100.4") is True
    assert _signed_in(db, owner, SAFARI_IPHONE, "198.51.100.4") is False


def test_each_person_sees_only_their_own_sign_ins(db):
    owner, finance = principal(UserRole.OWNER_DIRECTOR), principal(UserRole.FINANCE_OPS)
    _signed_in(db, owner)
    _signed_in(db, finance, SAFARI_IPHONE)

    mine = _client(db, UserRole.FINANCE_OPS).get("/security/sign-ins").json()["sign_ins"]
    assert [(s["browser"], s["system"]) for s in mine] == [("Safari", "iOS")]


def test_owner_and_compliance_see_the_security_feed_staff_do_not(db):
    write_workflow_event(
        db,
        event_type="api_key_created",
        actor_role="owner_director",
        actor_ref="owner",
        resource_type="api_key",
        resource_id="abc123abc123",
        event_payload={"digest": "x" * 64, "scope": "read", "owner": "u"},
        tenant_id=str(TENANT_A),
    )
    db.commit()

    feed = _client(db).get("/security/activity").json()["events"]
    assert [(e["kind"], e["severity"]) for e in feed] == [("api_key_created", "warning")]
    assert feed[0]["title"] == "An AI connection key was created"
    # Kinds and roles only: no digests, ids of people or payloads.
    assert "digest" not in str(feed) and "xxxx" not in str(feed)
    assert _client(db, UserRole.COMPLIANCE).get("/security/activity").status_code == 200
    assert _client(db, UserRole.GENERAL_EMPLOYEE).get("/security/activity").status_code == 403


def test_a_new_device_is_a_warning_and_an_ordinary_sign_in_is_not_listed(db):
    owner = principal(UserRole.OWNER_DIRECTOR)
    _signed_in(db, owner)
    _signed_in(db, owner, SAFARI_IPHONE)

    feed = _client(db).get("/security/activity").json()["events"]
    assert [(e["kind"], e["severity"], e["title"]) for e in feed] == [
        ("sign_in_recorded", "warning", "Sign-in from a new device: Safari on iOS")
    ]


def test_events_from_other_companies_never_appear(db):
    other = "00000000-0000-0000-0000-0000000000bb"
    db.add(Tenant(id=other, slug="tenant-b", name="Tenant B"))
    write_workflow_event(
        db,
        event_type="agent.kill_switch",
        actor_role="owner_director",
        actor_ref="owner-b",
        resource_type="agent",
        resource_id="all",
        event_payload={"enabled": True},
        tenant_id=other,
    )
    db.commit()

    assert _client(db).get("/security/activity").json()["events"] == []


def test_verifying_the_sign_in_code_records_the_sign_in(db, monkeypatch):
    from fastapi import Response

    from app.auth.provider import provider
    from app.auth.sessions import COOKIE, create_session
    from app.config import get_settings
    from app.models import AuthUserRole
    from app.routes.auth import router as auth_router

    owner = principal(UserRole.OWNER_DIRECTOR)
    db.add(
        AuthUserRole(
            user_id=str(owner.user_id),
            tenant_id=str(TENANT_A),
            user_role="owner_director",
            job_functions=["owner"],
            active=True,
        )
    )
    db.commit()
    monkeypatch.setattr(get_settings(), "auth_cookie_secure", False)
    monkeypatch.setattr(
        "app.auth.sessions._verified",
        lambda _: {"sub": str(owner.user_id), "email": "owner@example.invalid"},
    )
    monkeypatch.setattr(
        provider, "call", lambda *a, **kw: {"access_token": "fictional", "refresh_token": "r"}
    )
    response = Response()
    _, csrf = create_session(db, response, {"email": "owner@example.invalid"}, "signin")
    db.commit()
    handle = response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    app = FastAPI()
    app.include_router(auth_router)
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    client.cookies.set(COOKIE, handle)

    result = client.post(
        "/auth/email/verify",
        json={"code": "123456"},
        headers={
            "origin": get_settings().cors_origin_list[0],
            "x-csrf-token": csrf,
            "user-agent": CHROME_WINDOWS,
        },
    )
    assert result.status_code == 200, result.text
    [event] = db.scalars(
        select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "sign_in_recorded")
    ).all()
    assert event.event_payload["method"] == "password_and_email_code"
    assert event.event_payload["browser"] == "Chrome"
