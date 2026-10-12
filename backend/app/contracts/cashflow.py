import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.contracts.common import DataMode, JobFunction

HORIZONS = (30, 60, 90)


class CashSignal(BaseModel):
    """One agent's expected money in or out. Risk signals annotate another signal."""

    id: str
    source_agent: str
    job_function: JobFunction
    kind: Literal["inflow", "outflow", "risk"]
    label: str
    amount_myr: Decimal = Field(ge=0)
    source_currency: str
    source_amount: Decimal | None = None
    fx_rate: Decimal | None = None
    best_day: int
    likely_day: int | None
    worst_day: int | None
    probability: float = Field(ge=0, le=1)
    affects: str | None = None


class ForecastPoint(BaseModel):
    day: int
    date: dt.date
    best: Decimal
    likely: Decimal
    worst: Decimal


class Shortfall(BaseModel):
    day: int
    date: dt.date
    likely_balance: Decimal
    minimum_balance: Decimal
    gap: Decimal


class ForecastAlert(BaseModel):
    id: str
    severity: Literal["info", "warning", "critical"]
    title: str
    detail: str
    day: int
    date: dt.date


class ForecastResponse(BaseModel):
    data_mode: DataMode
    as_of: dt.date
    currency: Literal["MYR"] = "MYR"
    horizon_days: int
    opening_balance: Decimal
    minimum_balance: Decimal
    points: list[ForecastPoint]
    shortfall: Shortfall | None
    alerts: list[ForecastAlert]
    drivers: list[CashSignal]


class EventShift(BaseModel):
    event_id: str = Field(min_length=1, max_length=64)
    shift_days: int = Field(ge=-90, le=180)


class ScenarioRequest(BaseModel):
    horizon_days: int = 90
    as_of: dt.date | None = None
    shifts: list[EventShift] = Field(default_factory=list, max_length=50)

    @field_validator("horizon_days")
    @classmethod
    def _known_horizon(cls, value: int) -> int:
        if value not in HORIZONS:
            raise ValueError("horizon_days must be 30, 60 or 90")
        return value


class AgentCashTotal(BaseModel):
    agent_id: str
    job_function: JobFunction
    inflow_total: Decimal
    outflow_total: Decimal
    at_risk_total: Decimal
    signal_count: int


class CashSignalsResponse(BaseModel):
    data_mode: DataMode
    horizon_days: int
    signals: list[CashSignal]
    by_agent: list[AgentCashTotal]


class ForecastCheckHorizon(BaseModel):
    horizon_days: int
    compared: int
    within_range: int
    mean_abs_error_myr: Decimal | None
    # Mean of 1 - |likely - actual| / |actual|, as a percentage (0 to 100).
    accuracy_pct: Decimal | None = None
    # Split-conformal half-width: likely ± this held 80% of the time on past days.
    calibrated_80_myr: Decimal | None = None
    # More comparisons needed before the calibrated range is shown.
    calibration_needs: int = 0


class ForecastDifference(BaseModel):
    """One scored day: how far off, and the money the forecast expected before it."""

    date: dt.date
    horizon_days: int
    likely_myr: Decimal
    actual_myr: Decimal
    # actual - likely: positive means more cash than forecast.
    difference_myr: Decimal
    within_range: bool
    expected_in_myr: Decimal | None
    expected_out_myr: Decimal | None


class ForecastCheckResponse(BaseModel):
    """How past forecasts compare with the bank balance on the days they forecast."""

    data_mode: DataMode
    status: Literal["measured", "not_measured"]
    reason: Literal["synthetic_company", "no_forecasts_kept", "awaiting_bank_statement"] | None
    forecasts_kept: int
    compared: int
    within_range: int
    first_comparison_on: dt.date | None
    by_horizon: list[ForecastCheckHorizon]
    largest_differences: list[ForecastDifference] = Field(default_factory=list)


class PaymentModelCustomer(BaseModel):
    customer_id: int
    # The masked name the customer list shows.
    label: str
    paid_invoices: int
    median_days_late: int
    # Added to the likely receipt date for the worst case, after shrinkage.
    worst_extra_days: int


class PaymentModelBacktest(BaseModel):
    """Leave-one-out on past paid invoices: how often one landed inside its worst case."""

    checked: int
    within: int
    coverage_pct: float


class PaymentModelResponse(BaseModel):
    data_mode: DataMode
    learned_from: int
    default_extra_days: int
    company_extra_days: int
    company_learned: bool
    customers: list[PaymentModelCustomer]
    backtest: PaymentModelBacktest | None
