from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.contracts.common import DataMode
from app.contracts.trust import GuardrailEventsResponse, PostureResponse
from app.schemas import UserRole
from app.stubs import trust as stub

router = APIRouter(tags=["trust"])

_OVERSIGHT_ROLES = (UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)


@router.get("/trust/posture", response_model=PostureResponse)
def posture(
    principal: AuthPrincipal = Depends(require_roles(*_OVERSIGHT_ROLES)),
) -> PostureResponse:
    return stub.posture()


@router.get("/trust/guardrail-events", response_model=GuardrailEventsResponse)
def guardrail_events(
    limit: int = Query(default=50, ge=1, le=200),
    principal: AuthPrincipal = Depends(require_roles(*_OVERSIGHT_ROLES)),
) -> GuardrailEventsResponse:
    return GuardrailEventsResponse(data_mode=DataMode.STUB, events=stub.guardrail_events(limit))
