"""Agent runs served by the Supervisor runtime (app.services.agent_runtime).

Registered before app.routes.agents, so these handlers answer POST /agents/runs and
its event stream; the stub handlers there no longer receive requests. They stay in
the published schema (same paths and models) until they are deleted, so these are
hidden from it to avoid duplicate operation ids.
"""

from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.sse import EventSourceResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.contracts.agents import AgentRunCreated, AgentRunEvent, AgentRunRequest
from app.db import get_db
from app.schemas import UserRole
from app.services import agent_runtime

router = APIRouter(tags=["agents"])

_OPERATOR_ROLES = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR)


@router.post("/agents/runs", response_model=AgentRunCreated, include_in_schema=False)
def start_run(
    request: AgentRunRequest,
    principal: AuthPrincipal = Depends(require_roles(*_OPERATOR_ROLES)),
    db: Session = Depends(get_db),
) -> AgentRunCreated:
    return agent_runtime.start_run(db, principal, request.goal)


def _run_events(
    run_id: str,
    principal: AuthPrincipal = Depends(require_roles(*_OPERATOR_ROLES)),
    db: Session = Depends(get_db),
) -> list[AgentRunEvent]:
    # A dependency, so an unknown run or a refused tool fails before the stream starts.
    try:
        return agent_runtime.run_events(db, principal, run_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="run_not_found") from error


@router.get(
    "/agents/runs/{run_id}/events",
    response_class=EventSourceResponse,
    include_in_schema=False,
)
def run_events(events: list[AgentRunEvent] = Depends(_run_events)) -> Iterator[AgentRunEvent]:
    yield from events
