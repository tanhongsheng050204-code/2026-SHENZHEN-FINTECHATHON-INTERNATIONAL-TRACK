"""DuitDuit over MCP: read-only tools behind a revocable company key."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models import Base, Tenant, WorkflowAuditEntry
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
