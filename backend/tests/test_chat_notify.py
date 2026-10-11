"""Chat notifications: counts and a link only, sent when they change, never from the demo."""

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.config import get_settings
from app.contracts.common import AutonomyLevel, JobFunction
from app.db import get_db
from app.models import Base, Tenant, WorkflowAuditEntry
from app.routes.collaboration import router
from app.schemas import UserRole
from app.services import chat_notify, review_inbox
from tests.auth_support import TENANT_A, principal

TENANT = str(TENANT_A)


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Tenant(id=TENANT, slug="tenant-a", name="Tenant A"))
    session.commit()
    settings = get_settings()
    monkeypatch.setattr(settings, "chat_notifications_enabled", True)
    monkeypatch.setattr(settings, "chat_notify_tenant_id", TENANT)
    monkeypatch.setattr(settings, "slack_webhook_url", "https://hooks.slack.test/T/B/X")
    monkeypatch.setattr(settings, "whatsapp_access_token", "")
    monkeypatch.setattr(settings, "demo_sign_in_enabled", False)
    return session


@pytest.fixture
def sent(monkeypatch):
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, request=httpx.Request("POST", url))

    monkeypatch.setattr(chat_notify, "_post", fake_post)
    return calls


def _item(db, title="Approve the October payroll run", job=JobFunction.FINANCE):
    return review_inbox.propose(
        db,
        TENANT,
        agent_id="hr_payroll",
        reviewer=job,
        title=title,
        summary="Prepared.",
        level=AutonomyLevel.L1,
    )


def test_the_message_has_counts_and_a_link_but_no_titles(db, sent):
    _item(db)
    _item(db, "Reply to Customer C's complaint", JobFunction.OWNER)

    assert chat_notify.run_due(db) == 1
    [(url, kwargs)] = sent
    text = kwargs["json"]["text"]
    assert url == "https://hooks.slack.test/T/B/X"
    assert text.startswith("DuitDuit: 2 items wait for review (Finance 1, Owner 1).")
    assert text.endswith("/inbox")
    assert "payroll" not in text and "Customer C" not in text


def test_nothing_is_sent_again_until_the_counts_change(db, sent):
    _item(db)
    chat_notify.run_due(db)
    chat_notify.run_due(db)
    assert len(sent) == 1

    _item(db, "Approve PO-778")
    chat_notify.run_due(db)
    assert len(sent) == 2


def test_the_demo_company_is_recorded_as_simulated_and_never_sent(db, sent, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_sign_in_enabled", True)
    monkeypatch.setattr(settings, "demo_tenant_id", TENANT)
    _item(db)

    chat_notify.run_due(db)

    assert sent == []
    event = db.scalar(
        select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "chat_notified")
    )
    assert event.event_payload == {"status": "simulated", "waiting": {"finance": 1}}


def test_a_failed_delivery_is_recorded(db, monkeypatch):
    def refuse(url, **kwargs):
        return httpx.Response(403, request=httpx.Request("POST", url))

    monkeypatch.setattr(chat_notify, "_post", refuse)
    _item(db)

    assert chat_notify.notify(db, TENANT, "slack", {"finance": 1}) == "failed"


def test_whatsapp_uses_the_approved_template_when_set(db, sent, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "slack_webhook_url", "")
    monkeypatch.setattr(settings, "whatsapp_access_token", "token")
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "123")
    monkeypatch.setattr(settings, "whatsapp_recipient", "60123456789")
    monkeypatch.setattr(settings, "whatsapp_template", "review_waiting")
    _item(db)

    chat_notify.run_due(db)

    [(url, kwargs)] = sent
    assert url.endswith("/123/messages")
    assert kwargs["json"]["template"]["name"] == "review_waiting"


def test_only_the_owner_sends_a_test_and_unconfigured_channels_say_so(db, sent):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: principal(UserRole.OWNER_DIRECTOR)
    owner = TestClient(app)

    assert owner.post("/notifications/test", json={"channel": "slack"}).json()["status"] == "sent"
    assert owner.post("/notifications/test", json={"channel": "whatsapp"}).json()["status"] == (
        "not_configured"
    )
    channels = owner.get("/notifications/channels").json()["channels"]
    assert [(c["channel"], c["configured"]) for c in channels] == [
        ("slack", True),
        ("whatsapp", False),
    ]
    app.dependency_overrides[get_current_user] = lambda: principal(UserRole.FINANCE_OPS)
    assert TestClient(app).post("/notifications/test", json={"channel": "slack"}).status_code == 403
