"""DuitDuit over MCP: read-only tools behind a revocable company key."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models import AuthUserRole, Base, Tenant, WorkflowAuditEntry
from app.routes.collaboration import router as keys_router
from app.routes.mcp import router as mcp_router
from app.schemas import UserRole
from app.security import rate_limit
from tests.auth_support import TENANT_A, principal


@pytest.fixture
def db():
    rate_limit.reset()
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Tenant(id=str(TENANT_A), slug="tenant-a", name="Tenant A"))
    owner = principal(UserRole.OWNER_DIRECTOR)
    session.add(
        AuthUserRole(
            user_id=str(owner.user_id),
            tenant_id=str(TENANT_A),
            user_role="owner_director",
            job_functions=["owner"],
            active=True,
        )
    )
    session.commit()
    return session


def _app(db, role=UserRole.OWNER_DIRECTOR) -> TestClient:
    app = FastAPI()
    app.include_router(keys_router)
    app.include_router(mcp_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: principal(role)
    return TestClient(app)


def _key(db) -> str:
    return _app(db).post("/api-keys").json()["secret"]


def _rpc(client, key, method, params=None, request_id=1):
    return client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {key}"},
        json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}},
    )


def test_an_ai_tool_initialises_lists_and_calls_the_tools(db):
    key, client = _key(db), _app(db)

    hello = _rpc(client, key, "initialize", {"protocolVersion": "2025-06-18"}).json()
    assert hello["result"]["serverInfo"]["name"] == "duitduit"
    names = [t["name"] for t in _rpc(client, key, "tools/list").json()["result"]["tools"]]
    assert names == [
        "get_cash_forecast",
        "get_forecast_check",
        "get_review_inbox",
        "get_collections_board",
        "get_financing_matches",
    ]

    result = _rpc(
        client, key, "tools/call", {"name": "get_cash_forecast", "arguments": {"horizon_days": 90}}
    ).json()["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["data_mode"] == "stub"
    assert result["structuredContent"]["shortfall"]["gap"] == "29440.00"


def test_every_tool_answers(db):
    key, client = _key(db), _app(db)
    for name in (
        "get_forecast_check",
        "get_review_inbox",
        "get_collections_board",
        "get_financing_matches",
    ):
        result = _rpc(client, key, "tools/call", {"name": name}).json()["result"]
        assert result["isError"] is False, name


def test_a_call_is_recorded_by_tool_name_and_key_only(db):
    key, client = _key(db), _app(db)
    _rpc(client, key, "tools/call", {"name": "get_review_inbox"})

    event = db.scalar(
        select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "mcp_tool_called")
    )
    assert event.event_payload == {"tool": "get_review_inbox"}
    assert event.resource_id == key.split("_")[1]


def test_bad_or_revoked_keys_are_refused(db):
    key, client = _key(db), _app(db)
    assert _rpc(client, "ddk_000000000000_" + "x" * 40, "tools/list").status_code == 401
    assert (
        _rpc(client, key[:-1] + ("A" if key[-1] != "A" else "B"), "tools/list").status_code == 401
    )
    assert _rpc(client, "", "tools/list").status_code == 401

    key_id = key.split("_")[1]
    assert client.delete(f"/api-keys/{key_id}").status_code == 204
    assert _rpc(client, key, "tools/list").status_code == 401


def test_the_key_is_shown_once_and_only_its_hmac_is_kept(db):
    key = _key(db)
    listed = _app(db).get("/api-keys").json()["keys"]

    assert [k["id"] for k in listed] == [key.split("_")[1]]
    assert key not in str(listed)
    stored = db.scalar(
        select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "api_key_created")
    )
    assert key not in str(stored.event_payload)


def test_only_the_owner_manages_keys(db):
    finance = _app(db, UserRole.FINANCE_OPS)
    assert finance.post("/api-keys").status_code == 403
    assert finance.get("/api-keys").status_code == 403


def test_unknown_tools_and_methods_are_json_rpc_errors(db):
    key, client = _key(db), _app(db)
    assert _rpc(client, key, "tools/call", {"name": "send_money"}).json()["error"]["code"] == -32602
    assert _rpc(client, key, "resources/write").json()["error"]["code"] == -32601
    notice = client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {key}"},
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    assert notice.status_code == 202


def test_a_key_stops_working_when_its_owner_is_no_longer_an_owner(db):
    key, client = _key(db), _app(db)
    assert _rpc(client, key, "tools/list").status_code == 200

    db.get(
        AuthUserRole, (str(principal(UserRole.OWNER_DIRECTOR).user_id), str(TENANT_A))
    ).user_role = "finance_ops"
    db.commit()
    assert _rpc(client, key, "tools/list").status_code == 401


def test_guessing_keys_is_rate_limited_before_any_key_is_checked(db):
    client = _app(db)
    codes = {_rpc(client, "ddk_000000000000_" + "x" * 40, "ping").status_code for _ in range(125)}
    assert 429 in codes


def test_a_batch_cannot_carry_more_than_ten_messages(db):
    key, client = _key(db), _app(db)
    batch = [{"jsonrpc": "2.0", "id": n, "method": "ping"} for n in range(11)]
    response = client.post("/mcp", headers={"Authorization": f"Bearer {key}"}, json=batch)
    assert response.status_code == 400


def test_a_key_can_be_limited_to_some_tools(db):
    client = _app(db)
    made = client.post(
        "/api-keys", json={"tools": ["get_cash_forecast", "get_review_inbox"]}
    ).json()
    key = made["secret"]
    assert made["key"]["tools"] == ["get_cash_forecast", "get_review_inbox"]

    names = [t["name"] for t in _rpc(client, key, "tools/list").json()["result"]["tools"]]
    assert names == ["get_cash_forecast", "get_review_inbox"]
    refused = _rpc(client, key, "tools/call", {"name": "get_financing_matches"}).json()
    assert refused["error"] == {"code": -32602, "message": "Tool not allowed for this key"}


def test_a_key_expires(db, monkeypatch):
    import datetime as dt

    from app.services import api_keys

    client = _app(db)
    made = client.post("/api-keys", json={"expires_in_days": 30}).json()
    created = dt.datetime.fromisoformat(made["key"]["created_at"])
    expires = dt.datetime.fromisoformat(made["key"]["expires_at"])
    assert (expires - created).days == 30
    assert _rpc(client, made["secret"], "ping").status_code == 200

    monkeypatch.setattr(api_keys, "_now", lambda: created + dt.timedelta(days=31))
    assert _rpc(client, made["secret"], "ping").status_code == 401
    assert client.get("/api-keys").json()["keys"][0]["expired"] is True


def test_a_new_key_reads_every_tool_for_ninety_days_by_default(db):
    import datetime as dt

    made = _app(db).post("/api-keys").json()["key"]
    assert len(made["tools"]) == 5
    span = dt.datetime.fromisoformat(made["expires_at"]) - dt.datetime.fromisoformat(
        made["created_at"]
    )
    assert span.days == 90


def test_key_choices_are_checked(db):
    client = _app(db)
    assert client.post("/api-keys", json={"tools": []}).status_code == 422
    assert client.post("/api-keys", json={"tools": ["send_money"]}).status_code == 422
    assert client.post("/api-keys", json={"expires_in_days": 7}).status_code == 422


def test_the_owner_sees_when_a_key_was_last_used_and_for_what(db):
    key, client = _key(db), _app(db)
    assert client.get("/api-keys").json()["keys"][0]["last_used_at"] is None

    _rpc(client, key, "tools/call", {"name": "get_review_inbox"})
    _rpc(client, key, "tools/call", {"name": "get_collections_board"})

    [listed] = client.get("/api-keys").json()["keys"]
    assert listed["last_used_at"] is not None
    assert [call["tool"] for call in listed["recent_calls"]] == [
        "get_collections_board",
        "get_review_inbox",
    ]
