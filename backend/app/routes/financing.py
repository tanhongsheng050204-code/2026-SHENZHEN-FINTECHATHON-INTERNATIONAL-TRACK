from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.contracts.common import DataMode
from app.contracts.financing import (
    ApplicationPackRequest,
    ApplicationPackResponse,
    FinancingMatchesResponse,
    Jurisdiction,
    ScorecardResponse,
)
from app.schemas import UserRole
from app.stubs import financing as stub

router = APIRouter(tags=["financing"])

_READ_ROLES = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)
_PACK_ROLES = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR)


@router.get("/financing/matches", response_model=FinancingMatchesResponse)
def financing_matches(
    jurisdiction: Jurisdiction = Query(default="MY"),
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
) -> FinancingMatchesResponse:
    return stub.matches(jurisdiction)


@router.post("/financing/application-packs", response_model=ApplicationPackResponse)
def create_application_pack(
    request: ApplicationPackRequest,
    principal: AuthPrincipal = Depends(require_roles(*_PACK_ROLES)),
) -> ApplicationPackResponse:
    try:
        action = stub.application_pack(request.product_id)
    except stub.PackError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return ApplicationPackResponse(data_mode=DataMode.STUB, action=action)


@router.get("/financing/scorecard", response_model=ScorecardResponse)
def financing_scorecard(
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
) -> ScorecardResponse:
    """A points scorecard a lender can read line by line, with public signals as one factor."""
    return stub.scorecard()
