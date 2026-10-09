"""Agents, review inbox and position workspaces on a tenant's own records (Plan 5).

Registered before the stub routers for these paths. A tenant with a live cash basis
gets the persisted review inbox, real review records and grants, and computed
workspaces; every other tenant still sees the demo company through the stubs.
Hidden from the published schema only because the stub routes publish the same
paths and models.

Decisions and autonomy changes use Plan 2's step-up dependency when it is present.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import dependencies
from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.contracts.agents import (
    AgentCardResponse,
    AgentListResponse,
    AutonomyChangeRequest,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewInboxResponse,
)
from app.contracts.common import DataMode, JobFunction
from app.contracts.positions import PositionWorkspace
from app.db import get_db
from app.schemas import UserRole
from app.services import job_scope, live_agents, review_inbox
from app.stubs import agents as stub_agents
from app.stubs import inbox as stub_inbox
from app.stubs import positions as stub_positions

router = APIRouter()

_ALL_ROLES = tuple(UserRole)
_step_up = getattr(dependencies, "require_step_up", require_roles)
_hidden = {"include_in_schema": False}


def _base_agents(db, principal: AuthPrincipal) -> AgentListResponse:
    try:
        from app.services import agent_security
    except ImportError:
        return stub_agents.list_agents()
    return agent_security.list_agents(db, principal)


@router.get("/agents", response_model=AgentListResponse, tags=["agents"], **_hidden)
def list_agents(
    principal: AuthPrincipal = Depends(require_roles(*_ALL_ROLES)),
    db: Session = Depends(get_db),
) -> AgentListResponse:
    base = _base_agents(db, principal)
    if not live_agents.is_live(db, principal):
        return base
    return base.model_copy(
        update={
            "data_mode": DataMode.LIVE,
            "agents": live_agents.overlay(db, str(principal.tenant_id), base.agents),
        }
    )


@router.post(
    "/agents/{agent_id}/autonomy", response_model=AgentCardResponse, tags=["agents"], **_hidden
)
def change_autonomy(
    agent_id: str,
    request: AutonomyChangeRequest,
    principal: AuthPrincipal = Depends(_step_up(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> AgentCardResponse:
    live = live_agents.is_live(db, principal)
    try:
        if live:
            agent = live_agents.change_autonomy(db, principal, agent_id, request)
        else:
            agent = stub_agents.change_autonomy(agent_id, request)
    except (live_agents.AutonomyError, stub_agents.AutonomyChangeError) as error:
        raise HTTPException(status_code=409, detail=error.code) from error
    except LookupError as error:
        raise HTTPException(status_code=404, detail="agent_not_found") from error
    return AgentCardResponse(data_mode=DataMode.LIVE if live else DataMode.STUB, agent=agent)


@router.get("/review-inbox", response_model=ReviewInboxResponse, tags=["review-inbox"], **_hidden)
def review(
    job_function: JobFunction | None = Query(default=None),
    principal: AuthPrincipal = Depends(require_roles(*_ALL_ROLES)),
    db: Session = Depends(get_db),
) -> ReviewInboxResponse:
    live = live_agents.is_live(db, principal)
    try:
        if live:
            scope, actions = review_inbox.inbox(db, principal, job_function)
        else:
            scope, actions = job_scope.call_stub(
                stub_inbox.review_inbox,
                principal.role,
                str(principal.user_id),
                job_function,
                principal=principal,
            )
    except (review_inbox.InboxError, stub_inbox.InboxError) as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return ReviewInboxResponse(
        data_mode=DataMode.LIVE if live else DataMode.STUB, job_functions=scope, actions=actions
    )


@router.post(
    "/review-inbox/{action_id}/decision",
    response_model=ReviewDecisionResponse,
    tags=["review-inbox"],
    **_hidden,
)
def decide(
    action_id: str,
    request: ReviewDecisionRequest,
    principal: AuthPrincipal = Depends(_step_up(*_ALL_ROLES)),
    db: Session = Depends(get_db),
) -> ReviewDecisionResponse:
    live = live_agents.is_live(db, principal)
    try:
        if live:
            action = review_inbox.decide(db, principal, action_id, request)
        else:
            action = job_scope.call_stub(
                stub_inbox.decide,
                action_id,
                request,
                principal.role,
                str(principal.user_id),
                principal=principal,
            )
    except (review_inbox.InboxError, stub_inbox.InboxError) as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return ReviewDecisionResponse(data_mode=DataMode.LIVE if live else DataMode.STUB, action=action)


@router.get(
    "/positions/{job_function}/workspace",
    response_model=PositionWorkspace,
    tags=["positions"],
    **_hidden,
)
def position_workspace(
    job_function: JobFunction,
    principal: AuthPrincipal = Depends(require_roles(*_ALL_ROLES)),
    db: Session = Depends(get_db),
) -> PositionWorkspace:
    if not live_agents.is_live(db, principal):
        try:
            return job_scope.call_stub(
                stub_positions.workspace,
                job_function,
                principal.role,
                str(principal.user_id),
                principal=principal,
            )
        except stub_positions.PositionError as error:
            raise HTTPException(status_code=error.status_code, detail=error.code) from error
    if job_function not in job_scope.scope(principal):
        raise HTTPException(status_code=403, detail="not_your_job_function")
    return live_agents.workspace(db, principal, job_function)
