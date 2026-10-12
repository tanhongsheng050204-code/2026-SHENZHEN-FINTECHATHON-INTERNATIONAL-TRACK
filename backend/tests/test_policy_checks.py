"""The checker agent: every proposal is checked against company policy before a person decides."""

from decimal import Decimal

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.contracts.common import AutonomyLevel, EvidenceRef, JobFunction
from app.db import get_db
from app.schemas import UserRole
from app.services import review_inbox
from tests.auth_support import TENANT_A, principal
from tests.test_collections_board import live_db  # noqa: F401


def _client(db, role=UserRole.FINANCE_OPS) -> TestClient:
    from app.routes.collaboration import router as collab
    from app.routes.insights import router

    app = FastAPI()
    app.include_router(router)
    app.include_router(collab)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: principal(role)
    return TestClient(app)


def _propose(db, **kw):
    defaults = dict(
        agent_id="receivables",
        reviewer=JobFunction.FINANCE,
        level=AutonomyLevel.L2,
        title="Payment reminder for INV-1",
        summary="One reminder.",
        amount=Decimal("24500.00"),
        evidence=[EvidenceRef(label="Receivable record", source="pipeline:1")],
    )
    return review_inbox.propose(db, str(TENANT_A), **{**defaults, **kw})


def _checks(db, action_id, role=UserRole.FINANCE_OPS):
    response = _client(db, role).get(f"/insights/checks/{action_id}")
    assert response.status_code == 200, response.text
    return {c["name"]: c for c in response.json()["checks"]}


def test_a_clean_proposal_passes_every_check(live_db):  # noqa: F811
    checks = _checks(live_db, _propose(live_db, amount=Decimal("5000.00")))

    assert {c["status"] for c in checks.values()} == {"pass"}
    assert set(checks) >= {"evidence", "owner_escalation", "two_person_rule", "holds", "anomalies"}


def test_a_reminder_for_an_invoice_on_hold_is_a_failure(live_db):  # noqa: F811
    action_id = _propose(live_db)
    _client(live_db).put("/collections/holds/pipeline:1", json={"kind": "disputed"})

    holds = _checks(live_db, action_id)["holds"]
    assert holds["status"] == "fail"
    assert "disputed" in holds["detail"]


def test_a_large_item_for_finance_alone_should_reach_the_owner(live_db):  # noqa: F811
    # The company's owner escalation amount is RM20,000.00.
    check = _checks(live_db, _propose(live_db))["owner_escalation"]
    assert check["status"] == "warn"
    assert "RM20,000.00" in check["detail"]


def test_a_payment_below_two_approvals_is_a_failure(live_db):  # noqa: F811
    action_id = _propose(
        live_db,
        agent_id="payables",
        title="Pay supplier bill BILL-9",
        level=AutonomyLevel.L2,
        amount=Decimal("8000.00"),
        evidence=[EvidenceRef(label="Bill", source="payable:9")],
    )
    assert _checks(live_db, action_id)["two_person_rule"]["status"] == "fail"


def test_a_proposal_without_evidence_is_a_warning(live_db):  # noqa: F811
    action_id = _propose(live_db, amount=None, evidence=[], title="Look at this")
    assert _checks(live_db, action_id)["evidence"]["status"] == "warn"


def test_only_people_who_can_see_the_item_get_its_checks(live_db):  # noqa: F811
    action_id = _propose(live_db)
    staff = _client(live_db, UserRole.GENERAL_EMPLOYEE).get(f"/insights/checks/{action_id}")
    assert staff.status_code == 404
    assert _client(live_db).get("/insights/checks/act_missing").status_code == 404
