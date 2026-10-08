from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.contracts.common import DataMode
from app.contracts.team import (
    InvitationRequest,
    MemberResponse,
    MemberUpdateRequest,
    SignOutResponse,
    TeamResponse,
)
from app.schemas import UserRole
from app.stubs import team as stub

router = APIRouter(tags=["team"])

_OVERSIGHT_ROLES = (UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)


@router.get("/team/members", response_model=TeamResponse)
def team_members(
    principal: AuthPrincipal = Depends(require_roles(*_OVERSIGHT_ROLES)),
) -> TeamResponse:
    return TeamResponse(data_mode=DataMode.STUB, members=stub.members())


@router.post("/team/invitations", response_model=MemberResponse)
def invite_member(
    request: InvitationRequest,
    principal: AuthPrincipal = Depends(require_roles(UserRole.OWNER_DIRECTOR)),
) -> MemberResponse:
    return MemberResponse(data_mode=DataMode.STUB, member=stub.invite(request))


@router.patch("/team/members/{user_id}", response_model=MemberResponse)
def update_member(
    user_id: str,
    request: MemberUpdateRequest,
    principal: AuthPrincipal = Depends(require_roles(UserRole.OWNER_DIRECTOR)),
) -> MemberResponse:
    try:
        member = stub.update_member(user_id, request, str(principal.user_id))
    except stub.TeamError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return MemberResponse(data_mode=DataMode.STUB, member=member)


@router.post("/team/members/{user_id}/sign-out", response_model=SignOutResponse)
def sign_out_member(
    user_id: str,
    principal: AuthPrincipal = Depends(require_roles(UserRole.OWNER_DIRECTOR)),
) -> SignOutResponse:
    try:
        revoked = stub.sign_out(user_id)
    except stub.TeamError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return SignOutResponse(data_mode=DataMode.STUB, user_id=user_id, sessions_revoked=revoked)
