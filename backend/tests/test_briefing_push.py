import dataclasses
import datetime as dt
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models import AuthUserRole, Base, Tenant, WorkflowAuditEntry
from app.routes.assistant import router
from app.schemas import UserRole
from app.security import rate_limit
from app.services import briefing_push
from tests.auth_support import TENANT_A, principal


@pytest.fixture
def sent(monkeypatch):
    outbox: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        briefing_push, "_send_email", lambda to, subject, body: outbox.append(("email", to, body))
    )
    monkeypatch.setattr(
        briefing_push, "_send_telegram", lambda chat, body: outbox.append(("telegram", chat, body))
    )
    rate_limit.reset()
    return outbox


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Tenant(id=str(TENANT_A), slug="tenant-a", name="Tenant A"))
    session.add(
        AuthUserRole(
            user_id=str(_owner().user_id),
            tenant_id=str(TENANT_A),
            user_role=UserRole.OWNER_DIRECTOR.value,
            job_functions=["owner"],
        )
    )
    session.commit()
    return session


def _owner():
    person = principal(UserRole.OWNER_DIRECTOR)
    if "job_functions" in getattr(type(person), "__dataclass_fields__", {}):
        person = dataclasses.replace(
            person, job_functions=("owner",), aal="aal2", mfa_verified_at=dt.datetime.now(dt.UTC)
        )
    return person


def _client(db) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = _owner
    return TestClient(app)


def test_pushes_are_off_until_the_person_opts_in(db, sent):
    client = _client(db)

    assert client.get("/assistant/briefing/preferences").json() == {
        "email": False,
        "telegram": False,
    }
    assert briefing_push.run_due(db, dt.datetime(2026, 10, 12, 8, 0)) == 0
    assert sent == []


def test_opted_in_person_gets_one_push_per_channel_each_morning(db, sent):
    client = _client(db)
    saved = client.put(
        "/assistant/briefing/preferences", json={"email": True, "telegram_chat_id": "123456789"}
    ).json()
    assert saved == {"email": True, "telegram": True}

    morning = dt.datetime(2026, 10, 12, 8, 0)
    assert briefing_push.run_due(db, morning) == 2
    assert briefing_push.run_due(db, morning + dt.timedelta(minutes=5)) == 0
    assert briefing_push.run_due(db, dt.datetime(2026, 10, 12, 14, 0)) == 0

    channels = sorted(channel for channel, _, _ in sent)
    assert channels == ["email", "telegram"]
    assert all("Sign in to DuitDuit" in body for _, _, body in sent)
    assert all("RM29,440.00" not in body for _, _, body in sent)


def test_people_removed_from_the_team_get_no_push(db, sent):
    _client(db).put(
        "/assistant/briefing/preferences", json={"email": True, "telegram_chat_id": None}
    )
    db.delete(db.get(AuthUserRole, (str(_owner().user_id), str(TENANT_A))))
    db.commit()

    assert briefing_push.run_due(db, dt.datetime(2026, 10, 12, 8, 0)) == 0
    assert sent == []


def test_deactivated_people_get_no_push(db, sent):
    _client(db).put(
        "/assistant/briefing/preferences", json={"email": True, "telegram_chat_id": None}
    )
    db.get(AuthUserRole, (str(_owner().user_id), str(TENANT_A))).active = False
    db.commit()

    assert briefing_push.run_due(db, dt.datetime(2026, 10, 12, 8, 0)) == 0
    assert sent == []


def test_telegram_id_is_stored_encrypted(db, sent):
    _client(db).put(
        "/assistant/briefing/preferences", json={"email": False, "telegram_chat_id": "987654321"}
    )

    payloads = [
        json.dumps(row.event_payload) for row in db.scalars(select(WorkflowAuditEntry)).all()
    ]
    assert not any("987654321" in payload for payload in payloads)


def test_send_now_goes_only_to_the_person_asking(db, sent):
    client = _client(db)
    client.put("/assistant/briefing/preferences", json={"email": True, "telegram_chat_id": None})

    result = client.post("/assistant/briefing/send-now").json()

    assert result == {"sent": ["email"]}
    assert sent[0][1] == _owner().email


def test_bad_telegram_ids_are_refused(db, sent):
    response = _client(db).put(
        "/assistant/briefing/preferences", json={"email": False, "telegram_chat_id": "@me"}
    )

    assert response.status_code == 422
