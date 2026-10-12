"""PDPA data portability: one customer's records as a machine-readable file, for Compliance."""

from sqlalchemy import select

from app.models import WorkflowAuditEntry
from app.routes.privacy import router as privacy_router
from app.schemas import UserRole
from tests.auth_support import principal
from tests.test_collections_board import live_db  # noqa: F401  (fixture)


def _client(db, role=UserRole.COMPLIANCE):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.auth.dependencies import get_current_user
    from app.db import get_db

    app = FastAPI()
    app.include_router(privacy_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: principal(role)
    return TestClient(app)


def test_compliance_exports_a_customers_records_in_a_stable_format(live_db):  # noqa: F811
    response = _client(live_db).post("/privacy/customers/7/export")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["format"] == "duitduit-portability-v1"
    assert body["subject"]["kind"] == "customer" and body["subject"]["id"] == 7
    assert sorted(r["reference"] for r in body["receivables"]) == [
        "t1:INV-1",
        "t1:INV-2",
        "t1:INV-3",
        "t1:INV-4",
        "t1:INV-5",
    ]
    first = next(r for r in body["receivables"] if r["reference"] == "t1:INV-1")
    assert set(first) == {"reference", "amount", "currency", "due_date", "status"}
    assert response.headers["content-disposition"].startswith("attachment;")


def test_an_export_is_recorded_by_kind_and_id_only(live_db):  # noqa: F811
    _client(live_db).post("/privacy/customers/7/export")

    event = live_db.scalar(
        select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "data_export_prepared")
    )
    assert event.event_payload == {
        "subject_kind": "customer",
        "subject_id": 7,
        "sections": ["identity", "contacts", "receivables", "einvoices"],
    }


def test_only_compliance_exports_and_only_its_own_customers(live_db):  # noqa: F811
    assert (
        _client(live_db, UserRole.OWNER_DIRECTOR).post("/privacy/customers/7/export").status_code
        == 403
    )
    assert (
        _client(live_db, UserRole.FINANCE_OPS).post("/privacy/customers/7/export").status_code
        == 403
    )
    assert _client(live_db).post("/privacy/customers/999/export").status_code == 404
