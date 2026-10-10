import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.contracts.analysis import AnalysisResponse
from app.db import get_db
from app.schemas import UserRole
from app.services import financial_analysis

router = APIRouter(tags=["analysis"])

_READ_ROLES = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)


@router.get("/analysis", response_model=AnalysisResponse)
def analysis(
    months: int = Query(default=3, ge=1, le=12),
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
    db: Session = Depends(get_db),
) -> AnalysisResponse:
    """Monthly profit and loss, ratios with their formulas, and what changed."""
    if db is None:
        raise HTTPException(503, "analysis_storage_unavailable")
    return financial_analysis.analyse(db, str(principal.tenant_id), dt.date.today(), months)
