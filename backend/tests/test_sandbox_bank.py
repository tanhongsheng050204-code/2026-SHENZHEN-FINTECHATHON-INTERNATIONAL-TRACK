"""The simulated bank: an approved L3 payment executes once, on a sandbox ledger only."""

from decimal import Decimal

from sqlalchemy import select

from app.contracts.common import AutonomyLevel, JobFunction
from app.models import WorkflowAuditEntry
from app.schemas import UserRole
from app.services import review_inbox, sandbox_bank
from tests.auth_support import TENANT_A
from tests.test_review_inbox_live import _client, db  # noqa: F401


def _money_item(db, title="Pay supplier bill", level=AutonomyLevel.L3):  # noqa: F811
    return review_inbox.propose(
        db,
        str(TENANT_A),
        agent_id="payables",
        reviewer=JobFunction.FINANCE,
        title=title,
        summary="RM14,800.00 rent",
        amount=Decimal("14800.00"),
        level=level,
    )


def test_two_people_approve_and_the_payment_runs_once_in_the_simulated_bank(db):  # noqa: F811
    action_id = _money_item(db)
    owner, finance = _client(db), _client(db, UserRole.FINANCE_OPS)
    url = f"/review-inbox/{action_id}/decision"

    maker = finance.post(url, json={"decision": "approve"}).json()["action"]
    assert maker["status"] == "awaiting_second_approval" and maker["payment_reference"] is None
    assert sandbox_bank.payments(db, str(TENANT_A)) == []

    checker = owner.post(url, json={"decision": "approve"}).json()["action"]
    assert checker["status"] == "approved"
    assert checker["payment_reference"].startswith("SIM-")

    sandbox_bank.execute_if_due(db, str(TENANT_A), action_id)
    paid = sandbox_bank.payments(db, str(TENANT_A))
    assert [(p.action_id, p.amount, p.reference) for p in paid] == [
        (action_id, Decimal("14800.00"), checker["payment_reference"])
    ]
    listed = owner.get("/review-inbox").json()["actions"]
    assert next(a for a in listed if a["id"] == action_id)["payment_reference"] == paid[0].reference


def test_nothing_runs_when_rejected_half_approved_or_not_a_money_item(db):  # noqa: F811
    owner, finance = _client(db), _client(db, UserRole.FINANCE_OPS)
    rejected = _money_item(db, "Pay bill A")
    finance.post(f"/review-inbox/{rejected}/decision", json={"decision": "reject"})
    half = _money_item(db, "Pay bill B")
    finance.post(f"/review-inbox/{half}/decision", json={"decision": "approve"})
    reminder = _money_item(db, "Send reminder", AutonomyLevel.L2)
    owner.post(f"/review-inbox/{reminder}/decision", json={"decision": "approve"})

    for action_id in (rejected, half, reminder):
        assert sandbox_bank.execute_if_due(db, str(TENANT_A), action_id) is None
    assert sandbox_bank.payments(db, str(TENANT_A)) == []


def test_the_ledger_entry_names_ids_and_the_amount_never_the_words(db):  # noqa: F811
    action_id = _money_item(db, "Pay Ahmad Faizal for the van")
    _client(db, UserRole.FINANCE_OPS).post(
        f"/review-inbox/{action_id}/decision", json={"decision": "approve"}
    )
    _client(db).post(f"/review-inbox/{action_id}/decision", json={"decision": "approve"})

    row = db.scalar(
        select(WorkflowAuditEntry).where(
            WorkflowAuditEntry.event_type == sandbox_bank.EVENT
        )
    )
    assert set(row.event_payload) == {"action_id", "amount", "reference", "ledger"}
    assert "Ahmad" not in str(row.event_payload)
