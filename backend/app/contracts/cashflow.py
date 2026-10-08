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
