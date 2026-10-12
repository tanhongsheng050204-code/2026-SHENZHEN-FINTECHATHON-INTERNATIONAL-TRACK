"""Skills for the Sales, HR & payroll, Payables and Compliance agents.

Each reads the forecast's own signals (so it works the same for the synthetic demo
company and a company on its own records) or the company's records, and returns
figures and, where a person should act, a review-inbox proposal. Nothing is sent,
paid or changed.

- Sales: an uncertain deal (probability below 1) whose best-case date falls within
  FOLLOW_UP_DAYS gets a follow-up for the Sales position.
- HR & payroll: each payroll run within PAYROLL_DAYS is checked against the
  forecast: the likely balance at the end of pay day, after the payroll. Below the
  company minimum, it becomes a proposal for HR.
- HR & payroll: EPF, SOCSO, EIS and PCB (monthly tax deduction) for a payroll
  month are due by the 15th of the following month.
- Payables: supplier bills and purchase payments due within BILL_DAYS.
- Compliance: open incidents and their outstanding required steps.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select

from app.contracts.cashflow import CashSignal, ForecastResponse

FOLLOW_UP_DAYS = 14
PAYROLL_DAYS = 14
BILL_DAYS = 14
STATUTORY_DAY = 15


def money(amount: Decimal) -> str:
    return f"RM{amount:,.2f}"


def deals_to_follow_up(forecast: ForecastResponse) -> list[CashSignal]:
    return sorted(
        (
            s
            for s in forecast.drivers
            if s.source_agent == "sales"
            and s.kind == "inflow"
            and s.probability < 1
            and s.best_day <= FOLLOW_UP_DAYS
        ),
        key=lambda s: (s.best_day, s.id),
    )


@dataclass(frozen=True)
class PayrollCheck:
    signal: CashSignal
    pay_date: dt.date
    balance_after: Decimal
    minimum: Decimal

    @property
    def short(self) -> bool:
        return self.balance_after < self.minimum


def payroll_checks(forecast: ForecastResponse) -> list[PayrollCheck]:
    points = {p.day: p for p in forecast.points}
    checks = []
    for s in forecast.drivers:
        day = s.likely_day
        if s.source_agent != "hr_payroll" or day is None or day > PAYROLL_DAYS:
            continue
        point = points.get(day)
        if point is None:
            continue
        checks.append(PayrollCheck(s, point.date, point.likely, forecast.minimum_balance))
    return sorted(checks, key=lambda c: c.pay_date)


def bills_due(forecast: ForecastResponse) -> list[CashSignal]:
    return sorted(
        (
            s
            for s in forecast.drivers
            if s.source_agent in ("payables", "purchasing")
            and s.kind == "outflow"
            and s.likely_day is not None
            and s.likely_day <= BILL_DAYS
        ),
        key=lambda s: (s.likely_day, s.id),
    )


def statutory_due(db, tenant_id: str, as_of: dt.date) -> tuple[str, dt.date] | None:
    """The latest paid payroll month whose contributions are due within 14 days."""
    from app.models import PayrollRun

    if db is None:
        return None
    runs = db.scalars(
        select(PayrollRun)
        .where(
            PayrollRun.tenant_id == tenant_id,
            PayrollRun.status.in_(("approved", "paid")),
            PayrollRun.pay_date <= as_of,
        )
        .order_by(PayrollRun.pay_date.desc())
    ).all()
    for run in runs:
        year, month = (int(part) for part in run.period.split("-"))
        due = dt.date(year + month // 12, month % 12 + 1, STATUTORY_DAY)
        if as_of <= due <= as_of + dt.timedelta(days=14):
            return run.period, due
    return None


def open_incidents(db, tenant_id: str) -> tuple[int, int]:
    """(open incidents, required steps still to do)."""
    if db is None:
        return 0, 0
    from app.services import incidents

    found = [i for i in incidents.incidents(db, tenant_id) if i.status == "open"]
    steps = sum(1 for i in found for c in i.checklist if c.required and not c.done)
    return len(found), steps
