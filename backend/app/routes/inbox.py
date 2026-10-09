from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import require_roles, require_step_up
from app.auth.principal import AuthPrincipal
from app.contracts.agents import (
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewInboxResponse,
)
from app.contracts.common import DataMode, JobFunction
from app.schemas import UserRole
from app.stubs import inbox as stub

router = APIRouter(tags=["review-inbox"])

_ALL_ROLES = tuple(UserRole)


@router.get("/review-inbox", response_model=ReviewInboxResponse)
def review_inbox(
    job_function: JobFunction | None = Query(default=None),
    principal: AuthPrincipal = Depends(require_roles(*_ALL_ROLES)),
) -> ReviewInboxResponse:
    try:
        scope, actions = stub.review_inbox(
            principal.role, str(principal.user_id), job_function, principal.job_functions
        )
    except stub.InboxError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return ReviewInboxResponse(data_mode=DataMode.STUB, job_functions=scope, actions=actions)


@router.post("/review-inbox/{action_id}/decision", response_model=ReviewDecisionResponse)
def decide(
    action_id: str,
    request: ReviewDecisionRequest,
    principal: AuthPrincipal = Depends(require_step_up(*_ALL_ROLES)),
) -> ReviewDecisionResponse:
    try:
        action = stub.decide(
            action_id, request, principal.role, str(principal.user_id), principal.job_functions
        )
    except stub.InboxError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return ReviewDecisionResponse(data_mode=DataMode.STUB, action=action)
