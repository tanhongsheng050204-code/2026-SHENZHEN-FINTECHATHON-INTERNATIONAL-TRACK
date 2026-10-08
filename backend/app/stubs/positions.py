"""Stub position workspaces: every position's agents, skill results, cash and inbox.

Workstream B2 replaces the skill results with live skill runs. Display names and
enabled positions come from the trading template until the settings store (workstream
B1) takes over.
"""

from decimal import Decimal

from app.contracts.agents import AgentCard
from app.contracts.common import DataMode, EvidenceRef, JobFunction
from app.contracts.positions import (
    CashContribution,
    PositionsResponse,
    PositionSummary,
    PositionWorkspace,
    SkillResult,
)
from app.schemas import UserRole
from app.stubs import agents, cashflow, inbox

DISPLAY_NAMES: dict[JobFunction, str] = {
    JobFunction.OWNER: "Owner / Managing Director",
    JobFunction.OPERATIONS: "Operations Manager",
    JobFunction.FINANCE: "Finance",
    JobFunction.SALES: "Sales",
    JobFunction.CUSTOMER_SERVICE: "Customer Service",
    JobFunction.MARKETING: "Marketing / E-commerce",
    JobFunction.PROCUREMENT: "Purchasing / Import",
    JobFunction.LOGISTICS: "Storekeeper / Logistics",
    JobFunction.PRODUCTION: "Production",
    JobFunction.HR: "Admin & HR",
    JobFunction.COMPLIANCE: "Compliance / Data Protection",
}

TRADING_POSITIONS: frozenset[JobFunction] = frozenset(JobFunction) - {JobFunction.PRODUCTION}

_CASH_ROLES: dict[JobFunction, str] = {
    JobFunction.OWNER: "Consumes every position's cash signals",
    JobFunction.OPERATIONS: "Measures how long cash is stuck",
    JobFunction.COMPLIANCE: "Feeds compliance status into the Passport",
}

_ZERO = Decimal("0.00")


class PositionError(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _result(
    skill_id: str, title: str, value: str | None, summary: str, status: str, source: str
) -> SkillResult:
    return SkillResult(
        skill_id=skill_id,
        title=title,
        value=value,
        summary=summary,
        status=status,
        evidence=[EvidenceRef(label=title, source=source)],
    )


_RESULTS: dict[JobFunction, list[SkillResult]] = {
    JobFunction.OWNER: [
        _result(
            "forecast",
            "Cash forecast",
            "RM20,560.00 on day 23",
            "The likely balance falls below your RM50,000.00 minimum in 23 days.",
            "risk",
            "cashflow:forecast",
        ),
        _result(
            "match_products",
            "Financing matches",
            "5 eligible",
            "Invoice financing fits best; every rule is explained.",
            "ok",
            "financing:matches",
        ),
        _result(
            "readiness_passport",
            "Financing Readiness Passport",
            "Ready to share",
            "Hashed and anchored; share it with a lender through an expiring link.",
            "ok",
            "passport:pp_demo_1",
        ),
    ],
    JobFunction.OPERATIONS: [
        _result(
            "cash_conversion_cycle",
            "Cash conversion cycle",
            "75 days",
            "52 days to collect + 61 days in stock − 38 days to pay.",
            "attention",
            "finance:working-capital",
        ),
        _result(
            "stale_approvals",
            "Stale approvals",
            "2 items",
            "Two approvals have waited more than 48 hours.",
            "attention",
            "review:ages",
        ),
    ],
    JobFunction.FINANCE: [
        _result(
            "rank_overdue",
            "Top overdue customers",
            "RM73,700.00",
            "Customers A, B and C are the three most urgent collections.",
            "attention",
            "finance:ar-aging",
        ),
        _result(
            "bill_calendar",
            "Bills due soon",
            "RM14,800.00",
            "Rent and utilities fall due in 6 days.",
            "ok",
            "payables:calendar",
        ),
        _result(
            "bank_change_check",
            "Supplier bank changes",
            "1 quarantined",
            "Shenzhen Supplier 1's new bank account awaits callback and two approvers.",
            "risk",
            "payables:bank-changes",
        ),
    ],
    JobFunction.SALES: [
        _result(
            "pipeline_inflows",
            "Pipeline to cash",
            "RM26,000.00",
            "Order SO-311 from Customer G is 70% likely, expected in 60 days.",
            "ok",
            "pipeline:SO-311",
        ),
        _result(
            "credit_check",
            "Credit check",
            "Customer A: hold",
            "RM118,800.00 open against a RM100,000.00 credit limit.",
            "risk",
            "finance:credit-limits",
        ),
    ],
    JobFunction.CUSTOMER_SERVICE: [
        _result(
            "triage_messages",
            "Open cases",
            "4 open",
            "One complaint and three questions are waiting.",
            "attention",
            "support:cases",
        ),
        _result(
            "dispute_risk",
            "Dispute risk",
            "RM31,000.00 at risk",
            "Customer C's complaint may delay INV-1047.",
            "risk",
            "support:customer-c",
        ),
    ],
    JobFunction.MARKETING: [
        _result(
            "return_per_ringgit",
            "Return per ringgit",
            "3.4×",
            "The last Shopee campaign returned RM3.40 for every RM1 spent.",
            "ok",
            "marketing:campaigns",
        ),
        _result(
            "payout_timing",
            "Next marketplace payout",
            "RM9,400.00 in 26 days",
            "Shopee settles the next payout in 26 days.",
            "ok",
            "marketplace:payouts",
        ),
    ],
    JobFunction.PROCUREMENT: [
        _result(
            "committed_outflows",
            "Committed RMB payments",
            "RM99,540.00",
            "CNY 158,000 is committed to two Shenzhen suppliers at 0.63.",
            "attention",
            "purchasing:orders",
        ),
        _result(
            "supplier_comparison",
            "Supplier comparison",
            "Supplier 2: 6% cheaper",
            "Shenzhen Supplier 2 has a 6% lower unit price, 4 days longer lead time, 96% on time.",
            "ok",
            "purchasing:suppliers",
        ),
    ],
    JobFunction.LOGISTICS: [
        _result(
            "reorder_alerts",
            "Reorder alerts",
            "3 SKUs",
            "Three fast-moving SKUs are below their reorder level.",
            "attention",
            "stock:latest",
        ),
        _result(
            "cash_in_stock",
            "Cash tied up in stock",
            "RM84,300.00",
            "Across 42 SKUs at unit cost.",
            "ok",
            "stock:valuation",
        ),
    ],
    JobFunction.HR: [
        _result(
            "payroll_cash_plan",
            "Payroll cover",
            "Not covered",
            "Payroll of RM62,000.00 on day 23 falls in the projected shortfall.",
            "risk",
            "payroll:2026-10",
        ),
        _result(
            "statutory_reminders",
            "Statutory deadlines",
            "4 due in 7 days",
            "EPF, SOCSO, EIS and PCB submissions (illustrative dates).",
            "attention",
            "payroll:statutory",
        ),
    ],
    JobFunction.COMPLIANCE: [
        _result(
            "einvoice_readiness",
            "E-invoice readiness",
            "72% validated",
            "Validated e-invoices also raise financing eligibility.",
            "ok",
            "einvoice:readiness",
        ),
        _result(
            "ai_oversight",
            "AI oversight",
            "4 blocked",
            "Four guardrail events this week, all blocked or quarantined.",
            "ok",
            "trust:guardrail-events",
        ),
        _result(
            "access_review",
            "Access review",
            "1 account",
            "One account has been inactive for 45 days.",
            "attention",
            "team:activity",
        ),
    ],
}


def _agents_for(job_function: JobFunction) -> list[AgentCard]:
    return [agent for agent in agents.agents() if agent.job_function == job_function]


def _build_status(job_function: JobFunction) -> str:
    owned = _agents_for(job_function)
    return "built" if owned and all(a.build_status == "built" for a in owned) else "designed"


def positions(role: UserRole, user_id: str) -> PositionsResponse:
    scope = inbox.scope_for(role, user_id)
    return PositionsResponse(
        data_mode=DataMode.STUB,
        positions=[
            PositionSummary(
                job_function=job_function,
                display_name=DISPLAY_NAMES[job_function],
                enabled=job_function in TRADING_POSITIONS,
                build_status=_build_status(job_function),
                agent_ids=[agent.id for agent in _agents_for(job_function)],
            )
            for job_function in JobFunction
            if job_function in scope
        ],
    )


def _planned(job_function: JobFunction) -> list[SkillResult]:
    return [
        SkillResult(
            skill_id=skill.id,
            title=skill.name,
            value=None,
            summary="Designed — available with the Manufacturing template.",
            status="planned",
            evidence=[],
        )
        for agent in _agents_for(job_function)
        for skill in agent.skills
    ]


def workspace(job_function: JobFunction, role: UserRole, user_id: str) -> PositionWorkspace:
    if job_function not in inbox.scope_for(role, user_id):
        raise PositionError("not_your_job_function", 403)
    signals = cashflow.list_signals(horizon_days=90, job_function=job_function)
    totals = signals.by_agent
    return PositionWorkspace(
        data_mode=DataMode.STUB,
        job_function=job_function,
        display_name=DISPLAY_NAMES[job_function],
        build_status=_build_status(job_function),
        agents=_agents_for(job_function),
        skill_results=_RESULTS.get(job_function) or _planned(job_function),
        cash_contribution=CashContribution(
            role=_CASH_ROLES.get(job_function, "Feeds expected cash into the forecast"),
            inflow_total=sum((t.inflow_total for t in totals), _ZERO),
            outflow_total=sum((t.outflow_total for t in totals), _ZERO),
            at_risk_total=sum((t.at_risk_total for t in totals), _ZERO),
            signal_ids=[signal.id for signal in signals.signals],
        ),
        inbox_count=inbox.pending_count(job_function),
    )
