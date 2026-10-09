from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.contracts.assistant import (
    AssistantCommand,
    AssistantPlan,
    Briefing,
    BriefingPreference,
    BriefingPreferenceRequest,
    BriefingSendResult,
)
from app.db import get_db
from app.schemas import UserRole
from app.security import rate_limit
from app.services import assistant, briefing, briefing_push

router = APIRouter(tags=["assistant"])


@router.post("/assistant/interpret", response_model=AssistantPlan)
def interpret(
    command: AssistantCommand,
    principal: AuthPrincipal = Depends(require_roles(*tuple(UserRole))),
    db: Session = Depends(get_db),
) -> AssistantPlan:
    """What DuitDuit understood. A plan to confirm, never an action already taken."""
    return assistant.interpret(db, principal, command.text)


@router.get("/assistant/briefing", response_model=Briefing)
def daily_briefing(
    principal: AuthPrincipal = Depends(require_roles(*tuple(UserRole))),
    db: Session = Depends(get_db),
) -> Briefing:
    """What needs this person today; exact amounts only for the cash roles."""
    return briefing.build(db, principal)


@router.get("/assistant/briefing/preferences", response_model=BriefingPreference)
def briefing_preferences(
    principal: AuthPrincipal = Depends(require_roles(*tuple(UserRole))),
    db: Session = Depends(get_db),
) -> BriefingPreference:
    return BriefingPreference(**briefing_push.preference(db, principal))


@router.put("/assistant/briefing/preferences", response_model=BriefingPreference)
def set_briefing_preferences(
    request: BriefingPreferenceRequest,
    principal: AuthPrincipal = Depends(require_roles(*tuple(UserRole))),
    db: Session = Depends(get_db),
) -> BriefingPreference:
    """Opt in or out of pushed briefings; contacts are stored encrypted."""
    saved = briefing_push.set_preference(
        db, principal, email=request.email, telegram_chat_id=request.telegram_chat_id
    )
    return BriefingPreference(**saved)


@router.post(
    "/assistant/briefing/send-now",
    response_model=BriefingSendResult,
    dependencies=[Depends(rate_limit.limit("briefing-send-now", 5))],
)
def send_briefing_now(
    principal: AuthPrincipal = Depends(require_roles(*tuple(UserRole))),
    db: Session = Depends(get_db),
) -> BriefingSendResult:
    """Send the signed-in person their own briefing now, to their chosen channels."""
    return BriefingSendResult(sent=briefing_push.send_now(db, principal))
