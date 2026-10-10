"""One-click demo sign-in: a real provider session for the synthetic company, nothing bypassed.

Supabase responses are mocked; no provider emails, SMTP or Telegram calls occur.
"""

import dataclasses
import datetime as dt
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth import demo
from app.auth.provider import provider
from app.auth.sessions import COOKIE
from app.config import get_settings
from app.db import get_db
from app.integrations.email_connector import sender
from app.models import AuthUserRole, BackendAuthSession, Base, Tenant, WorkflowAuditEntry
from app.routes.auth import router as auth_router
from app.schemas import UserRole
from app.security import rate_limit
from app.services import alerts, briefing_push
from tests.auth_support import TENANT_A, TENANT_B, principal

ORIGIN = {"origin": "http://localhost:5173"}
SECRET = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # RFC 6238 test key "12345678901234567890"
DEMO_EMAIL = "demo-owner@example.invalid"
DEMO_USER = str(uuid4())
FACTOR = str(uuid4())


def test_totp_matches_the_rfc_6238_test_vector():
    assert demo.totp(SECRET, at=59) == "287082"
    assert demo.totp(SECRET, at=1111111109) == "081804"
    assert demo.totp(SECRET.lower(), at=59) == "287082"


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.add(Tenant(id=str(TENANT_A), slug="demo", name="Synthetic demo company"))
        session.add(Tenant(id=str(TENANT_B), slug="other", name="Other company"))
        session.commit()
        yield session
    engine.dispose()


@pytest.fixture
def enabled(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_cookie_secure", False)
    monkeypatch.setattr(settings, "demo_sign_in_enabled", True)
    monkeypatch.setattr(settings, "demo_email", DEMO_EMAIL)
    monkeypatch.setattr(settings, "demo_password", "fictional-demo-password")
    monkeypatch.setattr(settings, "demo_totp_secret", SECRET)
    monkeypatch.setattr(settings, "demo_tenant_id", str(TENANT_A))
    rate_limit.reset()
    return settings


@pytest.fixture
def client(db):
    app = FastAPI()
    app.include_router(auth_router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client


def _member(db, tenant=TENANT_A, user=DEMO_USER):
    db.add(
        AuthUserRole(
            user_id=user,
            tenant_id=str(tenant),
            user_role=UserRole.OWNER_DIRECTOR.value,
            job_functions=["owner"],
            active=True,
        )
    )
    db.commit()


@pytest.fixture
def fake_provider(monkeypatch):
    """Tokens are strings naming their assurance level; `_verified` turns them into claims."""
    calls = []
    monkeypatch.setattr(
        "app.auth.sessions._verified",
        lambda token: {"sub": DEMO_USER, "email": DEMO_EMAIL, "aal": token.split(":")[0]},
    )

    def call(method, path, **kw):
        calls.append((method, path, kw.get("payload")))
        if path.startswith("/token?grant_type=password"):
            return {"access_token": "aal1:a", "refresh_token": "r1", "expires_in": 3600}
        if method == "GET" and path == "/user":
            return {"factors": [{"id": FACTOR, "factor_type": "totp", "status": "verified"}]}
        if path.endswith("/challenge"):
            return {"id": str(uuid4())}
        if path.endswith("/verify"):
            return {"access_token": "aal2:b", "refresh_token": "r2", "expires_in": 3600}
        raise AssertionError(f"unexpected provider call {method} {path}")

    monkeypatch.setattr(provider, "call", call)
    return calls


def _sign_in(client):
    response = client.post("/auth/demo", headers=ORIGIN)
    if "set-cookie" in response.headers:
        client.cookies.set(COOKIE, response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1])
    return response


def test_demo_is_off_unless_the_server_turns_it_on(client, fake_provider):
    assert client.get("/auth/demo/status").json() == {"available": False}
    assert client.post("/auth/demo", headers=ORIGIN).status_code == 404
    assert fake_provider == []


def test_demo_needs_all_three_server_secrets(client, enabled, monkeypatch, fake_provider):
    monkeypatch.setattr(enabled, "demo_totp_secret", "")
    assert client.get("/auth/demo/status").json() == {"available": False}
    assert client.post("/auth/demo", headers=ORIGIN).status_code == 404


def test_demo_sign_in_is_a_real_password_and_authenticator_sign_in(
    db, client, enabled, fake_provider, monkeypatch
):
    _member(db)
    monkeypatch.setattr(demo.time, "time", lambda: 59.0)
    assert client.get("/auth/demo/status").json() == {"available": True}

    response = _sign_in(client)

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "authenticated"
    assert body["role"] == "owner_director"
    assert body["tenant_id"] == str(TENANT_A)
    assert body["aal"] == "aal2"
    verify = next(payload for method, path, payload in fake_provider if path.endswith("/verify"))
    assert verify["code"] == "287082"
    password = next(payload for _, path, payload in fake_provider if "grant_type=password" in path)
    assert password == {"email": DEMO_EMAIL, "password": "fictional-demo-password"}
    event = db.scalar(
        select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "demo_sign_in")
    )
    assert event is not None and event.tenant_id == str(TENANT_A)
    assert DEMO_EMAIL not in str(event.event_payload)


def test_demo_sign_in_refuses_other_origins(client, enabled, fake_provider):
    response = client.post("/auth/demo", headers={"origin": "https://evil.invalid"})
    assert response.status_code == 403
    assert fake_provider == []


def test_demo_account_outside_the_demo_company_is_refused(db, client, enabled, fake_provider):
    _member(db, tenant=TENANT_B)

    response = _sign_in(client)

    assert response.status_code == 503
    assert response.json()["detail"] == "demo_not_provisioned"
    assert all(row.revoked_at for row in db.scalars(select(BackendAuthSession)))


def test_the_authenticator_code_is_shown_only_to_the_demo_session(
    db, client, enabled, fake_provider, monkeypatch
):
    _member(db)
    assert client.get("/auth/demo/code").status_code == 401
    _sign_in(client)
    monkeypatch.setattr(demo.time, "time", lambda: 59.0)

    shown = client.get("/auth/demo/code")

    assert shown.status_code == 200
    assert shown.json() == {"code": "287082", "seconds_left": 1}
    assert shown.headers["cache-control"] == "no-store"


def test_the_code_is_hidden_from_everyone_else(db, client, enabled, monkeypatch):
    other = str(uuid4())
    _member(db, user=other)
    monkeypatch.setattr(
        "app.auth.sessions._verified",
        lambda token: {"sub": other, "email": "owner@example.invalid", "aal": "aal1"},
    )
    monkeypatch.setattr(
        provider,
        "call",
        lambda method, path, **kw: {
            "access_token": "aal1:x",
            "refresh_token": "r",
            "expires_in": 3600,
        },
    )
    response = client.post(
        "/auth/sign-in",
        json={"email": "owner@example.invalid", "password": "Fictional-1!"},
        headers=ORIGIN,
    )
    client.cookies.set(COOKIE, response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1])
    db.scalars(select(BackendAuthSession)).first().email_verified = True
    db.commit()

    assert client.get("/auth/demo/code").status_code == 404


@pytest.mark.parametrize("path", ["/auth/sign-out-everywhere", "/auth/mfa/enroll"])
def test_one_judge_cannot_lock_the_others_out(db, client, enabled, fake_provider, path):
    _member(db)
    csrf = _sign_in(client).json()["csrf_token"]

    response = client.post(path, headers={**ORIGIN, "x-csrf-token": csrf})

    assert response.status_code == 403
    assert response.json()["detail"] == "demo_account_locked"


def test_team_changes_are_closed_in_the_demo_company(enabled):
    owner = principal(UserRole.OWNER_DIRECTOR, tenant_id=TENANT_A)
    with pytest.raises(HTTPException) as refused:
        demo.forbid_in_demo(owner)
    assert refused.value.status_code == 403
    assert refused.value.detail == "demo_company_read_only"
    demo.forbid_in_demo(principal(UserRole.OWNER_DIRECTOR, tenant_id=TENANT_B))


def test_no_demo_rules_apply_when_demo_is_off():
    assert not demo.is_demo_tenant(str(TENANT_A))
    demo.forbid_in_demo(principal(UserRole.OWNER_DIRECTOR, tenant_id=TENANT_A))


def _owner():
    return dataclasses.replace(
        principal(UserRole.OWNER_DIRECTOR),
        job_functions=("owner",),
        aal="aal2",
        mfa_verified_at=dt.datetime.now(dt.UTC),
    )


def test_briefings_in_the_demo_company_are_recorded_not_sent(db, enabled, monkeypatch):
    _member(db, user=str(_owner().user_id))
    outbox = []
    monkeypatch.setattr(briefing_push, "_send_email", lambda *a: outbox.append(a))
    monkeypatch.setattr(briefing_push, "_send_telegram", lambda *a: outbox.append(a))
    monkeypatch.setattr(briefing_push.briefing, "push_text", lambda db, p: "Synthetic briefing")

    sent = briefing_push._deliver(
        db,
        _owner(),
        {"email": "judge@example.invalid", "telegram": "123"},
        dt.date(2026, 10, 12),
        force=True,
    )

    assert outbox == []
    assert sent == ["email", "telegram"]
    events = db.scalars(
        select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "briefing_pushed")
    ).all()
    assert [event.event_payload["simulated"] for event in events] == [True, True]


def test_alerts_in_the_demo_company_are_not_sent(db, enabled, monkeypatch):
    from decimal import Decimal

    _member(db)
    outbox = []
    monkeypatch.setattr(briefing_push, "_send_email", lambda *a: outbox.append(a))
    monkeypatch.setattr(briefing_push, "_send_telegram", lambda *a: outbox.append(a))
    monkeypatch.setattr(briefing_push, "_preferences", lambda db, tenant: {DEMO_USER: {}})
    monkeypatch.setattr(
        briefing_push, "_open", lambda user, payload: {"email": "judge@example.invalid"}
    )
    fired = alerts.Fired(
        rule_id="r1",
        metric="lowest_balance",
        subject="cash",
        value=Decimal("1"),
        channel="email",
        recipients=("owner",),
    )

    assert alerts._deliver(db, str(TENANT_A), fired) == 0
    assert outbox == []

    monkeypatch.setattr(enabled, "demo_sign_in_enabled", False)
    assert alerts._deliver(db, str(TENANT_A), fired) == 1


def test_outreach_in_the_demo_company_never_reaches_smtp(enabled, monkeypatch):
    from tests.test_email_sender import TENANT, _approved_action, _settings

    db, action = _approved_action()
    opened = []

    class SMTP:
        def __init__(self, *_a, **_k):
            opened.append(True)

    settings = _settings()
    settings.demo_sign_in_enabled = True
    settings.demo_tenant_id = TENANT
    monkeypatch.setattr(sender, "get_settings", lambda: settings)
    monkeypatch.setattr(sender.smtplib, "SMTP", SMTP)
    monkeypatch.setattr(enabled, "demo_tenant_id", TENANT)

    result = sender.dispatch_one(db)

    assert opened == []
    assert result.status == "cancelled"
    assert result.failure_code == "demo_delivery_simulated"
    db.close()


def test_team_routes_refuse_changes_in_the_demo_company(db, enabled):
    from app.auth.dependencies import get_current_user
    from app.routes.team import router as team_router

    app = FastAPI()
    app.include_router(team_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: principal(UserRole.OWNER_DIRECTOR)
    with TestClient(app) as team:
        invite = team.post(
            "/team/invitations",
            json={
                "email": "someone@example.invalid",
                "role": "finance_ops",
                "job_functions": ["finance"],
            },
        )
        member = team.patch(f"/team/members/{DEMO_USER}", json={"active": False})
        signout = team.post(f"/team/members/{DEMO_USER}/sign-out")
    for response in (invite, member, signout):
        assert response.status_code == 403
        assert response.json()["detail"] == "demo_company_read_only"


def test_provisioning_writes_secrets_only_to_a_new_private_file(db, monkeypatch, tmp_path, capsys):
    from scripts import provision_demo_account as script

    user = str(uuid4())

    def call(method, path, **kw):
        if path == "/admin/users":
            assert kw["admin"] and kw["payload"]["email_confirm"] is True
            return {"id": user}
        if "grant_type=password" in path:
            return {"access_token": "aal1:a"}
        if path == "/factors":
            return {"id": FACTOR, "totp": {"secret": SECRET}}
        if path.endswith("/challenge"):
            return {"id": "c1"}
        if path.endswith("/verify"):
            assert kw["payload"]["code"] == demo.totp(SECRET)
            return {"access_token": "aal2:b"}
        raise AssertionError(path)

    monkeypatch.setattr(script.provider, "call", call)
    monkeypatch.setattr(script, "SessionLocal", lambda: db)
    monkeypatch.setattr(get_settings(), "demo_tenant_id", str(TENANT_A))
    out = tmp_path / "demo.env"
    monkeypatch.setattr("sys.argv", ["provision", "--email", DEMO_EMAIL, "--out", str(out)])

    script.main()

    lines = dict(line.split("=", 1) for line in out.read_text().splitlines())
    assert lines["DEMO_SIGN_IN_ENABLED"] == "true"
    assert lines["DEMO_EMAIL"] == DEMO_EMAIL
    assert lines["DEMO_TOTP_SECRET"] == SECRET
    assert len(lines["DEMO_PASSWORD"]) >= 40
    printed = capsys.readouterr().out
    assert lines["DEMO_PASSWORD"] not in printed and SECRET not in printed
    member = db.get(AuthUserRole, (user, str(TENANT_A)))
    assert member.user_role == "owner_director" and member.active
    with pytest.raises(SystemExit):
        script.main()
