"""The payment-delay model: how late each customer pays, learned from their own record.

Training data is the company's paid e-invoices: days late = paid date - due date
(early payment counts as negative). The sales ledger is not used, because it keeps
an expected receipt date but no actual paid date.

For each customer the model keeps the median days late and the "spread": how much
later than usual the slow payments are (90th percentile minus median). A customer
with few invoices is shrunk towards the company-wide spread (empirical Bayes with
PRIOR_WEIGHT pseudo-invoices), so three invoices do not decide everything. With
no history at all the forecast keeps its fixed default.

The forecast's worst case for an invoice is its likely receipt date plus the
customer's spread. The sales ledger's likely date already includes the usual delay,
so only the spread is added.

The backtest is leave-one-out on the same paid invoices: refit without each one and
check whether it landed within its predicted worst case. It measures this
company's own history; on the synthetic demo company it is labelled as such.
"""

import math
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select

from app.contracts.cashflow import PaymentModelBacktest, PaymentModelCustomer, PaymentModelResponse
from app.contracts.common import DataMode
from app.models import EInvoiceRecord

DEFAULT_EXTRA_DAYS = 14  # cash_basis.WORST_CASE_EXTRA_DAYS
PRIOR_WEIGHT = 5
MIN_COMPANY_INVOICES = 10
MAX_EXTRA_DAYS = 90


def _rank(values: list[int], q: float) -> int:
    """Nearest-rank quantile of a non-empty list."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def _median(values: list[int]) -> int:
    ordered = sorted(values)
    return ordered[(len(ordered) - 1) // 2]


def _spread(values: list[int]) -> int:
    return max(0, _rank(values, 0.9) - _median(values))


@dataclass(frozen=True)
class Learned:
    paid_invoices: int
    median_days_late: int
    spread_days: int


@dataclass
class Model:
    delays: dict[int, list[int]]
    customers: dict[int, Learned] = field(default_factory=dict)
    company_extra_days: int = DEFAULT_EXTRA_DAYS
    company_learned: bool = False

    @property
    def learned_from(self) -> int:
        return sum(len(v) for v in self.delays.values())

    def basis(self, customer_id: int | None) -> str:
        if customer_id in self.customers:
            return "customer"
        return "company" if self.company_learned else "default"

    def extra_days(self, customer_id: int | None) -> int:
        learned = self.customers.get(customer_id) if customer_id is not None else None
        if learned is None:
            return self.company_extra_days
        n = learned.paid_invoices
        shrunk = (n * learned.spread_days + PRIOR_WEIGHT * self.company_extra_days) / (
            n + PRIOR_WEIGHT
        )
        return min(MAX_EXTRA_DAYS, round(shrunk))

    def median(self, customer_id: int | None) -> int:
        learned = self.customers.get(customer_id) if customer_id is not None else None
        if learned is not None:
            return learned.median_days_late
        everything = [d for values in self.delays.values() for d in values]
        return _median(everything) if everything else 0


def _from_delays(delays: dict[int, list[int]]) -> Model:
    model = Model(delays={k: list(v) for k, v in delays.items() if v})
    everything = [d for values in model.delays.values() for d in values]
    if len(everything) >= MIN_COMPANY_INVOICES:
        model.company_extra_days = min(MAX_EXTRA_DAYS, _spread(everything))
        model.company_learned = True
    model.customers = {
        customer_id: Learned(len(values), _median(values), _spread(values))
        for customer_id, values in model.delays.items()
    }
    return model


def _delays(db, tenant_id: str) -> dict[int, list[int]]:
    found: dict[int, list[int]] = defaultdict(list)
    for row in db.scalars(
        select(EInvoiceRecord).where(
            EInvoiceRecord.tenant_id == tenant_id,
            EInvoiceRecord.status == "validated",
            EInvoiceRecord.buyer_customer_id.is_not(None),
            EInvoiceRecord.due_date.is_not(None),
            EInvoiceRecord.paid_at.is_not(None),
        )
    ):
        found[row.buyer_customer_id].append((row.paid_at - row.due_date).days)
    return dict(found)


def fit(db, tenant_id: str) -> Model:
    return _from_delays(_delays(db, tenant_id))


def backtest(model: Model) -> PaymentModelBacktest | None:
    """Leave one paid invoice out, refit, and check it landed inside its worst case."""
    checked = within = 0
    for customer_id, values in model.delays.items():
        for index, delay in enumerate(values):
            rest = {k: list(v) for k, v in model.delays.items()}
            rest[customer_id] = values[:index] + values[index + 1 :]
            refit = _from_delays(rest)
            bound = refit.median(customer_id) + refit.extra_days(customer_id)
            checked += 1
            within += int(delay <= bound)
    if checked == 0:
        return None
    return PaymentModelBacktest(
        checked=checked, within=within, coverage_pct=round(100 * within / checked, 1)
    )


def report(db, tenant_id: str, data_mode: DataMode = DataMode.LIVE) -> PaymentModelResponse:
    from app.services.collections import _customer_labels

    model = fit(db, tenant_id)
    labels = _customer_labels(db, tenant_id, set(model.customers))
    return PaymentModelResponse(
        data_mode=data_mode,
        learned_from=model.learned_from,
        default_extra_days=DEFAULT_EXTRA_DAYS,
        company_extra_days=model.company_extra_days,
        company_learned=model.company_learned,
        customers=[
            PaymentModelCustomer(
                customer_id=customer_id,
                label=labels.get(customer_id, "Customer"),
                paid_invoices=learned.paid_invoices,
                median_days_late=learned.median_days_late,
                worst_extra_days=model.extra_days(customer_id),
            )
            for customer_id, learned in sorted(model.customers.items())
        ],
        backtest=backtest(model),
    )
