import os

# Provider keys must be cleared before importing application modules.
# ruff: noqa: E402

os.environ.setdefault("ENABLE_GLINER", "false")
os.environ.setdefault("ALLOW_OFFLINE_DEMO", "true")
os.environ.setdefault("TOKEN_ROOT_SECRET", "test-secret-that-is-longer-than-32-characters")
os.environ["GEMINI_API_KEY"] = ""
os.environ["MORPHEUS_API_KEY"] = ""

import json
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest
from fastapi import Response
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.provider import provider
from app.auth.sessions import create_session
from app.models import (
    AuthUserRole,
    Base,
    ImportMappingRecord,
    SecurityGuardrailEvent,
    Tenant,
    TenantCustomization,
    TenantSettingsChange,
    TenantSettingsRecord,
    TenantSettingsVersion,
    utcnow,
)


@pytest.fixture(autouse=True)
def persistent_contract_state(request, monkeypatch):
    if not request.node.path.name.startswith("test_contract_"):
        yield
        return
    from app.schemas import UserRole
    from tests import contract_support
    from tests.auth_support import TENANT_A, USER_IDS

    tenant_id = str(TENANT_A)
    owner_id = str(USER_IDS[UserRole.OWNER_DIRECTOR])
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    fixture = json.loads(
        (Path(__file__).parent / "topic_e_persistent_fixture.json").read_text(encoding="utf-8")
    )
    db.add(Tenant(id=tenant_id, name="Synthetic Trading Co.", slug="contract-fixture"))
    for item in fixture["members"]:
        values = dict(item)
        values["user_role"] = values.pop("role")
        values["last_active_at"] = datetime.fromisoformat(values["last_active_at"])
        db.add(AuthUserRole(tenant_id=tenant_id, **values))
    for version, document in fixture["settings"].items():
        db.add(TenantSettingsVersion(tenant_id=tenant_id, version=int(version), document=document))
    current = fixture["settings"]["3"]
    db.add(TenantSettingsRecord(tenant_id=tenant_id, version=3, document=current))
    for number, item in enumerate(fixture["changes"]):
        proposed = deepcopy(current)
        if item["status"] == "pending_approval":
            proposed["security"]["mfa_required_roles"].append("general_employee")
        db.add(
            TenantSettingsChange(
                tenant_id=tenant_id,
                id=item["id"],
                area=item["area"],
                status=item["status"],
                requires_approval=item["requires_approval"],
                base_version=3,
                version=item["version"],
                proposed_document=proposed,
                preview=item["preview"],
                proposer_id=owner_id,
                created_at=utcnow() - timedelta(days=5 - number),
            )
        )
    for kind, key in (("message_template", "templates"), ("alert_rule", "rules")):
        for number, item in enumerate(fixture[key]):
            db.add(
                TenantCustomization(
                    tenant_id=tenant_id,
                    id=item["id"],
                    kind=kind,
                    document=item,
                    created_by=owner_id,
                    created_at=utcnow() + timedelta(seconds=number),
                )
            )
    db.add(ImportMappingRecord(tenant_id=tenant_id, created_by=owner_id, **fixture["mapping"]))
    for number in range(1, 5):
        db.add(
            SecurityGuardrailEvent(
                id=f"ge_{number}",
                tenant_id=tenant_id,
                owasp_code=("ASI01", "ASI03", "ASI09", "ASI01")[number - 1],
                title="Synthetic test event",
                detail="Persisted test fixture",
                outcome="blocked",
                occurred_at=utcnow() + timedelta(seconds=number),
            )
        )
    db.flush()
    for _ in range(2):
        session, _csrf = create_session(db, Response(), {"email": "fixture@example.test"}, "signin")
        session.user_id = str(USER_IDS[UserRole.GENERAL_EMPLOYEE])
        session.tenant_id = tenant_id
    db.commit()
    monkeypatch.setattr(contract_support, "ACTIVE_DB", db)

    def mocked_provider(method, path, **kwargs):
        assert method == "POST" and path == "/invite"
        return {"id": str(uuid5(NAMESPACE_URL, kwargs["payload"]["email"].casefold()))}

    monkeypatch.setattr(provider, "call", mocked_provider)
    try:
        yield
    finally:
        db.close()
        engine.dispose()
