"""The facts financing rules read, computed from a tenant's own records.

Used only when the tenant has a live cash basis (imported bank balance); every
other tenant is matched against the synthetic demo profile. A fact with no source
in the tenant's records is left out, so its rule fails as "not on record" rather
than passing on an invented value:

- projected_shortfall_gap: the 90-day forecast's gap, zero when there is none.
- validated_einvoice_share: validated e-invoice records over all of them.
- receivables_over_90_share: invoiced pipeline more than 90 days past its expected
  payment date, by amount.
- top_customer_share: the largest customer's share of open invoiced and ordered pipeline.
- import_payables_share: foreign-currency open payables and purchase orders, by MYR amount.
- annual_revenue: the synthetic seed's declared revenue, when the tenant is synthetic.
- months_trading and anchor_buyer_programme: no source yet.
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import func, select

from app import models
from app.contracts.cashflow import ForecastResponse
from app.contracts.common import DataMode
from app.services import cash_basis
from app.stubs.financing import DEMO_PROFILE, Profile

_ZERO = Decimal("0")
_PLACES = Decimal("0.01")


def _share(part: Decimal, whole: Decimal) -> Decimal | None:
    return None if whole <= 0 else (part / whole).quantize(_PLACES)


def _einvoice_share(db, tenant_id: str) -> Decimal | None:
    record = models.EInvoiceRecord
    total = db.scalar(select(func.count()).where(record.tenant_id == tenant_id)) or 0
    validated = (
        db.scalar(
            select(func.count()).where(record.tenant_id == tenant_id, record.status == "validated")
        )
        or 0
    )
    return _share(Decimal(validated), Decimal(total))


def _business_facts(db, tenant_id: str, as_of: dt.date, values: dict) -> None:
    """Facts from the Plan 3 business tables."""
    m = models
    pipeline = list(
        db.scalars(
            select(m.SalesPipeline).where(
                m.SalesPipeline.tenant_id == tenant_id,
                m.SalesPipeline.stage.in_(("invoiced", "order")),
            )
        )
    )
    invoiced = [row for row in pipeline if row.stage == "invoiced"]
    invoiced_total = sum((Decimal(row.amount) for row in invoiced), _ZERO)
    stale = as_of - dt.timedelta(days=90)
    over_90 = sum(
        (Decimal(row.amount) for row in invoiced if row.expected_payment_date < stale), _ZERO
    )
    share = _share(over_90, invoiced_total)
    if share is not None:
        values["receivables_over_90_share"] = share
    by_customer: dict[int, Decimal] = {}
    for row in pipeline:
        by_customer[row.customer_id] = by_customer.get(row.customer_id, _ZERO) + row.amount
    share = _share(max(by_customer.values(), default=_ZERO), sum(by_customer.values(), _ZERO))
    if share is not None:
        values["top_customer_share"] = share

    owed = [
        *db.scalars(
            select(m.Payable).where(m.Payable.tenant_id == tenant_id, m.Payable.status == "open")
        ),
        *db.scalars(
            select(m.PurchaseOrder).where(
                m.PurchaseOrder.tenant_id == tenant_id, m.PurchaseOrder.status == "open"
            )
        ),
    ]
    foreign = sum((Decimal(r.amount_myr) for r in owed if r.currency != "MYR"), _ZERO)
    share = _share(foreign, sum((Decimal(r.amount_myr) for r in owed), _ZERO))
    if share is not None:
        values["import_payables_share"] = share


def compute(db, tenant_id: str, forecast: ForecastResponse) -> Profile:
    if forecast.data_mode != DataMode.LIVE:
        return DEMO_PROFILE
    m = models
    as_of = forecast.as_of
    values: dict[str, Decimal] = {
        "projected_shortfall_gap": forecast.shortfall.gap if forecast.shortfall else _ZERO,
    }

    einvoice = _einvoice_share(db, tenant_id)
    if einvoice is not None:
        values["validated_einvoice_share"] = einvoice

    if cash_basis._plan3_deployed():
        _business_facts(db, tenant_id, as_of, values)

    seed_type = getattr(m, "SyntheticTenantSeed", None)
    seed = db.get(seed_type, tenant_id) if seed_type is not None else None
    if seed is not None:
        values["annual_revenue"] = Decimal(seed.annual_revenue_myr)

    return Profile(DataMode.LIVE, values)
