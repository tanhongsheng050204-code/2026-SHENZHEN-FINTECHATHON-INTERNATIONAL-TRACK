"""More agents at work: Sales follow-ups, payroll readiness, statutory reminders, wider routing."""

import datetime as dt
from decimal import Decimal

import pytest

from app.contracts.common import DataMode, JobFunction
from app.models import PayrollRun
from app.schemas import UserRole
from app.services import agent_runtime, agent_skills, cashflow, review_inbox
from app.services.cashflow_engine import CashBasis, Signal
from tests.auth_support import TENANT_A, principal
from tests.test_collections_board import TODAY, live_db  # noqa: F401


@pytest.fixture(autouse=True)
def _no_persistent_guardrails(monkeypatch):
    monkeypatch.setattr(agent_runtime, "_external_guard", lambda *args, **kwargs: None)


def _basis(*signals, opening="100000.00", minimum="50000.00"):
    return CashBasis(DataMode.LIVE, Decimal(opening), Decimal(minimum), tuple(signals))


PAYROLL = Signal(
    "PR-2026-10",
    "hr_payroll",
    JobFunction.HR,
    "outflow",
    "Payroll 2026-10",
    Decimal("62000.00"),
    10,
    10,
    10,
)
DEAL_SOON = Signal(
    "SO-7",
    "sales",
    JobFunction.SALES,
    "inflow",
    "Quoted expected 20 Oct",
    Decimal("18000.00"),
    8,
    None,
    None,
    probability=0.4,
)
DEAL_LATER = Signal(
    "SO-8",
    "sales",
    JobFunction.SALES,
    "inflow",
    "Quoted expected 30 Dec",
    Decimal("9000.00"),
    70,
    None,
    None,
    probability=0.3,
)
BILL = Signal(
    "PAY-3",
    "payables",
    JobFunction.FINANCE,
    "outflow",
    "Supplier bill due 18 Oct",
    Decimal("7000.00"),
    6,
    6,
    6,
)


def _run(db, goal, role=UserRole.OWNER_DIRECTOR):
    person = principal(role)
    run = agent_runtime.start_run(db, person, goal)
    return agent_runtime.run_events(db, person, run.run_id)


def test_payroll_below_the_minimum_becomes_a_proposal_for_hr(live_db, monkeypatch):  # noqa: F811
    monkeypatch.setattr(cashflow, "basis_for", lambda *a: _basis(PAYROLL))

    events = _run(live_db, "Can we pay salaries this month?")
    [hr] = [e for e in events if e.agent_id == "hr_payroll" and e.type == "proposal_created"]
    assert "Payroll 2026-10" in hr.message and "RM38,000.00" in hr.message
    action = review_inbox._replay(live_db, str(TENANT_A))[hr.action_id].action
    assert action.reviewer_job_function == JobFunction.HR
    assert "Nothing has been paid" in action.summary


def test_payroll_that_leaves_enough_cash_says_so_without_a_proposal(live_db, monkeypatch):  # noqa: F811
    monkeypatch.setattr(cashflow, "basis_for", lambda *a: _basis(PAYROLL, opening="200000.00"))

    events = _run(live_db, "payroll")
    hr = [e for e in events if e.agent_id == "hr_payroll"]
    assert [e.type for e in hr] == ["tool_called"]
    assert "RM138,000.00 after it" in hr[0].message


def test_deals_closing_soon_get_a_follow_up_for_sales(live_db, monkeypatch):  # noqa: F811
    monkeypatch.setattr(cashflow, "basis_for", lambda *a: _basis(DEAL_SOON, DEAL_LATER))

    events = _run(live_db, "Which sales deals need attention?")
    proposals = [e for e in events if e.agent_id == "sales" and e.type == "proposal_created"]
    assert len(proposals) == 1 and "SO-7" in proposals[0].message
    assert "40%" in proposals[0].message
    action = review_inbox._replay(live_db, str(TENANT_A))[proposals[0].action_id].action
    assert action.reviewer_job_function == JobFunction.SALES
    assert action.evidence[0].source == "cash-signal:SO-7"


def test_supplier_bills_are_routed_to_payables(live_db, monkeypatch):  # noqa: F811
    monkeypatch.setattr(cashflow, "basis_for", lambda *a: _basis(BILL))

    events = _run(live_db, "What supplier bills are due?")
    payables = [e for e in events if e.agent_id == "payables"]
    assert payables and "1 bill" in payables[0].message and "RM7,000.00" in payables[0].message


def test_compliance_goals_report_open_incidents(live_db, monkeypatch):  # noqa: F811
    from app.contracts.security import IncidentRequest
    from app.services import incidents

    monkeypatch.setattr(cashflow, "basis_for", lambda *a: _basis())
    incidents.open_incident(
        live_db,
        principal(UserRole.COMPLIANCE),
        IncidentRequest(
            kind="other",
            data_kinds=["contact_details"],
            people_affected=1,
            significant_harm=False,
            detected_on=TODAY,
        ),
    )
    events = _run(live_db, "Any PDPA compliance issues?")
    compliance = [e for e in events if e.agent_id == "compliance"]
    assert compliance and "1 open incident" in compliance[0].message


def test_statutory_contributions_are_due_on_the_fifteenth_of_the_next_month(live_db):  # noqa: F811
    live_db.add(
        PayrollRun(
            id=1,
            tenant_id=str(TENANT_A),
            batch_id="b1",
            period="2026-10",
            pay_date=dt.date(2026, 10, 25),
            total_gross=Decimal("50000.00"),
            employer_contributions=Decimal("7000.00"),
            status="approved",
        )
    )
    live_db.commit()

    due = agent_skills.statutory_due(live_db, str(TENANT_A), dt.date(2026, 11, 10))
    assert due == ("2026-10", dt.date(2026, 11, 15))
    assert agent_skills.statutory_due(live_db, str(TENANT_A), dt.date(2026, 10, 1)) is None


def test_the_supervisor_names_every_area_it_covers(live_db):  # noqa: F811
    events = _run(live_db, "What will the weather be tomorrow?")
    assert "payroll" in events[-1].message and "sales" in events[-1].message


def test_workspaces_compute_follow_ups_statutory_dates_and_duplicate_bills(live_db, monkeypatch):  # noqa: F811
    from app.services import live_agents

    monkeypatch.setattr(cashflow, "basis_for", lambda *a: _basis(DEAL_SOON, DEAL_LATER, PAYROLL))
    owner = principal(UserRole.OWNER_DIRECTOR)

    sales = {
        r.skill_id: r
        for r in live_agents.workspace(live_db, owner, JobFunction.SALES).skill_results
    }
    assert sales["quote_followups"].value == "1 deal"
    assert sales["quote_followups"].status == "attention"

    hr = {
        r.skill_id: r for r in live_agents.workspace(live_db, owner, JobFunction.HR).skill_results
    }
    assert hr["statutory_reminders"].status in ("ok", "attention")
    assert hr["statutory_reminders"].summary != "Not computed from imported records yet."

    finance = {
        r.skill_id: r
        for r in live_agents.workspace(live_db, owner, JobFunction.FINANCE).skill_results
    }
    assert finance["duplicate_bills"].value == "0 flagged"
