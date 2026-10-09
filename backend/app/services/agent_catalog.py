"""Configured W1 agent manifests. Proposal metrics are absent until Plan 5 records them."""

from app.contracts.agents import AgentCard, AgentListResponse, AgentMetrics, AgentSkill
from app.contracts.common import AutonomyLevel, DataMode, JobFunction

_SkillSpec = tuple[str, str, str, str]


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
    ),
)


def agents() -> list[AgentCard]:
    return list(_AGENTS)


def list_agents() -> AgentListResponse:
    return AgentListResponse(
        data_mode=DataMode.LIVE, global_kill_switch_engaged=False, agents=list(_AGENTS)
    )


def find_agent(agent_id: str) -> AgentCard:
    for agent in _AGENTS:
        if agent.id == agent_id:
            return agent
    raise LookupError(agent_id)
