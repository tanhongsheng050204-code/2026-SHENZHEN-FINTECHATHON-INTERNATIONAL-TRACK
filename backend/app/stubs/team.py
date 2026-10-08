"""Stub Team page for the synthetic demo company.

Workstream B1 replaces it with user_roles (including job_functions) plus Supabase Auth.
The other stubs read job functions from here, so every position has a demo member.
"""

import datetime as dt
import uuid

from app.contracts.common import JobFunction
from app.contracts.team import InvitationRequest, MemberUpdateRequest, TeamMember
from app.schemas import UserRole

_NOW = dt.datetime(2026, 10, 14, 12, 0, tzinfo=dt.UTC)
OWNER_ID = "30000000-0000-0000-0000-000000000003"


class TeamError(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _member(
    user_id: str,
    name: str,
    email_masked: str,
    role: UserRole,
    job_functions: list[JobFunction],
    *,
    mfa: bool,
    last_active: dt.datetime,
) -> TeamMember:
    return TeamMember(
        user_id=user_id,
        display_name=name,
        email_masked=email_masked,
        role=role,
        job_functions=job_functions,
        active=True,
        mfa_enrolled=mfa,
        last_active_at=last_active,
    )


_MEMBERS: tuple[TeamMember, ...] = (
    _member(
        OWNER_ID,
        "Owner (demo)",
        "o***@finbrain-demo.test",
        UserRole.OWNER_DIRECTOR,
        [JobFunction.OWNER],
        mfa=True,
        last_active=_NOW,
    ),
    _member(
        "20000000-0000-0000-0000-000000000002",
        "Finance and HR clerk (demo)",
        "f***@finbrain-demo.test",
        UserRole.FINANCE_OPS,
        [JobFunction.FINANCE, JobFunction.HR],
        mfa=True,
        last_active=_NOW - dt.timedelta(hours=2),
    ),
    _member(
        "40000000-0000-0000-0000-000000000004",
        "Compliance officer (demo)",
        "c***@finbrain-demo.test",
        UserRole.COMPLIANCE,
        [JobFunction.COMPLIANCE],
        mfa=True,
        last_active=_NOW - dt.timedelta(days=1),
    ),
    _member(
        "10000000-0000-0000-0000-000000000001",
        "Sales and service executive (demo)",
        "e***@finbrain-demo.test",
        UserRole.GENERAL_EMPLOYEE,
        [JobFunction.SALES, JobFunction.CUSTOMER_SERVICE],
        mfa=False,
        last_active=_NOW - dt.timedelta(hours=3),
    ),
    _member(
        "50000000-0000-0000-0000-000000000005",
        "Operations manager (demo)",
        "m***@finbrain-demo.test",
        UserRole.FINANCE_OPS,
        [JobFunction.OPERATIONS],
        mfa=True,
        last_active=_NOW - dt.timedelta(hours=5),
    ),
    _member(
        "60000000-0000-0000-0000-000000000006",
        "Purchasing and stores executive (demo)",
        "p***@finbrain-demo.test",
        UserRole.GENERAL_EMPLOYEE,
        [JobFunction.PROCUREMENT, JobFunction.LOGISTICS],
        mfa=False,
        last_active=_NOW - dt.timedelta(hours=1),
    ),
    _member(
        "70000000-0000-0000-0000-000000000007",
        "Marketing executive (demo)",
        "k***@finbrain-demo.test",
        UserRole.GENERAL_EMPLOYEE,
        [JobFunction.MARKETING],
        mfa=False,
        last_active=_NOW - dt.timedelta(days=45),
    ),
)


def members() -> list[TeamMember]:
    return list(_MEMBERS)


def find_member(user_id: str) -> TeamMember | None:
    return next((m for m in _MEMBERS if m.user_id == user_id), None)


def job_functions_for(user_id: str) -> list[JobFunction]:
    member = find_member(user_id)
    return list(member.job_functions) if member else []


def _mask(email: str) -> str:
    local, domain = email.split("@", 1)
    return f"{local[0]}***@{domain}"


def invite(request: InvitationRequest) -> TeamMember:
    return TeamMember(
        user_id=str(uuid.uuid5(uuid.NAMESPACE_URL, request.email.casefold())),
        display_name="Invited user",
        email_masked=_mask(request.email),
        role=request.role,
        job_functions=request.job_functions,
        active=False,
        mfa_enrolled=False,
        last_active_at=None,
    )


def update_member(user_id: str, request: MemberUpdateRequest, actor_id: str) -> TeamMember:
    member = find_member(user_id)
    if member is None:
        raise TeamError("member_not_found", 404)
    if user_id == actor_id and request.active is False:
        raise TeamError("cannot_deactivate_self", 409)
    owners = [m for m in _MEMBERS if m.role == UserRole.OWNER_DIRECTOR and m.active]
    loses_owner = member.role == UserRole.OWNER_DIRECTOR and (
        request.active is False
        or (request.role is not None and request.role != UserRole.OWNER_DIRECTOR)
    )
    if loses_owner and len(owners) == 1:
        raise TeamError("last_owner_required", 409)
    role = request.role or member.role
    job_functions = request.job_functions or member.job_functions
    if JobFunction.OWNER in job_functions and role != UserRole.OWNER_DIRECTOR:
        raise TeamError("owner_function_requires_owner_role", 409)
    return member.model_copy(update=request.model_dump(exclude_none=True))


def sign_out(user_id: str) -> int:
    if find_member(user_id) is None:
        raise TeamError("member_not_found", 404)
    return 2
