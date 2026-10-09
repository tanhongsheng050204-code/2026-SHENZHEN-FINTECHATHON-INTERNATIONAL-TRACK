import datetime as dt
import json
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.contracts.passports import Passport, passport_digest
from app.db import get_db
from app.models import Base, Tenant, WorkflowAuditEntry
from app.routes.passports_live import router
from app.schemas import UserRole
from app.services import external_grants, passports
from tests.auth_support import TENANT_A, TENANT_B, principal


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Tenant(id=str(TENANT_A), slug="tenant-a", name="Tenant A Trading"))
    session.add(Tenant(id=str(TENANT_B), slug="tenant-b", name="Tenant B Trading"))
    session.commit()
    return session


def _client(db, role=UserRole.OWNER_DIRECTOR, tenant: UUID = TENANT_A) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    if role is not None:
        app.dependency_overrides[get_current_user] = lambda: principal(role, tenant_id=tenant)
    return TestClient(app)


def _issue(db) -> dict:
    response = _client(db).post("/passports")
    assert response.status_code == 200
    return response.json()["passport"]


def test_issued_passport_is_recorded_on_the_audit_chain(db):
    issued = _issue(db)

    entry = db.get(WorkflowAuditEntry, issued["audit_entry_id"])
    assert entry.event_type == "passport_issued"
    assert entry.tenant_id == str(TENANT_A)
    assert entry.event_payload["sha256"] == issued["sha256"]
    assert passport_digest(Passport.model_validate(issued)) == issued["sha256"]
    assert issued["company_label"].startswith("Tenant A Trading")
    keys = [m["key"] for m in issued["metrics"]]
    assert keys == [
        "cash_flow_health",
        "annual_revenue",
        "receivables_quality",
        "validated_einvoice_share",
        "customer_concentration",
        "data_completeness",
        "compliance_status",
    ]
    listed = _client(db, UserRole.FINANCE_OPS).get("/passports").json()["passports"]
    assert [p["id"] for p in listed] == [issued["id"]]
    second = _issue(db)
    assert second["version"] == 2


def test_verification_names_the_changed_field_and_checks_the_chain(db):
    issued = _issue(db)
    public = _client(db, role=None)

    ok = public.post("/lender/verify", json=issued).json()
    assert (ok["status"], ok["chain_intact"], ok["mismatched_fields"]) == ("verified", True, [])

    tampered = json.loads(json.dumps(issued))
    tampered["metrics"][2]["value"] = "0%"
    bad = public.post("/lender/verify", json=tampered).json()
    assert bad["status"] == "mismatch"
    assert bad["mismatched_fields"] == ["receivables_quality"]

    unknown = public.post("/lender/verify", json={**issued, "id": "pp_never"}).json()
    assert unknown["status"] == "unknown_passport"

    entry = db.get(WorkflowAuditEntry, issued["audit_entry_id"])
    entry.event_payload = {**entry.event_payload, "sha256": "0" * 64}
    db.commit()
    broken = public.post("/lender/verify", json=issued).json()
    assert broken["chain_intact"] is False


def test_lender_link_works_until_revoked_and_every_view_is_audited(db):
    issued = _issue(db)
    owner = _client(db)
    grant = owner.post(
        f"/passports/{issued['id']}/grants",
        json={"grantee_email": "credit@bank.example", "expires_in_days": 7},
    ).json()["grant"]
    assert "credit@bank.example" not in json.dumps(grant)

    public = _client(db, role=None)
    seen = public.get(grant["share_path"])
    assert seen.status_code == 200
    assert seen.json()["passport"]["sha256"] == issued["sha256"]
    events = db.scalars(select(WorkflowAuditEntry.event_type)).all()
    assert "external_grant_viewed" in events
    assert not any(
        "credit@bank.example" in json.dumps(row.event_payload)
        for row in db.scalars(select(WorkflowAuditEntry))
    )

    revoked = owner.delete(f"/passports/{issued['id']}/grants/{grant['id']}").json()["grant"]
    assert revoked["status"] == "revoked"
    gone = public.get(grant["share_path"])
    assert (gone.status_code, gone.json()["detail"]) == (410, "grant_revoked")
    listed = owner.get(f"/passports/{issued['id']}/grants").json()["grants"]
    assert [g["status"] for g in listed] == ["revoked"]


def test_expired_and_forged_links_are_refused(db, monkeypatch):
    issued = _issue(db)
    grant = (
        _client(db)
        .post(
            f"/passports/{issued['id']}/grants",
            json={"grantee_email": "credit@bank.example", "expires_in_days": 1},
        )
        .json()["grant"]
    )
    public = _client(db, role=None)

    later = dt.datetime.now(dt.UTC) + dt.timedelta(days=2)
    monkeypatch.setattr(external_grants, "_now", lambda: later)
    expired = public.get(grant["share_path"])
    assert (expired.status_code, expired.json()["detail"]) == (410, "grant_expired")

    token = grant["share_path"].rsplit("/", 1)[1]
    forged = token[:-1] + ("0" if token[-1] != "0" else "1")
    assert public.get(f"/lender/passports/{forged}").status_code == 404
    assert public.get("/lender/passports/demo-grant-token").status_code == 404


def test_another_tenant_cannot_see_or_share_the_passport(db):
    issued = _issue(db)
    other = _client(db, tenant=TENANT_B)

    assert other.get(f"/passports/{issued['id']}").status_code == 404
    assert other.get("/passports").json()["passports"] == []
    shared = other.post(
        f"/passports/{issued['id']}/grants",
        json={"grantee_email": "x@bank.example", "expires_in_days": 1},
    )
    assert shared.status_code == 404


def test_audit_pack_is_hashed_recorded_and_shared_with_an_auditor(db):
    finance = _client(db, UserRole.FINANCE_OPS)
    pack = finance.post("/audit-packs", json={"period": "2026-Q3"}).json()["pack"]

    assert pack["period"] == "2026-Q3"
    keys = [item["key"] for item in pack["items"]]
    assert keys == [
        "ledger_export",
        "einvoice_register",
        "reconciliation_status",
        "audit_chain_proof",
        "payroll_summary",
    ]
    assert "withheld" in pack["items"][-1]["description"]
    assert finance.get(f"/audit-packs/{pack['id']}").json()["pack"]["sha256"] == pack["sha256"]

    grant = (
        _client(db)
        .post(
            f"/audit-packs/{pack['id']}/grants",
            json={"grantee_email": "audit@firm.example", "expires_in_days": 3},
        )
        .json()["grant"]
    )
    view = _client(db, role=None).get(grant["share_path"])
    assert view.status_code == 200
    assert view.json()["pack"]["sha256"] == pack["sha256"]


def test_only_the_owner_issues_and_shares(db):
    assert _client(db, UserRole.FINANCE_OPS).post("/passports").status_code == 403
    assert _client(db, UserRole.GENERAL_EMPLOYEE).get("/passports").status_code == 403


def test_anchor_is_reported_once_an_anchor_file_covers_the_entry(db, tmp_path, monkeypatch):
    issued = _issue(db)
    tail = db.scalar(
        select(WorkflowAuditEntry.event_hash)
        .where(WorkflowAuditEntry.tenant_id == str(TENANT_A))
        .order_by(WorkflowAuditEntry.id.desc())
    )
    (tmp_path / "2026-10-14.json").write_text(
        json.dumps(
            {
                "anchored_at": "2026-10-14T00:00:00+00:00",
                "anchors": [{"tenant_id": str(TENANT_A), "chain": "workflow", "tail_hash": tail}],
            }
        )
    )
    monkeypatch.setattr(passports, "anchor_dir", lambda: tmp_path)

    result = _client(db, role=None).post("/lender/verify", json=issued).json()

    assert result["anchor"]["repository_path"] == "audit-anchors/2026-10-14.json"


def test_verification_is_not_an_oracle_for_someone_without_the_document(db):
    issued = _issue(db)
    guess = {**issued, "sha256": "0" * 64}
    guess["metrics"] = [{**m, "value": "50%"} for m in issued["metrics"]]

    result = _client(db, role=None).post("/lender/verify", json=guess).json()

    assert result["status"] == "mismatch"
    assert result["expected_sha256"] is None
    assert result["mismatched_fields"] == ["sha256"]
    assert result["anchor"] is None


def test_grantee_is_recorded_as_a_grant_only_reference(db):
    from app.security.tokenize import derive_token

    issued = _issue(db)
    grant = (
        _client(db)
        .post(
            f"/passports/{issued['id']}/grants",
            json={"grantee_email": "credit@bank.example", "expires_in_days": 7},
        )
        .json()["grant"]
    )

    reference = grant["grantee_email_token"]
    assert reference.startswith("GRANTEE_")
    assert reference != derive_token("EMAIL", "credit@bank.example", str(TENANT_A))
