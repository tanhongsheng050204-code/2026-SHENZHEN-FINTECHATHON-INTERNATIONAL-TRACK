"""What DuitDuit did for this company, measured from its own records."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.contracts.value import ValueReport
from app.db import get_db
from app.schemas import UserRole
from app.services import business_day, value

router = APIRouter(tags=["value"])


@router.get("/value", response_model=ValueReport)
def value_report(
    principal: AuthPrincipal = Depends(
        require_roles(UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)
    ),
    db: Session = Depends(get_db),
) -> ValueReport:
    return value.report(db, principal, business_day.today(db, principal.tenant_id))
