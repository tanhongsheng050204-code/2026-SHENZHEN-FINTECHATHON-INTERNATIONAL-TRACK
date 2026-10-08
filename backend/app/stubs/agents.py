"""Stub agent registry, runs, autonomy, kill switch and journey for the demo company.

Workstream B2 replaces it with the agent runtime (manifests, skills, cash signals).
Skill lists follow FINBRAIN_SIX_DOCUMENTS.md: W1 skills are "available", W2 skills
are "planned". Nothing is persisted: promotions and kill-switch changes are echoed back.
"""

import hashlib
import re

from app.contracts.agents import (
    AgentCard,
    AgentListResponse,
    AgentMetrics,
    AgentRunCreated,
    AgentRunEvent,
    AgentSkill,
    AutonomyChangeRequest,
    JourneyAgent,
    JourneyFunction,
    JourneyResponse,
    KillSwitchRequest,
    ScopedAutonomy,
)
from app.contracts.common import AutonomyLevel, DataMode, JobFunction, autonomy_rank

_RUN_ID = re.compile(r"^run_demo_[0-9a-f]{8}$")
_MINUTES_PER_TASK = {
    "cashflow": 15,
    "financing": 30,
    "operations": 20,
    "receivables": 15,
    "payables": 10,
    "sales": 15,
    "customer_service": 5,
    "marketing": 20,
    "purchasing": 15,
    "inventory": 10,
    "hr_payroll": 20,
    "compliance": 15,
}

_SkillSpec = tuple[str, str, str, str]


class AutonomyChangeError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _metrics(
    proposals: int, unedited: int, edited: int, rejected: int, *, recommended: bool
) -> AgentMetrics:
    return AgentMetrics(
        proposals=proposals,
        approved_unedited=unedited,
        approved_edited=edited,
        rejected=rejected,
        unedited_approval_rate=round(unedited / proposals, 2),
        promotion_recommended=recommended,
    )


def _agent(
    agent_id: str,
    name: str,
    purpose: str,
    job: JobFunction | None,
    skills: list[_SkillSpec],
    *,
    metrics: AgentMetrics | None = None,
    built: bool = True,
) -> AgentCard:
    return AgentCard(
        id=agent_id,
        name=name,
        purpose=purpose,
        job_function=job,
        reviewer_job_function=job,
        build_status="built" if built else "designed",
        autonomy_level=AutonomyLevel.L1 if job is not None and built else AutonomyLevel.L0,
        scoped_autonomy=[],
        skills=[
            AgentSkill(
                id=skill_id,
                name=skill_name,
                wave=wave,
                availability="available" if built and wave == "W1" else "planned",
                side_effect=side_effect,
            )
            for skill_id, skill_name, wave, side_effect in skills
        ],
        kill_switch_engaged=False,
        metrics=metrics,
    )


_AGENTS: tuple[AgentCard, ...] = (
    _agent(
        "supervisor",
        "Supervisor",
        "Routes a goal or question to the right agents and streams their progress.",
        None,
        [
            ("route_goal", "Route a goal to agents", "W1", "read"),
            ("stream_progress", "Stream progress", "W1", "read"),
            ("daily_briefing", "Daily briefing per position", "W2", "read"),
        ],
    ),
    _agent(
        "cashflow",
        "Cash-flow agent",
        "30/60/90-day forecast, shortfall alerts and what-if scenarios.",
        JobFunction.OWNER,
        [
            ("forecast", "30/60/90-day forecast with bands", "W1", "read"),
            ("shortfall_alerts", "Shortfall alerts", "W1", "read"),
            ("scenarios", "What-if scenarios", "W1", "read"),
            ("runway_and_fx", "Cash runway and RMB exposure", "W2", "read"),
            ("owner_briefing", "Weekly owner briefing", "W2", "draft"),
        ],
        metrics=_metrics(18, 16, 1, 1, recommended=False),
    ),
    _agent(
        "financing",
        "Financing agent",
        "Matches financing with reasons, drafts application packs and the Passport.",
        JobFunction.OWNER,
        [
            ("match_products", "Financing matches with reasons", "W1", "read"),
            ("application_pack", "Application pack", "W1", "draft"),
            ("readiness_passport", "Financing Readiness Passport", "W1", "draft"),
            ("qualification_coaching", "What to fix to qualify", "W2", "read"),
        ],
        metrics=_metrics(6, 5, 1, 0, recommended=False),
    ),
    _agent(
        "operations",
        "Operations agent",
        "Shows where cash and work get stuck across departments.",
        JobFunction.OPERATIONS,
        [
            ("cash_conversion_cycle", "Cash conversion cycle", "W1", "read"),
            ("stale_approvals", "Stale-approval watch", "W1", "read"),
            ("kpi_report", "Department KPI report", "W2", "draft"),
            ("bottlenecks", "Bottleneck detection", "W2", "read"),
        ],
        metrics=_metrics(5, 5, 0, 0, recommended=False),
    ),
    _agent(
        "receivables",
        "Receivables agent",
        "Prioritises collections and drafts payment reminders.",
        JobFunction.FINANCE,
        [
            ("rank_overdue", "Ranked overdue invoices", "W1", "read"),
            ("draft_reminders", "Reminder drafts in English, Malay and Chinese", "W1", "draft"),
            ("payment_promises", "Payment-promise tracking", "W1", "read"),
            ("dispute_flags", "Dispute flags", "W2", "read"),
        ],
        metrics=_metrics(47, 44, 3, 0, recommended=True),
    ),
    _agent(
        "payables",
        "Payables agent",
        "Bills, payment timing and supplier bank-change protection.",
        JobFunction.FINANCE,
        [
            ("bill_calendar", "Bill-due calendar", "W1", "read"),
            ("bank_change_check", "Supplier bank-change check", "W1", "read"),
            ("early_payment_discounts", "Early-payment discounts", "W2", "read"),
            ("duplicate_bills", "Duplicate-bill detection", "W2", "read"),
            ("bank_reconciliation", "Bank reconciliation and data health", "W2", "read"),
            ("sst_preparation", "SST filing preparation", "W2", "draft"),
        ],
        metrics=_metrics(12, 11, 1, 0, recommended=False),
    ),
    _agent(
        "sales",
        "Sales agent",
        "Turns the pipeline into expected cash and checks credit before new orders.",
        JobFunction.SALES,
        [
            ("pipeline_inflows", "Pipeline to expected inflows", "W1", "read"),
            ("credit_check", "Credit check before a new order", "W1", "read"),
            ("quote_followups", "Quote follow-up drafts", "W2", "draft"),
            ("win_loss", "Win/loss summary", "W2", "read"),
            ("concentration_watch", "Customer concentration watch", "W2", "read"),
        ],
        metrics=_metrics(14, 12, 2, 0, recommended=False),
    ),
    _agent(
        "customer_service",
        "Customer service agent",
        "Triages messages, suggests replies and flags payment-dispute risk.",
        JobFunction.CUSTOMER_SERVICE,
        [
            ("triage_messages", "Triage email and Telegram messages", "W1", "read"),
            ("suggest_replies", "Suggested replies", "W1", "draft"),
            ("dispute_risk", "Complaint to dispute-risk flag", "W1", "read"),
            ("knowledge_answers", "Answers from the knowledge base", "W2", "draft"),
            ("response_times", "Response-time tracking", "W2", "read"),
        ],
        metrics=_metrics(33, 29, 3, 1, recommended=False),
    ),
    _agent(
        "marketing",
        "Marketing agent",
        "Shows which spend pays back and when marketplace money arrives.",
        JobFunction.MARKETING,
        [
            ("return_per_ringgit", "Return per ringgit by campaign", "W1", "read"),
            ("payout_timing", "Marketplace payout timing", "W1", "read"),
            ("promo_cash_impact", "Promotion calendar cash impact", "W2", "read"),
            ("segment_insights", "Customer segment insights", "W2", "read"),
            ("content_drafts", "Content drafts", "W2", "draft"),
        ],
        metrics=_metrics(4, 3, 1, 0, recommended=False),
    ),
    _agent(
        "purchasing",
        "Purchasing agent",
        "Turns purchase orders into committed RMB outflows and compares suppliers.",
        JobFunction.PROCUREMENT,
        [
            ("committed_outflows", "Committed outflows from purchase orders", "W1", "read"),
            ("supplier_comparison", "Supplier comparison", "W1", "read"),
            ("landed_cost", "Landed-cost estimate", "W2", "read"),
            ("three_way_match", "Three-way match", "W2", "read"),
            ("reorder_suggestions", "Reorder suggestions from stock", "W2", "draft"),
        ],
        metrics=_metrics(9, 8, 1, 0, recommended=False),
    ),
    _agent(
        "inventory",
        "Inventory agent",
        "Reorder alerts and the cash tied up in stock.",
        JobFunction.LOGISTICS,
        [
            ("reorder_alerts", "Stock levels and reorder alerts", "W1", "read"),
            ("cash_in_stock", "Cash tied up in stock", "W1", "read"),
            ("slow_stock", "Slow-moving and dead stock", "W2", "read"),
            ("count_variance", "Stock-count variance", "W2", "read"),
            ("shipment_tracking", "Inbound shipment tracking", "W2", "read"),
        ],
        metrics=_metrics(11, 10, 1, 0, recommended=False),
    ),
    _agent(
        "production",
        "Production agent",
        "Production plans, materials and work-in-progress cash (Manufacturing template).",
        JobFunction.PRODUCTION,
        [
            ("production_plan", "Production plan against orders", "W2", "read"),
            ("material_requirements", "Material requirements", "W2", "read"),
            ("wip_cash", "Work-in-progress cash", "W2", "read"),
            ("downtime_quality_log", "Downtime and quality log", "W2", "read"),
        ],
        built=False,
    ),
    _agent(
        "hr_payroll",
        "HR and payroll agent",
        "Payroll cash planning and statutory deadlines.",
        JobFunction.HR,
        [
            ("payroll_cash_plan", "Payroll cash planning", "W1", "read"),
            ("statutory_reminders", "EPF, SOCSO, EIS and PCB reminders", "W1", "draft"),
            ("leave_claims_checks", "Leave and claims checks", "W2", "read"),
            ("on_offboarding", "Onboarding and offboarding checklists", "W2", "draft"),
            ("headcount_forecast", "Headcount cost forecast", "W2", "read"),
        ],
        metrics=_metrics(6, 6, 0, 0, recommended=False),
    ),
    _agent(
        "compliance",
        "Compliance agent",
        "E-invoice readiness, AI oversight and access reviews.",
        JobFunction.COMPLIANCE,
        [
            ("einvoice_readiness", "E-invoice readiness", "W1", "read"),
            ("ai_oversight", "AI oversight", "W1", "read"),
            ("access_review", "Access review", "W1", "draft"),
            ("statutory_calendar", "SST and statutory calendar", "W2", "read"),
            ("pdpa_assistant", "PDPA request assistant", "W2", "draft"),
            ("retention_checks", "Retention checks", "W2", "read"),
        ],
        metrics=_metrics(8, 8, 0, 0, recommended=False),
    ),
)


def agents() -> list[AgentCard]:
    return list(_AGENTS)


def list_agents() -> AgentListResponse:
    return AgentListResponse(
        data_mode=DataMode.STUB, global_kill_switch_engaged=False, agents=list(_AGENTS)
    )


def find_agent(agent_id: str) -> AgentCard:
    for agent in _AGENTS:
        if agent.id == agent_id:
            return agent
    raise LookupError(agent_id)


def apply_kill_switch(request: KillSwitchRequest) -> AgentListResponse:
    if request.agent_id is None:
        engaged = [a.model_copy(update={"kill_switch_engaged": request.engaged}) for a in _AGENTS]
        return AgentListResponse(
            data_mode=DataMode.STUB,
            global_kill_switch_engaged=request.engaged,
            agents=engaged,
        )
    target = find_agent(request.agent_id)
    updated = [
        a.model_copy(update={"kill_switch_engaged": request.engaged}) if a.id == target.id else a
        for a in _AGENTS
    ]
    return AgentListResponse(
        data_mode=DataMode.STUB, global_kill_switch_engaged=False, agents=updated
    )


def change_autonomy(agent_id: str, request: AutonomyChangeRequest) -> AgentCard:
    agent = find_agent(agent_id)
    if agent.build_status != "built" or agent.metrics is None:
        raise AutonomyChangeError("agent_not_promotable")
    if request.level == AutonomyLevel.L3:
        raise AutonomyChangeError("l3_not_delegable")
    raising = autonomy_rank(request.level) > autonomy_rank(agent.autonomy_level)
    if raising and not agent.metrics.promotion_recommended:
        raise AutonomyChangeError("promotion_not_recommended")
    scoped = [s for s in agent.scoped_autonomy if s.action != request.action]
    scoped.append(
        ScopedAutonomy(action=request.action, level=request.level, max_amount=request.max_amount)
    )
    return agent.model_copy(update={"scoped_autonomy": scoped})


def start_run(goal: str) -> AgentRunCreated:
    run_id = "run_demo_" + hashlib.sha256(goal.encode()).hexdigest()[:8]
    return AgentRunCreated(
        data_mode=DataMode.STUB, run_id=run_id, events_url=f"/agents/runs/{run_id}/events"
    )


def run_events(run_id: str) -> list[AgentRunEvent]:
    if not _RUN_ID.match(run_id):
        raise LookupError(run_id)
    steps = [
        ("run_started", "supervisor", "Goal received; planning with three agents.", None),
        ("tool_called", "cashflow", "forecast(horizon_days=90)", None),
        (
            "proposal_created",
            "cashflow",
            "Shortfall in 23 days: likely balance RM20,560.00 against a RM50,000.00 minimum.",
            "act_cashflow_alert",
        ),
        ("tool_called", "receivables", "rank_overdue(limit=3)", None),
        ("proposal_created", "receivables", "Three reminder drafts ready.", "act_reminders"),
        ("tool_called", "financing", "match_products(gap=29440.00)", None),
        (
            "proposal_created",
            "financing",
            "Invoice financing matched; application pack drafted.",
            "act_financing_pack",
        ),
        ("waiting_for_review", "supervisor", "Three items await your review.", None),
        ("run_completed", "supervisor", "Run complete.", None),
    ]
    return [
        AgentRunEvent(
            run_id=run_id,
            sequence=sequence,
            type=event_type,
            agent_id=agent_id,
            message=message,
            action_id=action_id,
        )
        for sequence, (event_type, agent_id, message, action_id) in enumerate(steps, start=1)
    ]


def journey() -> JourneyResponse:
    functions: list[JourneyFunction] = []
    for job_function in JobFunction:
        entries = [
            JourneyAgent(
                agent_id=agent.id,
                name=agent.name,
                autonomy_level=agent.autonomy_level,
                build_status=agent.build_status,
                override_rate=(
                    round(
                        (agent.metrics.approved_edited + agent.metrics.rejected)
                        / agent.metrics.proposals,
                        2,
                    )
                    if agent.metrics
                    else None
                ),
                estimated_hours_saved=(
                    agent.metrics.proposals * _MINUTES_PER_TASK[agent.id] / 60
                    if agent.metrics
                    else 0.0
                ),
            )
            for agent in _AGENTS
            if agent.reviewer_job_function == job_function
        ]
        if entries:
            functions.append(JourneyFunction(job_function=job_function, agents=entries))
    return JourneyResponse(
        data_mode=DataMode.STUB,
        estimate_note=(
            "Estimated hours saved = completed tasks × configured minutes per task. "
            "Synthetic demo data."
        ),
        functions=functions,
    )
