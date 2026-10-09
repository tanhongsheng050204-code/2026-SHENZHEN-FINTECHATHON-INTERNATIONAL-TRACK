"""A tenant's cash basis from its imported business records (Plan 3 tables).

Opening balance: the latest bank balance on or before the as-of date.
Signals, each landing on its own day relative to the as-of date:

- Open payables on their due date; open purchase orders on their expected payment
  date, keeping the source currency and rate. A purchase order is not also a payable.
- Approved and draft payroll runs on their pay date, gross plus employer contributions.
- Invoiced sales pipeline on its expected payment date. Plan 3 stores likely
  receipt dates with the collection delay already included, so the delay is not
  added again; the worst case assumes WORST_CASE_EXTRA_DAYS more.
- Uncertain pipeline by probability: at least 0.5 counts in the best and likely
  cases, below 0.5 only in the best case, and lost deals never.
- Expected marketplace payouts (net of fees) and marketing spend still to start.

Stock reorders are not cash signals yet. Labels never carry customer or supplier
names: those are vault tokens in these tables and stay protected here.

Returns None when the Plan 3 tables are not deployed or the tenant has no bank
balance, so callers fall back to the synthetic demo company.
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import select

from app import models
from app.contracts.common import DataMode, JobFunction
from app.services.cashflow_engine import CashBasis, Signal

WORST_CASE_EXTRA_DAYS = 14
DEFAULT_MINIMUM_BALANCE = Decimal("50000.00")
_PLAN3 = (
    "BankTransaction",
    "Payable",
    "PurchaseOrder",
    "PayrollRun",
    "SalesPipeline",
    "MarketplacePayout",
    "MarketingSpend",
)


def _plan3_deployed() -> bool:
    return all(hasattr(models, name) for name in _PLAN3)


def _day(date: dt.date, as_of: dt.date) -> int:
    return max(0, (date - as_of).days)


def _minimum_balance(db, tenant_id: str) -> Decimal:
    record_type = getattr(models, "TenantSettingsRecord", None)
    record = db.get(record_type, tenant_id) if record_type is not None else None
    try:
        return Decimal(str(record.document["alerts"]["minimum_cash_balance"]))
    except (AttributeError, KeyError, TypeError):
        return DEFAULT_MINIMUM_BALANCE


def _opening_balance(db, tenant_id: str, as_of: dt.date) -> Decimal | None:
    bank = models.BankTransaction
    latest = db.scalar(
        select(bank)
        .where(bank.tenant_id == tenant_id, bank.posted_on <= as_of, bank.balance.is_not(None))
        .order_by(bank.posted_on.desc(), bank.id.desc())
        .limit(1)
    )
    return None if latest is None else Decimal(latest.balance)


def _foreign(currency: str, amount: Decimal, rate) -> dict:
    if currency == "MYR":
        return {}
    return {"source_currency": currency, "source_amount": amount, "fx_rate": rate}


def _pipeline_signal(row, as_of: dt.date) -> Signal | None:
    probability = float(row.probability)
    if row.stage == "lost" or probability <= 0:
        return None
    day = _day(row.expected_payment_date, as_of)
    when = f"{row.expected_payment_date:%d %b}"
    if row.stage == "invoiced":
        return Signal(
            f"INV-{row.id}",
            "receivables",
            JobFunction.FINANCE,
            "inflow",
            f"Invoice expected {when}",
            Decimal(row.amount),
            day,
            day,
            day + WORST_CASE_EXTRA_DAYS,
        )
    return Signal(
        f"SO-{row.id}",
        "sales",
        JobFunction.SALES,
        "inflow",
        f"{row.stage.capitalize()} expected {when}",
        Decimal(row.amount),
        day,
        day if probability >= 0.5 else None,
        None,
        probability=probability,
    )


def load(db, tenant_id: str, as_of: dt.date) -> CashBasis | None:
    if not _plan3_deployed():
        return None
    opening = _opening_balance(db, tenant_id, as_of)
    if opening is None:
        return None
    m = models
    signals: list[Signal] = []

    for row in db.scalars(
        select(m.Payable).where(m.Payable.tenant_id == tenant_id, m.Payable.status == "open")
    ):
        day = _day(row.due_date, as_of)
        signals.append(
            Signal(
                f"PAY-{row.id}",
                "payables",
                JobFunction.FINANCE,
                "outflow",
                f"Supplier bill due {row.due_date:%d %b}",
                Decimal(row.amount_myr),
                day,
                day,
                day,
                **_foreign(row.currency, row.amount, row.fx_rate),
            )
        )

    for row in db.scalars(
        select(m.PurchaseOrder).where(
            m.PurchaseOrder.tenant_id == tenant_id, m.PurchaseOrder.status == "open"
        )
    ):
        day = _day(row.expected_payment, as_of)
        label = "Purchase order" + (
            f" · {row.currency} {row.amount:,.0f}" if row.currency != "MYR" else ""
        )
        signals.append(
            Signal(
                f"PO-{row.id}",
                "purchasing",
                JobFunction.PROCUREMENT,
                "outflow",
                label,
                Decimal(row.amount_myr),
                day,
                day,
                day,
                **_foreign(row.currency, row.amount, row.fx_rate),
            )
        )

    for row in db.scalars(
        select(m.PayrollRun).where(
            m.PayrollRun.tenant_id == tenant_id,
            m.PayrollRun.status.in_(("approved", "draft")),
            m.PayrollRun.pay_date >= as_of,
        )
    ):
        day = _day(row.pay_date, as_of)
        signals.append(
            Signal(
                f"PR-{row.period}",
                "hr_payroll",
                JobFunction.HR,
                "outflow",
                f"Payroll {row.period}",
                Decimal(row.total_gross) + Decimal(row.employer_contributions),
                day,
                day,
                day,
            )
        )

    for row in db.scalars(select(m.SalesPipeline).where(m.SalesPipeline.tenant_id == tenant_id)):
        signal = _pipeline_signal(row, as_of)
        if signal is not None:
            signals.append(signal)

    for row in db.scalars(
        select(m.MarketplacePayout).where(
            m.MarketplacePayout.tenant_id == tenant_id,
            m.MarketplacePayout.status == "expected",
            m.MarketplacePayout.payout_date >= as_of,
        )
    ):
        day = _day(row.payout_date, as_of)
        signals.append(
            Signal(
                f"MP-{row.id}",
                "marketing",
                JobFunction.MARKETING,
                "inflow",
                f"Marketplace payout {row.payout_date:%d %b}",
                Decimal(row.net),
                day,
                day,
                day + WORST_CASE_EXTRA_DAYS // 2,
            )
        )

    for row in db.scalars(
        select(m.MarketingSpend).where(
            m.MarketingSpend.tenant_id == tenant_id, m.MarketingSpend.period_start >= as_of
        )
    ):
        day = _day(row.period_start, as_of)
        signals.append(
            Signal(
                f"MK-{row.id}",
                "marketing",
                JobFunction.MARKETING,
                "outflow",
                f"Marketing campaign from {row.period_start:%d %b}",
                Decimal(row.spend),
                day,
                day,
                day,
            )
        )

    return CashBasis(
        data_mode=DataMode.LIVE,
        opening_balance=opening,
        minimum_balance=_minimum_balance(db, tenant_id),
        signals=tuple(signals),
    )
