"""What DuitDuit did for this company, measured from its own records.

Every figure comes from the same engines as its page: the forecast, the review
inbox, bank matching, anomaly detection, the simulated bank and the protected
record store. Hours saved is the one estimate, and says how it is worked out. A
figure with no records behind it says "not measured" instead of a number.
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select

from app.auth.principal import AuthPrincipal
from app.contracts.cashflow import EventShift
from app.contracts.common import DataMode
from app.contracts.value import ValueMetric, ValueReport
from app.models import SecurityGuardrailEvent, SyntheticTenantSeed, TokenizedContent

_ZERO = Decimal("0.00")


def _money(amount: Decimal) -> str:
    return f"RM{amount:,.2f}"


def report(db, principal: AuthPrincipal, as_of: dt.date) -> ValueReport:
    from app.services import (
        agent_runtime,
        anomalies,
        bank_matching,
        cashflow,
        cashflow_engine,
        review_inbox,
        sandbox_bank,
    )
    from app.stubs.agents import _MINUTES_PER_TASK

    tenant_id = str(principal.tenant_id)
    metrics: list[ValueMetric] = []

    basis = cashflow.basis_for(db, principal, as_of)
    forecast = cashflow_engine.build_forecast(basis, horizon_days=90, as_of=as_of)
    shortfall = forecast.shortfall
    if forecast.data_mode != DataMode.LIVE:
        metrics.append(ValueMetric(
            key="shortfall_warning", label="Cash gap warning", value="Not measured",
            detail="Import a bank statement and bills to forecast cash.", kind="not_measured",
        ))
    elif shortfall:
        metrics.append(ValueMetric(
            key="shortfall_warning", label="Cash gap warning",
            value=f"{shortfall.day} days ahead",
            detail=f"Cash falls {_money(shortfall.gap)} below your minimum on "
            f"{shortfall.date:%d %b %Y}, seen on {as_of:%d %b}.",
            kind="measured",
        ))
        early = agent_runtime._early_receivables(forecast)
        if early:
            scenario = cashflow_engine.build_forecast(
                basis, horizon_days=90, as_of=as_of,
                shifts=[
                    EventShift(event_id=s.id, shift_days=shortfall.day - 1 - s.likely_day)
                    for s in early
                ],
            )
            remaining = max(_ZERO, forecast.minimum_balance - scenario.points[shortfall.day].likely)
            closed = shortfall.gap - remaining
            metrics.append(ValueMetric(
                key="gap_closable", label="Gap the proposed actions close",
                value=f"{_money(closed)} of {_money(shortfall.gap)}",
                detail=f"By collecting {len(early)} later invoice"
                f"{'s' if len(early) != 1 else ''} before day {shortfall.day}, as the "
                "collections agent proposes. A scenario: no date was changed.",
                kind="measured",
            ))
    else:
        metrics.append(ValueMetric(
            key="shortfall_warning", label="Cash gap warning", value="None in 90 days",
            detail="The likely balance stays above your minimum.", kind="measured",
        ))

    items = [item.action for item in review_inbox._replay(db, tenant_id).values()]
    decided = [a for a in items if a.status in ("approved", "rejected")]
    unchanged = [a for a in items if a.status == "approved"]
    metrics.append(ValueMetric(
        key="proposals_prepared", label="Work prepared by the agents",
        value=str(len(items)),
        detail=f"{len(decided)} decided by a person, {len(unchanged)} approved. "
        "Each waited in the review inbox.",
        kind="measured",
    ))

    matched = bank_matching.match(db, tenant_id, as_of)
    metrics.append(
        ValueMetric(
            key="bank_reconciled", label=f"Bank lines reconciled, {matched.label}",
            value=f"{matched.matched} of {matched.lines}",
            detail=f"{len(matched.unmatched)} left for a person to explain.",
            kind="measured",
        )
        if matched.lines
        else ValueMetric(
            key="bank_reconciled", label="Bank lines reconciled", value="Not measured",
            detail="No bank lines for last month.", kind="not_measured",
        )
    )

    found = anomalies.scan(db, tenant_id).findings
    metrics.append(ValueMetric(
        key="unusual_caught", label="Unusual bills and payments caught",
        value=f"{len(found)} flagged",
        detail=f"Worth {_money(sum((f.amount_myr for f in found), _ZERO))}, before anyone paid.",
        kind="measured",
    ))

    paid = sandbox_bank.payments(db, tenant_id)
    metrics.append(ValueMetric(
        key="payments_two_people", label="Payments run after two approvals",
        value=str(len(paid)),
        detail=f"{_money(sum((p.amount for p in paid), _ZERO))} in the simulated bank, each "
        "approved by a maker and a different checker.",
        kind="measured",
    ))

    protected = db.scalar(
        select(func.count()).select_from(TokenizedContent).where(
            TokenizedContent.tenant_id == tenant_id
        )
    ) or 0
    blocked = db.scalar(
        select(func.count()).select_from(SecurityGuardrailEvent).where(
            SecurityGuardrailEvent.tenant_id == tenant_id
        )
    ) or 0
    metrics.append(ValueMetric(
        key="records_protected", label="Records protected before any AI saw them",
        value=str(protected),
        detail=f"{blocked} unsafe request{'s' if blocked != 1 else ''} blocked or quarantined.",
        kind="measured",
    ))

    minutes = sum(_MINUTES_PER_TASK.get(a.agent_id, 15) for a in items)
    metrics.append(ValueMetric(
        key="hours_saved", label="Time saved (estimate)",
        value=f"{minutes / 60:.1f} h",
        detail="Prepared items × configured minutes per kind of task. An estimate, not "
        "measured.",
        kind="estimate",
    ))

    return ValueReport(
        data_mode=forecast.data_mode,
        as_of=as_of,
        synthetic=db.get(SyntheticTenantSeed, tenant_id) is not None,
        metrics=metrics,
    )
