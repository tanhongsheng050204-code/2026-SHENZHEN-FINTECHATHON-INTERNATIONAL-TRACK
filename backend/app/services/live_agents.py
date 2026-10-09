"""Agents, earned autonomy and position workspaces for a tenant on its own records.

Used when the tenant has a live cash basis (Plan 4); the demo company keeps the
sample cards and workspaces. Here:

- An agent card's metrics are its real review record (app.services.review_inbox).
- Scoped autonomy the owner grants is an "autonomy_granted" event on the tenant's
  chain, so a grant survives restarts and is audited. A raise is refused unless the
  record recommends it; L3 is never delegated.
- A position workspace computes each skill that has an engine behind it from the
  tenant's cash basis: forecast and shortfall, late or early receivables, financing
  eligibility, supplier bills, purchase commitments, payroll, pipeline and payouts.
  Skills without an engine say so instead of showing a figure.
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from app.auth.principal import AuthPrincipal
from app.contracts.agents import AgentCard, AutonomyChangeRequest, ScopedAutonomy
from app.contracts.cashflow import CashSignal, ForecastResponse
from app.contracts.common import AutonomyLevel, DataMode, EvidenceRef, JobFunction, autonomy_rank
from app.contracts.positions import CashContribution, PositionWorkspace, SkillResult
from app.models import WorkflowAuditEntry
from app.schemas import UserRole
from app.services import cashflow, cashflow_engine, financing_profile, review_inbox
from app.services.workflow_audit import write_workflow_event
from app.stubs import agents as manifests
from app.stubs.financing import matches
from app.stubs.positions import DISPLAY_NAMES

_ZERO = Decimal("0.00")


class AutonomyError(ValueError):
    def __init__(self, code: str, status_code: int = 409) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def is_live(db, principal: AuthPrincipal) -> bool:
    if db is None:
        return False
    return cashflow.basis_for(db, principal, dt.date.today()).data_mode == DataMode.LIVE


def _grants(db, tenant_id: str) -> dict[str, list[ScopedAutonomy]]:
    grants: dict[str, dict[str, ScopedAutonomy]] = {}
    for row in db.scalars(
        select(WorkflowAuditEntry)
        .where(
            WorkflowAuditEntry.tenant_id == tenant_id,
            WorkflowAuditEntry.event_type == "autonomy_granted",
        )
        .order_by(WorkflowAuditEntry.id)
    ):
        scoped = ScopedAutonomy.model_validate(row.event_payload["scoped"])
        grants.setdefault(row.resource_id, {})[scoped.action] = scoped
    return {agent: list(by_action.values()) for agent, by_action in grants.items()}


def overlay(db, tenant_id: str, cards: list[AgentCard]) -> list[AgentCard]:
    """Replace sample metrics and echoed grants with the tenant's real ones."""
    records = review_inbox.metrics(db, tenant_id)
    grants = _grants(db, tenant_id)
    return [
        card.model_copy(
            update={
                "metrics": records.get(card.id) if card.build_status == "built" else None,
                "scoped_autonomy": grants.get(card.id, []),
            }
        )
        for card in cards
    ]


def change_autonomy(
    db, principal: AuthPrincipal, agent_id: str, request: AutonomyChangeRequest
) -> AgentCard:
    tenant_id = str(principal.tenant_id)
    agent = manifests.find_agent(agent_id)
    if agent.build_status != "built" or agent.job_function is None:
        raise AutonomyError("agent_not_promotable")
    if request.level == AutonomyLevel.L3:
        raise AutonomyError("l3_not_delegable")
    record = review_inbox.metrics(db, tenant_id).get(agent_id)
    raising = autonomy_rank(request.level) > autonomy_rank(agent.autonomy_level)
    if raising and not (record and record.promotion_recommended):
        raise AutonomyError("promotion_not_recommended")
    scoped = ScopedAutonomy(
        action=request.action, level=request.level, max_amount=request.max_amount
    )
    write_workflow_event(
        db,
        event_type="autonomy_granted",
        actor_role=principal.role.value,
        actor_ref=str(principal.user_id),
        resource_type="agent",
        resource_id=agent_id,
        event_payload={"scoped": scoped.model_dump(mode="json")},
        tenant_id=tenant_id,
    )
    db.commit()
    return overlay(db, tenant_id, [agent])[0]


# --- Position workspaces ---


def _ringgit(amount: Decimal) -> str:
    return f"RM{amount:,.2f}"


def _result(skill_id, title, value, summary, status, source) -> SkillResult:
    return SkillResult(
        skill_id=skill_id,
        title=title,
        value=value,
        summary=summary,
        status=status,
        evidence=[EvidenceRef(label=title, source=source)],
    )


def _by(forecast: ForecastResponse, agent: str, kind: str) -> list[CashSignal]:
    return [s for s in forecast.drivers if s.source_agent == agent and s.kind == kind]


_EXACT_ROLES = (UserRole.OWNER_DIRECTOR, UserRole.FINANCE_OPS, UserRole.COMPLIANCE)
_BANDS = (
    (Decimal("10000"), "under RM10k"),
    (Decimal("50000"), "RM10k–50k"),
    (Decimal("100000"), "RM50k–100k"),
    (Decimal("250000"), "RM100k–250k"),
    (Decimal("500000"), "RM250k–500k"),
    (Decimal("1000000"), "RM500k–1M"),
)


def _sees_exact(principal: AuthPrincipal) -> bool:
    """Exact amounts for the roles that read the cash pages; bands for everyone else."""
    return principal.role in _EXACT_ROLES


def _sees_exact_payroll(principal: AuthPrincipal) -> bool:
    """Payroll totals: the owner, or someone who just passed a step-up (Plan 2)."""
    if principal.role == UserRole.OWNER_DIRECTOR:
        return True
    try:
        from app.auth.dependencies import has_recent_mfa
    except ImportError:
        return False
    return principal.role in _EXACT_ROLES and has_recent_mfa(principal)


def _band(amount: Decimal) -> str:
    return next((label for limit, label in _BANDS if amount < limit), "over RM1M")


def _formatter(exact: bool):
    return _ringgit if exact else _band


def _coarse(amount: Decimal, exact: bool) -> Decimal:
    if exact:
        return amount
    return (amount / 10000).quantize(Decimal("1")) * 10000


def _computed(db, principal: AuthPrincipal, forecast: ForecastResponse) -> dict[str, SkillResult]:
    from app.services import agent_runtime

    money = _formatter(_sees_exact(principal))
    pay = _formatter(_sees_exact_payroll(principal))
    shortfall = forecast.shortfall
    results: dict[str, SkillResult] = {}
    results["forecast"] = _result(
        "forecast",
        "90-day forecast",
        f"Day {shortfall.day}" if shortfall else "No shortfall",
        f"Likely balance {money(shortfall.likely_balance)} against a "
        f"{money(shortfall.minimum_balance)} minimum."
        if shortfall
        else "The likely balance stays above your minimum for 90 days.",
        "risk" if shortfall else "ok",
        "cashflow:forecast",
    )
    results["shortfall_alerts"] = _result(
        "shortfall_alerts",
        "Shortfall alerts",
        str(len(forecast.alerts)),
        "; ".join(a.title for a in forecast.alerts) or "No alerts.",
        "risk" if forecast.alerts else "ok",
        "cashflow:alerts",
    )
    late = agent_runtime._late_receivables(forecast) or agent_runtime._early_receivables(forecast)
    results["rank_overdue"] = _result(
        "rank_overdue",
        "Collections to chase",
        money(sum((s.amount_myr for s in late[:3]), _ZERO)) if late else None,
        ", ".join(s.label for s in late[:3]) or "Nothing late or needed early.",
        "attention" if late else "ok",
        "receivables:ranking",
    )
    profile = financing_profile.compute(db, str(principal.tenant_id), forecast)
    found = matches("MY", profile).matches
    eligible = [m for m in found if m.eligible]
    results["match_products"] = _result(
        "match_products",
        "Financing matches",
        f"{len(eligible)} of {len(found)}",
        f"Best fit: {eligible[0].product.name}." if eligible else "Nothing qualifies yet.",
        "ok" if eligible else "attention",
        "financing:matches",
    )
    soon = forecast.as_of + dt.timedelta(days=30)
    bills = [s for s in _by(forecast, "payables", "outflow") if s.best_day <= 30]
    results["bill_calendar"] = _result(
        "bill_calendar",
        "Bills due in 30 days",
        money(sum((s.amount_myr for s in bills), _ZERO)),
        f"{len(bills)} supplier bills due by {soon:%d %b}.",
        "ok",
        "payables:due",
    )
    orders = _by(forecast, "purchasing", "outflow")
    foreign = [s for s in orders if s.source_currency != "MYR"]
    results["committed_outflows"] = _result(
        "committed_outflows",
        "Committed purchase orders",
        money(sum((s.amount_myr for s in orders), _ZERO)),
        f"{len(orders)} open purchase orders, {len(foreign)} in foreign currency.",
        "attention" if shortfall and any(s.likely_day == shortfall.day for s in orders) else "ok",
        "purchasing:orders",
    )
    payroll = sorted(_by(forecast, "hr_payroll", "outflow"), key=lambda s: s.best_day)
    on_shortfall = bool(shortfall and payroll and payroll[0].likely_day == shortfall.day)
    results["payroll_cash_plan"] = _result(
        "payroll_cash_plan",
        "Next payroll",
        pay(payroll[0].amount_myr) if payroll else None,
        (f"Due on day {payroll[0].best_day}" if payroll else "No payroll run on record.")
        + (", the shortfall day." if on_shortfall else "."),
        "risk" if on_shortfall else "ok",
        "payroll:runs",
    )
    pipeline = _by(forecast, "sales", "inflow")
    weighted = sum((s.amount_myr * Decimal(str(s.probability)) for s in pipeline), _ZERO)
    results["pipeline_inflows"] = _result(
        "pipeline_inflows",
        "Weighted pipeline",
        money(weighted.quantize(Decimal("0.01"))),
        f"{len(pipeline)} open deals weighted by probability.",
        "ok",
        "sales:pipeline",
    )
    payouts = sorted(_by(forecast, "marketing", "inflow"), key=lambda s: s.best_day)
    results["payout_timing"] = _result(
        "payout_timing",
        "Next marketplace payout",
        money(payouts[0].amount_myr) if payouts else None,
        f"Expected on day {payouts[0].best_day}." if payouts else "No payout expected.",
        "ok",
        "marketplace:payouts",
    )
    return results


def workspace(db, principal: AuthPrincipal, job_function: JobFunction) -> PositionWorkspace:
    tenant_id = str(principal.tenant_id)
    today = dt.date.today()
    basis = cashflow.basis_for(db, principal, today)
    forecast = cashflow_engine.build_forecast(basis, horizon_days=90, as_of=today)
    signals = cashflow_engine.list_signals(basis, horizon_days=90, job_function=job_function)
    cards = overlay(
        db,
        tenant_id,
        [a for a in manifests.agents() if a.job_function == job_function],
    )
    computed = _computed(db, principal, forecast)
    results = []
    for card in cards:
        for skill in card.skills:
            if skill.availability != "available":
                continue
            results.append(
                computed.get(skill.id)
                or SkillResult(
                    skill_id=skill.id,
                    title=skill.name,
                    value=None,
                    summary="Not computed from imported records yet.",
                    status="planned",
                    evidence=[],
                )
            )
    totals = signals.by_agent
    exact = _sees_exact(principal)
    return PositionWorkspace(
        data_mode=DataMode.LIVE,
        job_function=job_function,
        display_name=DISPLAY_NAMES[job_function],
        build_status="built"
        if cards and all(c.build_status == "built" for c in cards)
        else "designed",
        agents=cards,
        skill_results=results,
        cash_contribution=CashContribution(
            role="Feeds expected cash into the forecast",
            inflow_total=_coarse(sum((t.inflow_total for t in totals), _ZERO), exact),
            outflow_total=_coarse(sum((t.outflow_total for t in totals), _ZERO), exact),
            at_risk_total=_coarse(sum((t.at_risk_total for t in totals), _ZERO), exact),
            signal_ids=[s.id for s in signals.signals],
        ),
        inbox_count=review_inbox.pending_count(db, tenant_id, job_function),
    )
