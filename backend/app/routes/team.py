from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles, require_step_up
from app.auth.principal import AuthPrincipal
from app.contracts.common import DataMode
from app.contracts.team import (
    InvitationRequest,
    MemberResponse,
    MemberUpdateRequest,
    SignOutResponse,
    TeamResponse,
)
from app.db import get_db
from app.schemas import UserRole
from app.services import identity

router = APIRouter(tags=["team"])

_OVERSIGHT_ROLES = (UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)


@router.get("/team/members", response_model=TeamResponse)
def team_members(
    principal: AuthPrincipal = Depends(require_roles(*_OVERSIGHT_ROLES)),
    db: Session = Depends(get_db),
) -> TeamResponse:
    return TeamResponse(data_mode=DataMode.LIVE, members=identity.members(db, principal))


@router.post("/team/invitations", response_model=MemberResponse)
def invite_member(
    request: InvitationRequest,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> MemberResponse:
    return MemberResponse(data_mode=DataMode.LIVE, member=identity.invite(db, principal, request))


@router.patch("/team/members/{user_id}", response_model=MemberResponse)
def update_member(
    user_id: str,
    request: MemberUpdateRequest,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> MemberResponse:
    return MemberResponse(
        data_mode=DataMode.LIVE, member=identity.update_member(db, principal, user_id, request)
    )


@router.post("/team/members/{user_id}/sign-out", response_model=SignOutResponse)
def sign_out_member(
    user_id: str,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> SignOutResponse:
    revoked = identity.sign_out_member(db, principal, user_id)
    return SignOutResponse(data_mode=DataMode.LIVE, user_id=user_id, sessions_revoked=revoked)
