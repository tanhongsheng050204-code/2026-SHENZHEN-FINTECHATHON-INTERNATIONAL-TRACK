"""Check saved alert rules against the company's own records.

Each rule names a metric, a threshold and the positions to tell. A reading comes
only from imported records; a metric with no source has no reading and never fires.
A rule fires at most once a day for each subject (the company, or one customer),
and each firing is an `alert_fired` event on the audit chain, holding the rule,
the metric, the subject id and the value, never a name.

In the app, the briefing shows today's alerts to the positions they name. By email
or Telegram an alert goes only to people in those positions who opted in to pushed
briefings, with ranges and counts instead of exact amounts.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select

from app import models
from app.contracts.customization import AlertRule
from app.services import cash_basis, cashflow_engine
from app.services.workflow_audit import write_workflow_event

_EVENT = "alert_fired"
_ZERO = Decimal("0")
_BANDS = [500, 1000, 2500, 5000, 10000, 25000, 50000, 100000]
_BAND_LABELS = [
    "under RM500",
    "RM500–1K",
    "RM1K–2.5K",
    "RM2.5K–5K",
    "RM5K–10K",
    "RM10K–25K",
    "RM25K–50K",
    "RM50K–100K",
    "over RM100K",
]
SCREENS = {
    "projected_balance": "cashflow",
    "overdue_amount_per_customer": "customers",
    "stock_below_reorder": "positions",
    "payroll_coverage_days": "cashflow",
    "marketing_return_per_ringgit": "positions",
    "open_disputes": "customers",
}


@dataclass(frozen=True)
class Reading:
    metric: str
    subject: str
    value: Decimal | None


@dataclass(frozen=True)
class Fired:
    rule_id: str
    metric: str
    subject: str
    value: Decimal
    channel: str
    recipients: tuple[str, ...]


def _band(amount: Decimal) -> str:
    index = sum(1 for bound in _BANDS if amount >= bound)
    return _BAND_LABELS[index]


def describe(metric: str, value: Decimal, *, exact: bool) -> str:
    money = f"RM{value:,.2f}" if exact else f"in the {_band(value)} range"
    if metric == "projected_balance":
        return f"The lowest projected balance in the next 30 days is {money}."
    if metric == "overdue_amount_per_customer":
        return f"A customer has {money if exact else _band(value)} overdue."
    if metric == "stock_below_reorder":
        count = int(value)
        return f"{count} item{'s' if count != 1 else ''} below their reorder level."
    if metric == "payroll_coverage_days":
        return f"Current cash covers about {int(value)} days of payroll."
    if metric == "marketing_return_per_ringgit":
        return f"Marketing returned RM{value:,.2f} for each ringgit spent."
    return f"{metric.replace('_', ' ').capitalize()}: {value}."


def _forecast(db, tenant_id: str, as_of: dt.date):
    basis = cash_basis.load(db, tenant_id, as_of)
    if basis is None:
        return None
    return cashflow_engine.build_forecast(basis, horizon_days=30, as_of=as_of)


def readings(db, tenant_id: str, as_of: dt.date) -> list[Reading]:
    m = models
    result: list[Reading] = []
    forecast = _forecast(db, tenant_id, as_of)
    lowest = min(p.likely for p in forecast.points) if forecast else None
    result.append(Reading("projected_balance", "company", lowest))

    overdue: dict[int, Decimal] = {}
    for row in db.scalars(
        select(m.SalesPipeline).where(
            m.SalesPipeline.tenant_id == tenant_id,
            m.SalesPipeline.stage == "invoiced",
            m.SalesPipeline.expected_payment_date < as_of,
        )
    ):
        overdue[row.customer_id] = overdue.get(row.customer_id, _ZERO) + row.amount
    result += [
        Reading("overdue_amount_per_customer", f"customer:{customer}", amount)
        for customer, amount in sorted(overdue.items())
    ]

    latest = (
        select(m.StockSnapshot.item_id, func.max(m.StockSnapshot.snapshot_date).label("day"))
        .where(m.StockSnapshot.tenant_id == tenant_id, m.StockSnapshot.snapshot_date <= as_of)
        .group_by(m.StockSnapshot.item_id)
        .subquery()
    )
    rows = db.execute(
        select(m.StockSnapshot.on_hand, m.InventoryItem.reorder_level)
        .join(
            latest,
            (latest.c.item_id == m.StockSnapshot.item_id)
            & (latest.c.day == m.StockSnapshot.snapshot_date),
        )
        .join(
            m.InventoryItem,
            (m.InventoryItem.id == m.StockSnapshot.item_id)
            & (m.InventoryItem.tenant_id == tenant_id),
        )
        .where(m.StockSnapshot.tenant_id == tenant_id)
    ).all()
    below = sum(1 for on_hand, reorder in rows if on_hand < reorder) if rows else None
    result.append(
        Reading("stock_below_reorder", "company", None if below is None else Decimal(below))
    )

    payroll = db.scalar(
        select(m.PayrollRun)
        .where(
            m.PayrollRun.tenant_id == tenant_id,
            m.PayrollRun.status.in_(("approved", "draft")),
            m.PayrollRun.pay_date >= as_of,
        )
        .order_by(m.PayrollRun.pay_date)
        .limit(1)
    )
    coverage = None
    if forecast is not None and payroll is not None:
        monthly = payroll.total_gross + payroll.employer_contributions
        if monthly > 0:
            coverage = (forecast.opening_balance / (monthly / 30)).quantize(Decimal("1"))
    result.append(Reading("payroll_coverage_days", "company", coverage))

    spend, revenue = _ZERO, _ZERO
    for row in db.scalars(
        select(m.MarketingSpend).where(
            m.MarketingSpend.tenant_id == tenant_id,
            m.MarketingSpend.period_end <= as_of,
            m.MarketingSpend.attributed_revenue.is_not(None),
        )
    ):
        spend += row.spend
        revenue += row.attributed_revenue
    marketing = (revenue / spend).quantize(Decimal("0.01")) if spend > 0 else None
    result.append(Reading("marketing_return_per_ringgit", "company", marketing))

    # No disputes register is imported yet, so this metric has no reading.
    result.append(Reading("open_disputes", "company", None))
    return result


def _rules(db, tenant_id: str) -> list[AlertRule]:
    return [
        AlertRule.model_validate(row.document)
        for row in db.scalars(
            select(models.TenantCustomization)
            .where(
                models.TenantCustomization.tenant_id == tenant_id,
                models.TenantCustomization.kind == "alert_rule",
            )
            .order_by(models.TenantCustomization.created_at, models.TenantCustomization.id)
        )
    ]


def _already(db, tenant_id: str, key: str) -> bool:
    return (
        db.scalar(
            select(models.WorkflowAuditEntry.id).where(
                models.WorkflowAuditEntry.tenant_id == tenant_id,
                models.WorkflowAuditEntry.event_type == _EVENT,
                models.WorkflowAuditEntry.resource_id == key,
            )
        )
        is not None
    )


def _deliver(db, tenant_id: str, fired: Fired) -> int:
    """Email or Telegram, ranges only, to opted-in people in the named positions."""
    from app.auth import demo
    from app.services import briefing_push

    # The shared demo company keeps its alerts in the app; nothing leaves the system.
    if fired.channel == "in_app" or demo.is_demo_tenant(tenant_id):
        return 0
    sent = 0
    preferences = briefing_push._preferences(db, tenant_id)
    for member in db.scalars(
        select(models.AuthUserRole).where(
            models.AuthUserRole.tenant_id == tenant_id, models.AuthUserRole.active.is_(True)
        )
    ):
        if not set(member.job_functions or ()) & set(fired.recipients):
            continue
        payload = preferences.get(str(member.user_id))
        if payload is None:
            continue
        address = briefing_push._open(str(member.user_id), payload).get(fired.channel)
        if not address:
            continue
        body = (
            "DuitDuit alert\n\n"
            + describe(fired.metric, fired.value, exact=False)
            + "\n\nSign in to DuitDuit for the details."
        )
        try:
            if fired.channel == "email":
                briefing_push._send_email(address, "DuitDuit alert", body)
            else:
                briefing_push._send_telegram(address, body)
            sent += 1
        except Exception:
            continue
    return sent


def evaluate(db, tenant_id: str, as_of: dt.date) -> list[Fired]:
    rules = [rule for rule in _rules(db, tenant_id) if rule.enabled]
    if not rules:
        return []
    by_metric: dict[str, list[Reading]] = {}
    for reading in readings(db, tenant_id, as_of):
        by_metric.setdefault(reading.metric, []).append(reading)
    fired: list[Fired] = []
    for rule in rules:
        for reading in by_metric.get(rule.metric, []):
            if reading.value is None:
                continue
            breached = (
                reading.value < rule.threshold
                if rule.operator == "below"
                else reading.value > rule.threshold
            )
            key = f"{rule.id}:{reading.subject}:{as_of.isoformat()}"
            if not breached or _already(db, tenant_id, key):
                continue
            alert = Fired(
                rule_id=rule.id,
                metric=rule.metric,
                subject=reading.subject,
                value=reading.value,
                channel=rule.channel,
                recipients=tuple(str(r) for r in rule.recipients),
            )
            delivered = _deliver(db, tenant_id, alert)
            write_workflow_event(
                db,
                event_type=_EVENT,
                actor_role="system",
                actor_ref="alert-rules",
                resource_type="alert",
                resource_id=key,
                event_payload={
                    "rule_id": rule.id,
                    "metric": rule.metric,
                    "subject": reading.subject,
                    "value": str(reading.value),
                    "recipients": list(alert.recipients),
                    "channel": rule.channel,
                    "day": as_of.isoformat(),
                    "delivered": delivered,
                },
                tenant_id=tenant_id,
            )
            db.commit()
            fired.append(alert)
    return fired


def fired_today(db, tenant_id: str, jobs: set[str], day: dt.date) -> list[dict]:
    """Today's alerts for anyone holding one of `jobs`."""
    rows = db.scalars(
        select(models.WorkflowAuditEntry)
        .where(
            models.WorkflowAuditEntry.tenant_id == tenant_id,
            models.WorkflowAuditEntry.event_type == _EVENT,
        )
        .order_by(models.WorkflowAuditEntry.id)
    )
    return [
        row.event_payload
        for row in rows
        if row.event_payload.get("day") == day.isoformat()
        and set(row.event_payload.get("recipients", ())) & jobs
    ]


def run_due(db, now_local: dt.datetime) -> int:
    """Check every tenant that has alert rules. Returns the number of alerts fired."""
    tenants = db.scalars(
        select(models.TenantCustomization.tenant_id)
        .where(models.TenantCustomization.kind == "alert_rule")
        .distinct()
    ).all()
    return sum(len(evaluate(db, str(tenant), now_local.date())) for tenant in tenants)
