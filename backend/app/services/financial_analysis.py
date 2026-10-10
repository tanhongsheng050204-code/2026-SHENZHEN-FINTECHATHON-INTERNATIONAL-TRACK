"""Business financial analysis from the company's own imported records.

Cash basis: revenue when it is received and costs when they are paid, by month.

- Revenue: sales ledger rows marked paid (on their received date) plus paid
  marketplace payouts at their gross amount; payout fees are a cost.
- Purchases: paid purchase orders in MYR. Rent and bills: paid payables.
- Payroll: paid runs, gross pay plus employer contributions. Totals only; no
  employee appears anywhere in the result.
- Marketing: spend of campaigns ending in the month.

Ratios carry their formula and the record kinds they used. A ratio whose records
are missing is "not_measured" with no value, never an estimate. "What changed"
compares the last two months with plain arithmetic; no model is involved.
"""

import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from app import models
from app.contracts.analysis import AnalysisResponse, ExpenseShare, PnlMonth, Ratio
from app.contracts.common import DataMode
from app.services import cash_basis, cashflow_engine

_ZERO = Decimal("0.00")
_LINES = (
    ("purchases", "Purchases"),
    ("payroll", "Payroll"),
    ("rent_and_bills", "Rent and bills"),
    ("marketing", "Marketing"),
    ("marketplace_fees", "Marketplace fees"),
)


def _one(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _pct(part: Decimal, whole: Decimal) -> Decimal | None:
    return _one(part / whole * 100) if whole else None


def _months(as_of: dt.date, count: int) -> list[tuple[str, dt.date, dt.date]]:
    """The last `count` completed calendar months, oldest first."""
    result = []
    index = as_of.year * 12 + as_of.month - 1
    for back in range(count, 0, -1):
        start_index = index - back
        start = dt.date(start_index // 12, start_index % 12 + 1, 1)
        end = dt.date((start_index + 1) // 12, (start_index + 1) % 12 + 1, 1)
        result.append((start.strftime("%Y-%m"), start, end))
    return result


def _sum(rows, day, amount, start, end) -> Decimal:
    return sum((amount(r) for r in rows if start <= day(r) < end), _ZERO)


def _records(db, tenant_id: str) -> dict[str, list]:
    m = models

    def rows(model, *where):
        return list(db.scalars(select(model).where(model.tenant_id == tenant_id, *where)))

    return {
        "sales": rows(m.SalesPipeline, m.SalesPipeline.stage == "paid"),
        "payouts": rows(m.MarketplacePayout, m.MarketplacePayout.status == "paid"),
        "purchases": rows(m.PurchaseOrder, m.PurchaseOrder.status == "paid"),
        "bills": rows(m.Payable, m.Payable.status == "paid"),
        "payroll": rows(m.PayrollRun, m.PayrollRun.status == "paid"),
        "marketing": rows(m.MarketingSpend),
        "open_sales": rows(m.SalesPipeline, m.SalesPipeline.stage == "invoiced"),
        "open_bills": rows(m.Payable, m.Payable.status == "open"),
        "open_orders": rows(m.PurchaseOrder, m.PurchaseOrder.status == "open"),
    }


def _month(records, key: str, start: dt.date, end: dt.date) -> PnlMonth:
    sales = _sum(
        records["sales"], lambda r: r.expected_payment_date, lambda r: r.amount, start, end
    )
    marketplace = _sum(records["payouts"], lambda r: r.payout_date, lambda r: r.gross, start, end)
    fees = _sum(records["payouts"], lambda r: r.payout_date, lambda r: r.fees, start, end)
    purchases = _sum(
        records["purchases"], lambda r: r.expected_payment, lambda r: r.amount_myr, start, end
    )
    bills = _sum(records["bills"], lambda r: r.due_date, lambda r: r.amount_myr, start, end)
    payroll = _sum(
        records["payroll"],
        lambda r: r.pay_date,
        lambda r: r.total_gross + r.employer_contributions,
        start,
        end,
    )
    marketing = _sum(records["marketing"], lambda r: r.period_end, lambda r: r.spend, start, end)
    revenue = sales + marketplace
    costs = purchases + payroll + bills + marketing + fees
    gross = revenue - purchases
    net = revenue - costs
    return PnlMonth(
        month=key,
        label=start.strftime("%B %Y"),
        revenue=revenue,
        sales=sales,
        marketplace=marketplace,
        purchases=purchases,
        payroll=payroll,
        rent_and_bills=bills,
        marketing=marketing,
        marketplace_fees=fees,
        total_costs=costs,
        gross_profit=gross,
        gross_margin=_pct(gross, revenue),
        net_result=net,
        net_margin=_pct(net, revenue),
    )


def _ratio(key, label, value, unit, formula, sources) -> Ratio:
    return Ratio(
        key=key,
        label=label,
        value=value,
        unit=unit,
        status="measured" if value is not None else "not_measured",
        formula=formula,
        sources=sources,
    )


def _ratios(db, tenant_id, as_of, records, months: list[PnlMonth]) -> list[Ratio]:
    revenue = sum((m.revenue for m in months), _ZERO)
    spent = sum((m.purchases + m.rent_and_bills for m in months), _ZERO)
    days = Decimal(len(months) * 30)
    open_sales = sum((r.amount for r in records["open_sales"]), _ZERO)
    owed = sum((r.amount_myr for r in records["open_bills"] + records["open_orders"]), _ZERO)

    first, end = _months(as_of, len(months))[0][1], _months(as_of, 1)[0][2]
    campaigns = [
        r
        for r in records["marketing"]
        if first <= r.period_end < end and r.attributed_revenue is not None
    ]
    spend = sum((r.spend for r in campaigns), _ZERO)
    attributed = sum((r.attributed_revenue for r in campaigns), _ZERO)

    by_customer: dict[int, Decimal] = {}
    for row in records["sales"]:
        if first <= row.expected_payment_date < end:
            by_customer[row.customer_id] = by_customer.get(row.customer_id, _ZERO) + row.amount
    sales_total = sum(by_customer.values(), _ZERO)
    payroll = sum((m.payroll for m in months), _ZERO)

    basis = cash_basis.load(db, tenant_id, as_of)
    forecast = (
        cashflow_engine.build_forecast(basis, horizon_days=90, as_of=as_of) if basis else None
    )
    runway = (
        Decimal(forecast.shortfall.day) if forecast is not None and forecast.shortfall else None
    )
    period = f"last {len(months)} months"
    return [
        _ratio(
            "days_to_get_paid",
            "Days to get paid",
            _one(open_sales / revenue * days) if revenue and records["open_sales"] else None,
            "days",
            f"Open invoiced sales ÷ revenue over the {period} × {days} days",
            ["sales ledger (invoiced, paid)", "marketplace payouts"],
        ),
        _ratio(
            "days_to_pay_suppliers",
            "Days to pay suppliers",
            _one(owed / spent * days) if spent and owed else None,
            "days",
            f"Open payables and purchase orders ÷ purchases and bills paid over the {period}"
            f" × {days} days",
            ["payables register", "purchase orders"],
        ),
        _ratio(
            "cash_runway",
            "Days until cash falls below the minimum",
            runway,
            "day",
            "First day the 90-day forecast's likely balance is below your minimum",
            ["90-day cash forecast"],
        ),
        _ratio(
            "marketing_return",
            "Marketing return per ringgit",
            (attributed / spend).quantize(Decimal("0.01")) if spend else None,
            "ringgit",
            f"Attributed revenue ÷ spend, campaigns ending in the {period}",
            ["marketing spend"],
        ),
        _ratio(
            "largest_customer_share",
            "Largest customer's share of sales",
            _pct(max(by_customer.values()), sales_total) if sales_total else None,
            "percent",
            f"Largest customer's received sales ÷ all received sales, {period}",
            ["sales ledger (paid)"],
        ),
        _ratio(
            "payroll_share",
            "Payroll as a share of revenue",
            _pct(payroll, revenue) if revenue and payroll else None,
            "percent",
            f"Payroll paid ÷ revenue, {period}",
            ["payroll runs (totals only)", "sales ledger", "marketplace payouts"],
        ),
    ]


def _changes(months: list[PnlMonth]) -> list[str]:
    if len(months) < 2:
        return []
    before, after = months[-2], months[-1]
    lines = [("Revenue", "revenue"), *((label, key) for key, label in _LINES)]
    lines.append(("Net result", "net_result"))
    moves = []
    for label, key in lines:
        old, new = getattr(before, key), getattr(after, key)
        delta = new - old
        if delta:
            moves.append((abs(delta), label, delta, old))
    moves.sort(key=lambda move: move[0], reverse=True)
    sentences = []
    for _, label, delta, old in moves[:3]:
        verb = "rose" if delta > 0 else "fell"
        share = f" ({'+' if delta > 0 else '−'}{abs(_pct(delta, old))}%)" if old else ""
        sentences.append(f"{label} {verb} RM{abs(delta):,.2f}{share} in {after.label}.")
    return sentences


def analyse(db, tenant_id: str, as_of: dt.date, months: int = 3) -> AnalysisResponse:
    synthetic = db.get(models.SyntheticTenantSeed, tenant_id) is not None
    records = _records(db, tenant_id)
    table = [_month(records, key, start, end) for key, start, end in _months(as_of, months)]
    costs = {key: sum((getattr(m, key) for m in table), _ZERO) for key, _ in _LINES}
    total = sum(costs.values(), _ZERO)
    has_records = any(records[k] for k in ("sales", "payouts", "purchases", "bills", "payroll"))
    return AnalysisResponse(
        data_mode=DataMode.LIVE if has_records else DataMode.STUB,
        synthetic=synthetic,
        as_of=as_of,
        basis="Cash basis: revenue when received, costs when paid.",
        months=table,
        expenses=[
            ExpenseShare(label=label, amount=costs[key], share=_pct(costs[key], total))
            for key, label in _LINES
        ],
        ratios=_ratios(db, tenant_id, as_of, records, table),
        changes=_changes(table),
    )
