import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.contracts.financing import (
    ApplicationPackRequest,
    ApplicationPackResponse,
    FinancingMatchesResponse,
    Jurisdiction,
    ScorecardResponse,
)
from app.db import get_db
from app.schemas import UserRole
from app.services import cashflow_engine, financing_profile
from app.services.cashflow import basis_for
from app.stubs import financing as stub

router = APIRouter(tags=["financing"])

_READ_ROLES = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)
_PACK_ROLES = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR)


def _profile(db, principal: AuthPrincipal) -> stub.Profile:
    today = dt.date.today()
    forecast = cashflow_engine.build_forecast(
        basis_for(db, principal, today), horizon_days=90, as_of=today
    )
    return financing_profile.compute(db, str(principal.tenant_id), forecast)


@router.get("/financing/matches", response_model=FinancingMatchesResponse)
def financing_matches(
    jurisdiction: Jurisdiction = Query(default="MY"),
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
    db: Session = Depends(get_db),
) -> FinancingMatchesResponse:
    return stub.matches(jurisdiction, _profile(db, principal))


@router.post("/financing/application-packs", response_model=ApplicationPackResponse)
def create_application_pack(
    request: ApplicationPackRequest,
    principal: AuthPrincipal = Depends(require_roles(*_PACK_ROLES)),
    db: Session = Depends(get_db),
) -> ApplicationPackResponse:
    profile = _profile(db, principal)
    try:
        action = stub.application_pack(request.product_id, profile)
    except stub.PackError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return ApplicationPackResponse(data_mode=profile.data_mode, action=action)


@router.get("/financing/scorecard", response_model=ScorecardResponse)
def financing_scorecard(
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
) -> ScorecardResponse:
    """A points scorecard a lender can read line by line, with public signals as one factor."""
    return stub.scorecard()
