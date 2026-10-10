"""Match bank lines to the company's own records for the last completed month.

A bank line matches a record when the direction agrees, the MYR amount is equal to
the cent and the dates are at most three days apart. Each record matches at most
one line, closest date first. Records count only once they are settled:

- debits: paid payables, paid purchase orders and paid payroll runs;
- credits: paid marketplace payouts.

Lines with no record are listed for a person to explain. No line is ever matched
on a guess, and a month with no bank lines is reported as not measured.
"""

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select

from app import models

WINDOW_DAYS = 3
# Imported statements record money in and out; older rows say credit and debit.
_SIDE = {"in": "credit", "credit": "credit", "out": "debit", "debit": "debit"}
_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class Unmatched:
    posted_on: dt.date
    direction: str
    amount: Decimal


@dataclass(frozen=True)
class Result:
    period: str
    lines: int
    matched: int
    unmatched: list[Unmatched] = field(default_factory=list)

    @property
    def share(self) -> Decimal | None:
        if not self.lines:
            return None
        return (Decimal(self.matched) / Decimal(self.lines)).quantize(_PLACES)

    @property
    def label(self) -> str:
        return dt.date.fromisoformat(f"{self.period}-01").strftime("%B %Y")


def last_month(as_of: dt.date) -> tuple[dt.date, dt.date]:
    end = as_of.replace(day=1)
    return (end - dt.timedelta(days=1)).replace(day=1), end


def _records(db, tenant_id: str) -> dict[str, list[tuple[dt.date, Decimal]]]:
    m = models
    debits = [
        (row.due_date, row.amount_myr)
        for row in db.scalars(
            select(m.Payable).where(m.Payable.tenant_id == tenant_id, m.Payable.status == "paid")
        )
    ]
    debits += [
        (row.expected_payment, row.amount_myr)
        for row in db.scalars(
            select(m.PurchaseOrder).where(
                m.PurchaseOrder.tenant_id == tenant_id, m.PurchaseOrder.status == "paid"
            )
        )
    ]
    debits += [
        (row.pay_date, row.total_gross + row.employer_contributions)
        for row in db.scalars(
            select(m.PayrollRun).where(
                m.PayrollRun.tenant_id == tenant_id, m.PayrollRun.status == "paid"
            )
        )
    ]
    credits = [
        (row.payout_date, row.net)
        for row in db.scalars(
            select(m.MarketplacePayout).where(
                m.MarketplacePayout.tenant_id == tenant_id,
                m.MarketplacePayout.status == "paid",
            )
        )
    ]
    return {"debit": debits, "credit": credits}


def match(db, tenant_id: str, as_of: dt.date) -> Result:
    start, end = last_month(as_of)
    lines = db.scalars(
        select(models.BankTransaction)
        .where(
            models.BankTransaction.tenant_id == tenant_id,
            models.BankTransaction.posted_on >= start,
            models.BankTransaction.posted_on < end,
        )
        .order_by(models.BankTransaction.posted_on, models.BankTransaction.id)
    ).all()
    available = _records(db, tenant_id)
    matched = 0
    unmatched: list[Unmatched] = []
    for line in lines:
        side = _SIDE.get(line.direction, line.direction)
        pool = available.get(side, [])
        candidates = [
            (abs((day - line.posted_on).days), index)
            for index, (day, amount) in enumerate(pool)
            if amount == line.amount and abs((day - line.posted_on).days) <= WINDOW_DAYS
        ]
        if candidates:
            pool.pop(min(candidates)[1])
            matched += 1
        else:
            unmatched.append(Unmatched(line.posted_on, side, line.amount))
    return Result(
        period=start.strftime("%Y-%m"), lines=len(lines), matched=matched, unmatched=unmatched
    )
