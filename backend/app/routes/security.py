"""Security activity, each person's sign-ins, the incident register and the data
protection officer."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, require_roles, require_step_up
from app.auth.principal import AuthPrincipal
from app.contracts.common import DataMode
from app.contracts.security import (
    DpoRequest,
    DpoResponse,
    Incident,
    IncidentRequest,
    IncidentsResponse,
    IncidentStepRequest,
    NoticeRequest,
    NoticeResponse,
    SecurityActivityResponse,
    SignInsResponse,
)
from app.db import get_db
from app.schemas import UserRole
from app.services import incidents, security_activity

router = APIRouter(tags=["security"])

_OVERSIGHT = (UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)
_ALL = tuple(UserRole)


def _refuse(error: incidents.IncidentError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.code)


@router.get("/security/sign-ins", response_model=SignInsResponse)
def my_sign_ins(principal: CurrentUser, db: Session = Depends(get_db)) -> SignInsResponse:
    return SignInsResponse(
        data_mode=DataMode.LIVE,
        sign_ins=security_activity.sign_ins(db, str(principal.tenant_id), str(principal.user_id)),
    )


@router.get("/security/activity", response_model=SecurityActivityResponse)
def activity(
    principal: AuthPrincipal = Depends(require_roles(*_OVERSIGHT)),
    db: Session = Depends(get_db),
) -> SecurityActivityResponse:
    return SecurityActivityResponse(
        data_mode=DataMode.LIVE, events=security_activity.feed(db, str(principal.tenant_id))
    )


@router.get("/security/incidents", response_model=IncidentsResponse)
def list_incidents(
    principal: AuthPrincipal = Depends(require_roles(*_OVERSIGHT)),
    db: Session = Depends(get_db),
) -> IncidentsResponse:
    return IncidentsResponse(
        data_mode=DataMode.LIVE, incidents=incidents.incidents(db, str(principal.tenant_id))
    )


@router.post("/security/incidents", response_model=Incident)
def open_incident(
    request: IncidentRequest,
    principal: AuthPrincipal = Depends(require_step_up(*_OVERSIGHT)),
    db: Session = Depends(get_db),
) -> Incident:
    return incidents.open_incident(db, principal, request)


@router.post("/security/incidents/{incident_id}/steps", response_model=Incident)
def incident_step(
    incident_id: str,
    request: IncidentStepRequest,
    principal: AuthPrincipal = Depends(require_step_up(*_OVERSIGHT)),
    db: Session = Depends(get_db),
) -> Incident:
    try:
        return incidents.complete_step(db, principal, incident_id, request.step)
    except incidents.IncidentError as error:
        raise _refuse(error) from error


@router.post("/security/incidents/{incident_id}/notices", response_model=NoticeResponse)
def incident_notice(
    incident_id: str,
    request: NoticeRequest,
    principal: AuthPrincipal = Depends(require_step_up(*_OVERSIGHT)),
    db: Session = Depends(get_db),
) -> NoticeResponse:
    try:
        action_id = incidents.draft_notice(db, principal, incident_id, request.audience)
    except incidents.IncidentError as error:
        raise _refuse(error) from error
    return NoticeResponse(data_mode=DataMode.LIVE, action_id=action_id)


@router.get("/security/dpo", response_model=DpoResponse)
def data_protection_officer(
    principal: AuthPrincipal = Depends(require_roles(*_ALL)),
    db: Session = Depends(get_db),
) -> DpoResponse:
    return DpoResponse(
        data_mode=DataMode.LIVE, officer=incidents.officer(db, str(principal.tenant_id))
    )


@router.put("/security/dpo", response_model=DpoResponse)
def name_data_protection_officer(
    request: DpoRequest,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> DpoResponse:
    try:
        officer = incidents.name_officer(db, principal, request.user_id)
    except incidents.IncidentError as error:
        raise _refuse(error) from error
    return DpoResponse(data_mode=DataMode.LIVE, officer=officer)
