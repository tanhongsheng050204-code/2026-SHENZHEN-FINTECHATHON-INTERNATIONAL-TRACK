"""Regression coverage for cookie sessions and persistent business imports.

Supabase responses are mocked; no provider emails or external model calls occur.
"""

from dataclasses import replace
from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, Response
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.provider import provider
from app.auth.sessions import COOKIE, accept_tokens, create_session, credentials, token_claims
from app.config import get_settings
from app.contracts.customization import ImportMappingRequest
from app.db import get_db
from app.models import Base, PayrollLine, Tenant, TokenizedContent, TokenVaultEntry, utcnow
from app.routes.auth import router as auth_router
from app.schemas import UserRole
from app.services.business_imports import authorize, commit_import, prepare
from app.services.import_mappings import save
from seed.topic_e import datasets
from tests.auth_support import principal


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


@pytest.fixture
def auth_client(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_cookie_secure", False)
    app = FastAPI()
    app.include_router(auth_router)
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client


def test_session_reads_preserve_csrf_across_tabs(db, auth_client):
    response = Response()
    _, csrf = create_session(db, response, {"email": "fake@example.invalid"}, "invite")
    db.commit()
    handle = response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    auth_client.cookies.set(COOKIE, handle)
    for _ in range(3):
        result = auth_client.get("/auth/session")
        assert result.status_code == 200
        assert result.json()["csrf_token"] == csrf
        assert result.headers["cache-control"] == "no-store"
    result = auth_client.post(
        "/auth/email/verify",
        json={"code": "123456"},
        headers={"origin": "https://evil.invalid", "x-csrf-token": csrf},
    )
    assert result.status_code == 403
    assert result.json()["detail"] == "csrf_origin_denied"


def test_token_refresh_and_mfa_preserve_session_csrf(db, monkeypatch):
    user_id = str(uuid4())
    monkeypatch.setattr(
        "app.auth.sessions._verified", lambda _: {"sub": user_id, "email": "fake@example.invalid"}
    )
    row, csrf = create_session(db, Response(), {"email": "fake@example.invalid"}, "signin")
    accept_tokens(
        row,
        {"access_token": "fictional", "refresh_token": "fictional", "expires_at": 0},
        email="fake@example.invalid",
    )
    monkeypatch.setattr(
        provider, "call", lambda *a, **kw: {"access_token": "fictional", "refresh_token": "next"}
    )
    token_claims(row)
    assert credentials(row)["csrf_token"] == csrf


@pytest.mark.parametrize(
    "mfa_age,allowed", [(None, False), (-30, False), (99999, False), (1, True)]
)
def test_recovery_requires_recent_mfa_for_enrolled_account(
    db, auth_client, monkeypatch, mfa_age, allowed
):
    user_id = str(uuid4())
    monkeypatch.setattr(
        "app.auth.sessions._verified",
        lambda _: {"sub": user_id, "email": "fake@example.invalid", "aal": "aal2"},
    )
    response = Response()
    row, csrf = create_session(db, response, {"email": "fake@example.invalid"}, "recovery")
    accept_tokens(row, {"access_token": "fictional"}, email="fake@example.invalid")
    row.email_verified = True
    row.mfa_verified_at = utcnow() - timedelta(seconds=mfa_age) if mfa_age is not None else None
    db.commit()
    writes = []

    def call(method, path, **kw):
        if method == "GET" and path == "/user":
            return {"factors": [{"factor_type": "totp", "status": "verified"}]}
        assert method == "PUT" and path == "/user"
        writes.append(path)
        return {}

    monkeypatch.setattr(provider, "call", call)
    auth_client.cookies.set(
        COOKIE, response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
    )
    result = auth_client.post(
        "/auth/password",
        json={"password": "Fictional-Review-Password9!"},
        headers={"origin": "http://localhost:5173", "x-csrf-token": csrf},
    )
    assert result.status_code == (200 if allowed else 403)
    assert len(writes) == int(allowed)
    if allowed:
        assert row.mfa_verified_at is None


def test_all_import_schemas_replay_and_payroll_stays_out_of_search(db):
    owner = principal(UserRole.OWNER_DIRECTOR)
    tenant_id = str(owner.tenant_id)
    db.add(Tenant(id=tenant_id, name="Synthetic regression", slug="synthetic-regression"))
    db.flush()
    for schema, (headers, columns, csv_text) in datasets(date(2026, 10, 9)).items():
        mapping = save(
            db,
            owner,
            ImportMappingRequest(
                schema_name=schema, name="Synthetic mapping", headers=headers, column_map=columns
            ),
        )
        preview = prepare(db, owner, schema, csv_text, mapping.id).preview
        assert preview.can_commit, preview.issues
        first = commit_import(db, owner, schema, csv_text, mapping.id)
        second = commit_import(db, owner, schema, csv_text, mapping.id)
        assert first.imported_rows > 0
        assert second.replayed
        assert second.imported_rows == 0
    lines = db.scalars(select(PayrollLine)).all()
    assert lines
    employee_tokens = {line.employee_token for line in lines}
    search_text = " ".join(db.scalars(select(TokenizedContent.content_text)))
    assert not any(token in search_text for token in employee_tokens)
    vault = db.scalars(
        select(TokenVaultEntry).where(TokenVaultEntry.token.in_(employee_tokens))
    ).all()
    assert vault and all(row.data_class == "employee_personal" for row in vault)


def test_import_mappings_cannot_be_reused_across_tenants(db):
    owner = principal(UserRole.OWNER_DIRECTOR)
    other = replace(owner, tenant_id=uuid4())
    for number, actor in enumerate((owner, other)):
        db.add(Tenant(id=str(actor.tenant_id), name="Synthetic", slug=f"synthetic-{number}"))
    db.flush()
    schema = "bank_statement_v1"
    headers, columns, csv_text = datasets(date(2026, 10, 9))[schema]
    mapping = save(
        db,
        owner,
        ImportMappingRequest(
            schema_name=schema, name="Synthetic mapping", headers=headers, column_map=columns
        ),
    )
    preview = prepare(db, other, schema, csv_text, mapping.id).preview
    assert not preview.can_commit
    assert preview.issues[0].code == "mapping_not_found_or_headers_changed"


def test_finance_assignment_does_not_grant_payroll_import():
    finance = replace(principal(UserRole.FINANCE_OPS), job_functions=("finance",))
    with pytest.raises(HTTPException) as error:
        authorize(finance, "payroll_v1")
    assert error.value.status_code == 403
    authorize(replace(finance, job_functions=("finance", "hr")), "payroll_v1")
