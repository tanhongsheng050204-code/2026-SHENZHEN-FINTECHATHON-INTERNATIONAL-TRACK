import datetime as dt

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.db import get_db
from app.schemas import UserRole
from app.security import rate_limit
from app.services import alerts
from app.services.live_agents import _sees_exact

router = APIRouter(tags=["alerts"])


class AlertCheckResult(BaseModel):
    fired: list[str]


@router.post(
    "/alerts/check",
    response_model=AlertCheckResult,
    dependencies=[Depends(rate_limit.limit("alerts-check", 10, per_user=True))],
)
def check_alerts(
    principal: AuthPrincipal = Depends(
        require_roles(UserRole.OWNER_DIRECTOR, UserRole.FINANCE_OPS)
    ),
    db: Session = Depends(get_db),
) -> AlertCheckResult:
    """Check the saved alert rules now. Each rule still fires at most once a day."""
    fired = alerts.evaluate(db, str(principal.tenant_id), dt.date.today())
    exact = _sees_exact(principal)
    return AlertCheckResult(
        fired=[alerts.describe(item.metric, item.value, exact=exact) for item in fired]
    )
