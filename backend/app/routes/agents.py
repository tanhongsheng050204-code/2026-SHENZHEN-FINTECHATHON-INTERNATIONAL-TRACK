from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.sse import EventSourceResponse

from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.contracts.agents import (
    AgentCardResponse,
    AgentListResponse,
    AgentRunCreated,
    AgentRunEvent,
    AgentRunRequest,
    AutonomyChangeRequest,
    JourneyResponse,
    KillSwitchRequest,
)
from app.contracts.common import DataMode
from app.schemas import UserRole
from app.stubs import agents as stub

router = APIRouter(tags=["agents"])

_ALL_ROLES = tuple(UserRole)
_OPERATOR_ROLES = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR)
_KILL_SWITCH_ROLES = (UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)


@router.get("/agents", response_model=AgentListResponse)
def list_agents(
    principal: AuthPrincipal = Depends(require_roles(*_ALL_ROLES)),
) -> AgentListResponse:
    return stub.list_agents()


@router.post("/agents/runs", response_model=AgentRunCreated)
def start_run(
    request: AgentRunRequest,
    principal: AuthPrincipal = Depends(require_roles(*_OPERATOR_ROLES)),
) -> AgentRunCreated:
    return stub.start_run(request.goal)


def _known_run_events(run_id: str) -> list[AgentRunEvent]:
    # A dependency, so an unknown run is a 404 before the stream starts.
    try:
        return stub.run_events(run_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="run_not_found") from error


@router.get(
    "/agents/runs/{run_id}/events",
    response_class=EventSourceResponse,
    response_description="Server-sent events; each data line is one AgentRunEvent",
)
def run_events(
    principal: AuthPrincipal = Depends(require_roles(*_OPERATOR_ROLES)),
    events: list[AgentRunEvent] = Depends(_known_run_events),
) -> Iterator[AgentRunEvent]:
    yield from events


@router.post("/agents/{agent_id}/autonomy", response_model=AgentCardResponse)
def change_autonomy(
    agent_id: str,
    request: AutonomyChangeRequest,
    principal: AuthPrincipal = Depends(require_roles(UserRole.OWNER_DIRECTOR)),
) -> AgentCardResponse:
    try:
        agent = stub.change_autonomy(agent_id, request)
    except stub.AutonomyChangeError as error:
        raise HTTPException(status_code=409, detail=error.code) from error
    except LookupError as error:
        raise HTTPException(status_code=404, detail="agent_not_found") from error
    return AgentCardResponse(data_mode=DataMode.STUB, agent=agent)


@router.post("/agents/kill-switch", response_model=AgentListResponse)
def kill_switch(
    request: KillSwitchRequest,
    principal: AuthPrincipal = Depends(require_roles(*_KILL_SWITCH_ROLES)),
) -> AgentListResponse:
    try:
        return stub.apply_kill_switch(request)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="agent_not_found") from error


@router.get("/agents/journey", response_model=JourneyResponse)
def journey(
    principal: AuthPrincipal = Depends(require_roles(*_ALL_ROLES)),
) -> JourneyResponse:
    return stub.journey()
