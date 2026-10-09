import dataclasses
import datetime as dt
import re

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.contracts.passports import GrantRequest
from app.db import get_db
from app.models import Base, Tenant
from app.routes.assistant import router
from app.schemas import UserRole
from app.services import briefing, external_grants
from tests.auth_support import TENANT_A, principal

JOBS = {
    UserRole.OWNER_DIRECTOR: ("owner",),
    UserRole.FINANCE_OPS: ("finance", "hr"),
    UserRole.COMPLIANCE: ("compliance",),
    UserRole.GENERAL_EMPLOYEE: ("sales", "customer_service"),
}


def _person(role: UserRole):
    person = principal(role)
    if "job_functions" in getattr(type(person), "__dataclass_fields__", {}):
        person = dataclasses.replace(
            person, job_functions=JOBS[role], aal="aal2", mfa_verified_at=dt.datetime.now(dt.UTC)
        )
    return person


def _brief(role=UserRole.OWNER_DIRECTOR, db=None) -> dict:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: _person(role)
    response = TestClient(app).get("/assistant/briefing")
    assert response.status_code == 200, response.text
    return response.json()


def _database() -> Session:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(Tenant(id=str(TENANT_A), slug="tenant-a", name="Tenant A"))
    db.commit()
    return db


def test_owner_hears_about_cash_and_what_is_waiting():
    lines = {line["kind"]: line for line in _brief()["lines"]}

    assert lines["cash"]["tone"] == "risk"
    assert "day 23" in lines["cash"]["text"]
    assert "RM29,440.00" in lines["cash"]["text"]
    assert lines["cash"]["screen"] == "cashflow"
    assert re.search(r"\d+ items? waiting for you", lines["inbox"]["text"])


def test_staff_get_no_cash_line_and_only_their_own_items():
    lines = {line["kind"]: line for line in _brief(UserRole.GENERAL_EMPLOYEE)["lines"]}

    assert "cash" not in lines
    assert "inbox" in lines


def test_pushed_briefings_carry_ranges_and_counts_only():
    text = briefing.push_text(None, _person(UserRole.OWNER_DIRECTOR))

    assert "day 23" not in text
    assert not re.search(r"RM[\d,]+\.\d\d", text)
    assert "about 3 weeks" in text or "this week" in text or "next week" in text
    assert "Sign in to DuitDuit" in text


def test_owner_is_reminded_of_share_links_about_to_expire():
    db = _database()
    owner = _person(UserRole.OWNER_DIRECTOR)
    external_grants.create(
        db, owner, "lender", "pp_x", GrantRequest(grantee_email="a@bank.example", expires_in_days=1)
    )

    lines = {line["kind"]: line for line in _brief(db=db)["lines"]}

    assert "expire" in lines["sharing"]["text"]
    assert lines["sharing"]["screen"] == "financing"
