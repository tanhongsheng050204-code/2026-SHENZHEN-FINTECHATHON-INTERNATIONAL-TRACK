import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.contracts.cashflow import (
    HORIZONS,
    CashSignalsResponse,
    ForecastResponse,
    ScenarioRequest,
)
from app.contracts.common import JobFunction
from app.db import get_db
from app.schemas import UserRole
from app.services import cashflow_engine
from app.services.cashflow import basis_for
from app.services.cashflow_engine import UnknownEventError

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
    db: Session = Depends(get_db),
) -> ForecastResponse:
    _check_horizon(horizon_days)
    day = as_of or dt.date.today()
    return cashflow_engine.build_forecast(
        basis_for(db, principal, day), horizon_days=horizon_days, as_of=day
    )


@router.post("/cashflow/scenarios", response_model=ForecastResponse)
def cashflow_scenario(
    request: ScenarioRequest,
    principal: AuthPrincipal = Depends(require_roles(*_SCENARIO_ROLES)),
    db: Session = Depends(get_db),
) -> ForecastResponse:
    day = request.as_of or dt.date.today()
    try:
        return cashflow_engine.build_forecast(
            basis_for(db, principal, day),
            horizon_days=request.horizon_days,
            as_of=day,
            shifts=request.shifts,
        )
    except UnknownEventError as error:
        raise HTTPException(status_code=422, detail=f"unknown_event:{error.event_id}") from error


@router.get("/cashflow/signals", response_model=CashSignalsResponse)
def cashflow_signals(
    horizon_days: int = Query(default=90),
    job_function: JobFunction | None = Query(default=None),
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
    db: Session = Depends(get_db),
) -> CashSignalsResponse:
    _check_horizon(horizon_days)
    basis = basis_for(db, principal, dt.date.today())
    return cashflow_engine.list_signals(basis, horizon_days=horizon_days, job_function=job_function)
