from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.contracts.assistant import AssistantCommand, AssistantPlan
from app.db import get_db
from app.schemas import UserRole
from app.services import assistant

router = APIRouter(tags=["assistant"])


@router.post("/assistant/interpret", response_model=AssistantPlan)
def interpret(
    command: AssistantCommand,
    principal: AuthPrincipal = Depends(require_roles(*tuple(UserRole))),
    db: Session = Depends(get_db),
) -> AssistantPlan:
    """What DuitDuit understood. A plan to confirm, never an action already taken."""
    return assistant.interpret(db, principal, command.text)
