"""Business financial analysis: monthly profit and loss, ratios and what changed."""

import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.common import DataMode


class PnlMonth(BaseModel):
    month: str = Field(description="YYYY-MM")
    label: str
    revenue: Decimal = Field(description="Sales received plus marketplace payouts (gross)")
    sales: Decimal
    marketplace: Decimal
    purchases: Decimal
    payroll: Decimal = Field(description="Gross pay plus employer contributions, totals only")
    rent_and_bills: Decimal
    marketing: Decimal
    marketplace_fees: Decimal
    total_costs: Decimal
    gross_profit: Decimal = Field(description="Revenue minus purchases")
    gross_margin: Decimal | None = Field(description="Percent of revenue, one decimal")
    net_result: Decimal = Field(description="Revenue minus all costs")
    net_margin: Decimal | None


class ExpenseShare(BaseModel):
    label: str
    amount: Decimal
    share: Decimal | None = Field(description="Percent of all costs in the period")


class Ratio(BaseModel):
    key: str
    label: str
    value: Decimal | None
    unit: Literal["days", "percent", "ringgit", "day"]
    status: Literal["measured", "not_measured"]
    formula: str
    sources: list[str]


class AnalysisResponse(BaseModel):
    data_mode: DataMode
    synthetic: bool
    as_of: dt.date
    basis: str
    months: list[PnlMonth]
    expenses: list[ExpenseShare]
    ratios: list[Ratio]
    changes: list[str]
