import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.contracts.cashflow import (
    HORIZONS,
    CashSignalsResponse,
    ForecastResponse,
    ScenarioRequest,
)
from app.contracts.common import JobFunction
from app.schemas import UserRole
from app.stubs.cashflow import UnknownEventError, build_forecast, list_signals

router = APIRouter(tags=["cashflow"])

_READ_ROLES = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)
_SCENARIO_ROLES = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR)


def _check_horizon(horizon_days: int) -> None:
    if horizon_days not in HORIZONS:
        raise HTTPException(status_code=422, detail="invalid_horizon")


@router.get("/cashflow/forecast", response_model=ForecastResponse)
def cashflow_forecast(
    horizon_days: int = Query(default=90),
    as_of: dt.date | None = Query(default=None),
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
) -> ForecastResponse:
    _check_horizon(horizon_days)
    return build_forecast(horizon_days=horizon_days, as_of=as_of or dt.date.today())


@router.post("/cashflow/scenarios", response_model=ForecastResponse)
def cashflow_scenario(
    request: ScenarioRequest,
    principal: AuthPrincipal = Depends(require_roles(*_SCENARIO_ROLES)),
) -> ForecastResponse:
    try:
        return build_forecast(
            horizon_days=request.horizon_days,
            as_of=request.as_of or dt.date.today(),
            shifts=request.shifts,
        )
    except UnknownEventError as error:
        raise HTTPException(status_code=422, detail=f"unknown_event:{error.event_id}") from error


@router.get("/cashflow/signals", response_model=CashSignalsResponse)
def cashflow_signals(
    horizon_days: int = Query(default=90),
    job_function: JobFunction | None = Query(default=None),
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
) -> CashSignalsResponse:
    _check_horizon(horizon_days)
    return list_signals(horizon_days=horizon_days, job_function=job_function)
