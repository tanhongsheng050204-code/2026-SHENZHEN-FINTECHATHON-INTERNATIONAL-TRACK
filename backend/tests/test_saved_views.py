"""Saved views: filters only, private or shared, removed by their owner."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models import Base, Tenant, WorkflowAuditEntry
from app.routes.collaboration import router
from app.schemas import UserRole
from tests.auth_support import TENANT_A, principal

OVERDUE = {
    "screen": "customers",
    "filters": {"priorities": ["urgent", "high"], "min_overdue": "10000"},
    "shared": True,
}


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


def _client(db, role=UserRole.FINANCE_OPS) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: principal(role)
    return TestClient(app)


def _views(client, screen="customers"):
    return client.get("/saved-views", params={"screen": screen}).json()["views"]


def test_a_shared_view_is_seen_by_the_team_and_a_private_one_only_by_its_owner(db):
    finance = _client(db)
    finance.post("/saved-views", json=OVERDUE)
    finance.post("/saved-views", json={**OVERDUE, "shared": False})

    assert len(_views(finance)) == 2
    seen = _views(_client(db, UserRole.GENERAL_EMPLOYEE))
    assert len(seen) == 1 and seen[0]["mine"] is False
    assert seen[0]["filters"]["priorities"] == ["urgent", "high"]


def test_free_text_is_not_accepted(db):
    response = _client(db).post(
        "/saved-views",
        json={**OVERDUE, "filters": {"priorities": ["urgent"], "name": "Ali's late payers"}},
    )
    assert response.status_code == 200
    event = db.scalar(
        select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "saved_view_saved")
    )
    assert "Ali" not in str(event.event_payload)


def test_only_its_author_or_the_owner_removes_a_shared_view(db):
    view_id = _client(db).post("/saved-views", json=OVERDUE).json()["id"]

    assert (
        _client(db, UserRole.GENERAL_EMPLOYEE).delete(f"/saved-views/{view_id}").status_code == 403
    )
    assert _client(db, UserRole.OWNER_DIRECTOR).delete(f"/saved-views/{view_id}").status_code == 204
    assert _views(_client(db)) == []


def test_someone_elses_private_view_does_not_exist_for_you(db):
    view_id = _client(db).post("/saved-views", json={**OVERDUE, "shared": False}).json()["id"]

    assert _client(db, UserRole.OWNER_DIRECTOR).delete(f"/saved-views/{view_id}").status_code == 404


def test_board_views_follow_the_board_access(db):
    view = {"screen": "collections", "filters": {"stages": ["overdue"]}, "shared": True}

    assert _client(db).post("/saved-views", json=view).status_code == 200
    employee = _client(db, UserRole.GENERAL_EMPLOYEE)
    assert employee.get("/saved-views", params={"screen": "collections"}).status_code == 403
