"""Bank reconciliation for one month, and asking Finance to explain a line."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.contracts.common import DataMode
from app.contracts.reconciliation import ExplainResponse, ReconciliationResponse
from app.db import get_db
from app.schemas import UserRole
from app.services import business_day, reconciliation

router = APIRouter(tags=["reconciliation"])

_MONEY_READ = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)
_MONEY_WORK = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR)


@router.get("/reconciliation", response_model=ReconciliationResponse)
def get_reconciliation(
    period: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    principal: AuthPrincipal = Depends(require_roles(*_MONEY_READ)),
    db: Session = Depends(get_db),
) -> ReconciliationResponse:
    try:
        return reconciliation.statement(
            db, principal, period, business_day.today(db, principal.tenant_id)
        )
    except reconciliation.ReconciliationError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error


@router.post("/reconciliation/{ref}/explain", response_model=ExplainResponse)
def explain_line(
    ref: str,
    principal: AuthPrincipal = Depends(require_roles(*_MONEY_WORK)),
    db: Session = Depends(get_db),
) -> ExplainResponse:
    try:
        action_id = reconciliation.explain(
            db, principal, ref, business_day.today(db, principal.tenant_id)
        )
    except reconciliation.ReconciliationError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return ExplainResponse(data_mode=DataMode.LIVE, action_id=action_id)
