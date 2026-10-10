import datetime as dt
import json
from dataclasses import replace
from decimal import Decimal

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.auth.dependencies import get_current_user
from app.contracts.common import DataMode, JobFunction
from app.db import get_db
from app.routes.agents_live import router as inbox_router
from app.routes.assistant import router
from app.schemas import UserRole
from app.services import assistant, external_grants, passports, playbooks, review_inbox
from app.services.cashflow_engine import CashBasis, Signal
from app.services.workflow_audit import verify_workflow_chain
from tests.auth_support import TENANT_A, TENANT_B, principal


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(
            [
                models.Tenant(id=str(TENANT_A), name="Synthetic tenant A", slug="tenant-a"),
                models.Tenant(id=str(TENANT_B), name="Tenant B", slug="tenant-b"),
            ]
        )
        session.commit()
        yield session
    engine.dispose()


def _client(db, role=UserRole.OWNER_DIRECTOR, tenant=TENANT_A):
    app = FastAPI()
    app.include_router(router)
    app.include_router(inbox_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: principal(role, tenant)
    return TestClient(app)


def _run(db, name, role=UserRole.OWNER_DIRECTOR):
    response = _client(db, role).post(f"/assistant/playbooks/{name}")
    assert response.status_code == 200, response.text
    return response.json()


def _steps(result):
    return {step["label"]: step for step in result["steps"]}


def _actions(db):
    return [item.action for item in review_inbox._replay(db, str(TENANT_A)).values()]


def test_bank_meeting_prepares_forecast_profile_and_l2_share_proposal(db):
    result = _run(db, "bank_meeting", UserRole.FINANCE_OPS)
    steps = _steps(result)
    assert "day 23" in steps["Cash forecast"]["text"].lower()
    assert "RM20,560.00" in steps["Cash forecast"]["text"]
    assert "RM29,440.00" in steps["Cash forecast"]["text"]
    assert "Annual revenue" in steps["Financing profile"]["text"]
    assert steps["Missing facts"]["status"] == "done"
    assert result["synthetic"] is True
    assert result["next_screen"] == "financing"
    action = _actions(db)[0]
    assert action.id in result["inbox_item_ids"]
    assert action.autonomy_level == "L2"
    assert action.status == "pending"
    assert "No link" in action.summary
    assert external_grants.list_for(db, str(TENANT_A), "lender", "pp_x") == []
    assert passports.list_for(db, str(TENANT_A)) == []


def test_chase_late_payers_creates_one_l2_draft_per_customer(db):
    result = _run(db, "chase_late_payers")
    actions = _actions(db)
    assert len(actions) == 3
    assert len(result["inbox_item_ids"]) == 3
    assert all(a.autonomy_level == "L2" and a.status == "pending" and a.draft for a in actions)
    assert len({a.title for a in actions}) == 3
    assert _run(db, "chase_late_payers")["inbox_item_ids"] == result["inbox_item_ids"]


def test_pay_everyone_is_read_only_and_reports_demo_gap_and_scenarios(db):
    result = _run(db, "pay_everyone", UserRole.COMPLIANCE)
    steps = _steps(result)
    assert "Next 30 days" in steps["Planning window"]["text"]
    assert "Short by RM29,440.00 around day 23" in steps["Can we pay?"]["text"]
    assert "RM20,560.00" in steps["Can we pay?"]["text"]
    assert "RM62,000.00" in steps["Inflows and outflows"]["text"]
    assert "RM0.00" in steps["Collect earlier"]["text"]
    assert "no schedule was changed" in steps["Discuss payment timing"]["text"].lower()
    assert result["inbox_item_ids"] == []
    assert _actions(db) == []
    assert db.scalar(select(models.PayrollRun)) is None


def test_month_end_never_invents_a_reconciliation_or_no_data_tick(db):
    result = _run(db, "month_end", UserRole.COMPLIANCE)
    steps = _steps(result)
    # No bank lines on record: still "not measured", never a tick.
    assert steps["Bank reconciliation"]["status"] == "not_measured"
    assert steps["Bank reconciliation"]["text"].startswith("Bank reconciliation: not measured.")
    assert steps["Recent import"]["status"] == "not_measured"
    assert steps["e-Invoices"]["status"] == "not_measured"
    assert result["inbox_item_ids"] == []
    assert _actions(db) == []


@pytest.mark.parametrize(
    "phrase,name",
    [
        ("prepare me for the bank meeting", "bank_meeting"),
        ("bank pack", "bank_meeting"),
        ("loan meeting", "bank_meeting"),
        ("chase late payers", "chase_late_payers"),
        ("chase the late payers", "chase_late_payers"),
        ("chase overdue", "chase_late_payers"),
        ("who owes us", "chase_late_payers"),
        ("can I pay everyone this month?", "pay_everyone"),
        ("can we make payroll", "pay_everyone"),
        ("close the month", "month_end"),
        ("month end", "month_end"),
        ("month-end checklist", "month_end"),
    ],
)
def test_rules_select_playbooks_before_goals_without_creating_proposals(db, phrase, name):
    result = _client(db).post("/assistant/interpret", json={"text": phrase}).json()
    assert (result["kind"], result["playbook"]) == ("playbook", name)
    assert _actions(db) == []


@pytest.mark.parametrize("name", list(playbooks.TITLES))
def test_sales_employee_is_refused_in_interpret_route_and_service(db, name):
    client = _client(db, UserRole.GENERAL_EMPLOYEE)
    assert client.post(f"/assistant/playbooks/{name}").status_code == 403
    with pytest.raises(HTTPException) as error:
        playbooks.run(db, principal(UserRole.GENERAL_EMPLOYEE), name)
    assert error.value.status_code == 403
    phrase = {
        "bank_meeting": "bank pack",
        "chase_late_payers": "who owes us",
        "pay_everyone": "can we make payroll",
        "month_end": "close the month",
    }[name]
    assert client.post("/assistant/interpret", json={"text": phrase}).json()["kind"] == "refuse"
    assert _actions(db) == []


@pytest.mark.parametrize("name", ["bank_meeting", "chase_late_payers"])
def test_compliance_cannot_prepare_external_actions(db, name):
    assert _client(db, UserRole.COMPLIANCE).post(f"/assistant/playbooks/{name}").status_code == 403
    assert _actions(db) == []


def test_missing_facts_are_named_for_a_live_profile(db, monkeypatch):
    monkeypatch.setattr(
        playbooks.cashflow,
        "basis_for",
        lambda *args: CashBasis(
            DataMode.LIVE,
            Decimal("100000"),
            Decimal("50000"),
            (),
        ),
    )
    result = _run(db, "bank_meeting")
    assert result["synthetic"] is False
    assert _steps(result)["Missing facts"]["status"] == "attention"
    assert "Months trading" in _steps(result)["Missing facts"]["text"]
    assert "Annual revenue" in _steps(result)["Missing facts"]["text"]


def test_positive_payroll_answer_uses_the_lowest_balance_not_end_balance(db, monkeypatch):
    monkeypatch.setattr(
        playbooks.cashflow,
        "basis_for",
        lambda *args: CashBasis(
            DataMode.LIVE,
            Decimal("100000"),
            Decimal("50000"),
            (
                Signal(
                    "P",
                    "hr_payroll",
                    JobFunction.HR,
                    "outflow",
                    "Payroll",
                    Decimal("10000"),
                    5,
                    5,
                    5,
                ),
                Signal(
                    "R",
                    "receivables",
                    JobFunction.FINANCE,
                    "inflow",
                    "Invoice",
                    Decimal("20000"),
                    20,
                    20,
                    20,
                ),
            ),
        ),
    )
    result = _run(db, "pay_everyone")
    assert "Yes, RM40,000.00 spare" in _steps(result)["Can we pay?"]["text"]
    assert result["inbox_item_ids"] == []


def test_persisted_demo_proposals_are_visible_and_decidable_in_the_actual_inbox(db):
    owner = _client(db)
    result = _run(db, "bank_meeting")
    item_id = result["inbox_item_ids"][0]
    response = owner.get("/review-inbox")
    assert response.status_code == 200, response.text
    assert item_id in [a["id"] for a in response.json()["actions"]]
    finance = _client(db, UserRole.FINANCE_OPS)
    assert (
        finance.post(f"/review-inbox/{item_id}/decision", json={"decision": "approve"}).status_code
        == 403
    )
    approved = owner.post(f"/review-inbox/{item_id}/decision", json={"decision": "approve"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["action"]["status"] == "approved"
    assert passports.list_for(db, str(TENANT_A)) == []
    assert external_grants.list_for(db, str(TENANT_A), "lender", "pp_x") == []


def test_playbook_audit_has_only_ids_and_remains_on_the_hash_chain(db):
    for name in playbooks.TITLES:
        _run(db, name)
    rows = db.scalars(
        select(models.WorkflowAuditEntry).where(
            models.WorkflowAuditEntry.event_type == "assistant_playbook",
        )
    ).all()
    assert len(rows) == 4
    assert all(set(row.event_payload) == {"playbook", "inbox_item_ids"} for row in rows)
    assert verify_workflow_chain(db, str(TENANT_A)) is True


def test_all_playbooks_create_no_sendable_outreach_or_active_grants(db, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("A playbook tried to execute external work")

    monkeypatch.setattr(external_grants, "create", forbidden)
    monkeypatch.setattr(passports, "issue", forbidden)
    monkeypatch.setattr(playbooks.overdue_reminders, "plan_due_reminders", forbidden)
    for name in playbooks.TITLES:
        _run(db, name)
    assert db.scalar(select(models.OutreachAction)) is None
    assert db.scalar(select(models.EinvoiceOutreachDraft)) is None
    assert all(a.status == "pending" for a in _actions(db))


def test_due_invoices_group_by_customer_without_pii_or_autoapproved_worker_items(db):
    customer = models.Customer(
        tenant_id=str(TENANT_A), canonical_name="Private Person", normalized_name="PRIVATE PERSON"
    )
    foreign = models.Customer(
        tenant_id=str(TENANT_B), canonical_name="Other Person", normalized_name="OTHER PERSON"
    )
    db.add_all([customer, foreign])
    db.flush()
    for index, customer_id, tenant, paid in [
        (1, customer.id, TENANT_A, None),
        (2, customer.id, TENANT_A, None),
        (3, customer.id, TENANT_A, dt.date.today()),
        (4, foreign.id, TENANT_B, None),
    ]:
        db.add(
            models.EInvoiceRecord(
                tenant_id=str(tenant),
                buyer_customer_id=customer_id,
                supplier_name="Private Supplier",
                buyer_name="Private Person",
                invoice_no=f"private@example.test-{index}",
                total_amount=Decimal("10"),
                currency="MYR",
                due_date=dt.date.today() - dt.timedelta(days=5),
                status="validated",
                paid_at=paid,
            )
        )
    db.add(
        models.TenantOutreachPolicy(
            tenant_id=str(TENANT_A), telegram_reminders_enabled=True, require_approval=False
        )
    )
    db.commit()
    result = _run(db, "chase_late_payers")
    assert len(result["inbox_item_ids"]) == 1
    action = _actions(db)[0]
    assert len(action.evidence) == 3  # customer plus two unpaid invoices
    assert action.autonomy_level == "L2" and action.status == "pending"
    assert db.scalar(select(models.OutreachAction)) is None
    serialized = json.dumps(result) + str(
        db.scalars(select(models.WorkflowAuditEntry.event_payload)).all()
    )
    assert "Private" not in serialized and "private@example.test" not in serialized
    other = _client(db, tenant=TENANT_B)
    assert action.id not in [a["id"] for a in other.get("/review-inbox").json()["actions"]]
    assert (
        other.post(f"/review-inbox/{action.id}/decision", json={"decision": "approve"}).status_code
        == 404
    )


@pytest.mark.parametrize("age,status", [(6, "done"), (8, "attention")])
def test_month_end_uses_tenant_import_age_invoice_state_and_open_items(db, age, status):
    db.add_all(
        [
            models.BusinessImportBatch(
                id="b1",
                tenant_id=str(TENANT_A),
                schema_name="bank_statement",
                fingerprint="0" * 64,
                imported_rows=1,
                duplicate_rows=0,
                created_at=dt.datetime.now(dt.UTC) - dt.timedelta(days=age),
            ),
            models.BusinessImportBatch(
                id="b2",
                tenant_id=str(TENANT_B),
                schema_name="bank_statement",
                fingerprint="1" * 64,
                imported_rows=1,
                duplicate_rows=0,
            ),
            models.EInvoiceRecord(
                tenant_id=str(TENANT_A),
                supplier_name="Supplier",
                status="pending",
                total_amount=Decimal("10"),
            ),
            models.EInvoiceRecord(
                tenant_id=str(TENANT_B),
                supplier_name="Other Supplier",
                status="rejected",
                total_amount=Decimal("10"),
            ),
        ]
    )
    db.commit()
    _run(db, "bank_meeting")
    result = _run(db, "month_end", UserRole.COMPLIANCE)
    steps = _steps(result)
    assert steps["Recent import"]["status"] == status
    assert "1 records; 1 pending" in steps["e-Invoices"]["text"]
    assert steps["e-Invoices"]["status"] == "attention"
    assert "1 item still open" in steps["Open inbox items"]["text"]


def test_kill_switch_blocks_playbook_tools_and_creates_no_proposals(db):
    db.add(
        models.AgentSecurityControl(
            tenant_id=str(TENANT_A),
            agent_id="*",
            engaged=True,
            updated_by=str(principal(UserRole.OWNER_DIRECTOR).user_id),
        )
    )
    db.commit()
    response = _client(db).post("/assistant/playbooks/bank_meeting")
    assert response.status_code == 409
    assert response.json()["detail"] == "kill_switch_engaged"
    assert _actions(db) == []


def test_unknown_playbook_is_404_and_does_not_fall_back_to_a_goal(db):
    assert _client(db).post("/assistant/playbooks/send_money").status_code == 404
    assert _actions(db) == []


def test_approval_phrases_keep_the_existing_confirmation_route(db):
    result = assistant.interpret(db, principal(UserRole.OWNER_DIRECTOR), "approve the bank pack")
    assert result.kind != "playbook"


@pytest.mark.parametrize("role", [UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE])
def test_playbook_inbox_decisions_keep_step_up_and_read_only_role_checks(db, role):
    item_id = _run(db, "bank_meeting")["inbox_item_ids"][0]
    client = _client(db, role)
    if role == UserRole.OWNER_DIRECTOR:
        person = replace(principal(role), aal="aal1", mfa_verified_at=None)
        client.app.dependency_overrides[get_current_user] = lambda: person
    response = client.post(f"/review-inbox/{item_id}/decision", json={"decision": "approve"})
    assert response.status_code == 403
    assert response.json()["detail"] == (
        "step_up_required" if role == UserRole.OWNER_DIRECTOR else "read_only_role"
    )
    assert _actions(db)[0].status == "pending"


def test_interpreting_a_playbook_does_not_decide_existing_items(db):
    first = _run(db, "bank_meeting")
    response = _client(db).post("/assistant/interpret", json={"text": "bank pack"})
    assert response.json()["kind"] == "playbook"
    assert _actions(db)[0].status == "pending"
    assert _run(db, "bank_meeting")["inbox_item_ids"] == first["inbox_item_ids"]
