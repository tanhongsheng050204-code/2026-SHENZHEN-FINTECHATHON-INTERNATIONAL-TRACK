from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.auth.principal import AuthPrincipal
from app.auth.provider import provider
from app.contracts.common import JobFunction
from app.contracts.team import InvitationRequest, MemberUpdateRequest, TeamMember
from app.models import AuthUserRole, BackendAuthSession, utcnow
from app.schemas import UserRole
from app.services.workflow_audit import write_workflow_event


def mask_email(email: str) -> str:
    if "@" not in email:
        return "[restricted]"
    local, domain = email.split("@", 1)
    return f"{local[:1]}***@{domain}"


def tenant_lock(db: Session, tenant_id: str) -> None:
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("select pg_advisory_xact_lock(hashtext(:key))"), {"key": f"plan2:{tenant_id}"}
        )


def audit(
    db: Session, principal: AuthPrincipal, event: str, resource: str, resource_id: str, **payload
):
    write_workflow_event(
        db,
        event_type=event,
        actor_role=principal.role.value,
        actor_ref=principal.actor_ref,
        resource_type=resource,
        resource_id=resource_id,
        event_payload=payload,
        tenant_id=str(principal.tenant_id),
    )


def member_view(row: AuthUserRole) -> TeamMember:
    return TeamMember(
        user_id=row.user_id,
        display_name=row.display_name,
        email_masked=row.email_masked,
        role=row.user_role,
        job_functions=row.job_functions,
        active=row.active,
        mfa_enrolled=row.mfa_enrolled,
        last_active_at=row.last_active_at,
    )


def members(db: Session, principal: AuthPrincipal) -> list[TeamMember]:
    return [
        member_view(row)
        for row in db.scalars(
            select(AuthUserRole)
            .where(AuthUserRole.tenant_id == str(principal.tenant_id))
            .order_by(AuthUserRole.created_at, AuthUserRole.user_id)
        )
    ]


def invite(db: Session, principal: AuthPrincipal, request: InvitationRequest) -> TeamMember:
    # The explicit invitation endpoint is the only operation here that sends email.
    result = provider.call("POST", "/invite", payload={"email": request.email}, admin=True)
    user_id = str(UUID(result["id"]))
    tenant_id = str(principal.tenant_id)
    tenant_lock(db, tenant_id)
    if db.get(AuthUserRole, (user_id, tenant_id)):
        raise HTTPException(409, "member_already_exists")
    row = AuthUserRole(
        user_id=user_id,
        tenant_id=tenant_id,
        user_role=request.role.value,
        job_functions=[job.value for job in request.job_functions],
        email_masked=mask_email(request.email),
        display_name="Invited member",
        active=True,
    )
    db.add(row)
    db.flush()
    audit(
        db,
        principal,
        "team.invited",
        "member",
        user_id,
        role=request.role.value,
        job_functions=row.job_functions,
    )
    db.commit()
    return member_view(row)


def find_member(db: Session, principal: AuthPrincipal, user_id: str) -> AuthUserRole:
    try:
        user_id = str(UUID(user_id))
    except ValueError as error:
        raise HTTPException(404, "member_not_found") from error
    row = db.scalar(
        select(AuthUserRole)
        .where(AuthUserRole.user_id == user_id, AuthUserRole.tenant_id == str(principal.tenant_id))
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "member_not_found")
    return row


def update_member(
    db: Session, principal: AuthPrincipal, user_id: str, request: MemberUpdateRequest
) -> TeamMember:
    tenant_lock(db, str(principal.tenant_id))
    row = find_member(db, principal, user_id)
    if row.user_id == str(principal.user_id) and request.active is False:
        raise HTTPException(409, "cannot_deactivate_self")
    role = request.role.value if request.role else row.user_role
    active = row.active if request.active is None else request.active
    jobs = (
        [job.value for job in request.job_functions] if request.job_functions else row.job_functions
    )
    if (
        row.active
        and row.user_role == "owner_director"
        and (not active or role != "owner_director")
    ):
        others = db.scalar(
            select(func.count())
            .select_from(AuthUserRole)
            .where(
                AuthUserRole.tenant_id == row.tenant_id,
                AuthUserRole.user_role == "owner_director",
                AuthUserRole.active.is_(True),
                AuthUserRole.user_id != row.user_id,
            )
        )
        if not others:
            raise HTTPException(409, "last_owner_required")
    if "owner" in jobs and role != "owner_director":
        raise HTTPException(409, "owner_function_requires_owner_role")
    if (row.user_role, row.active, row.job_functions) == (role, active, jobs):
        raise HTTPException(409, "no_changes")
    row.user_role, row.active, row.job_functions = role, active, jobs
    row.session_generation += 1
    row.updated_at = utcnow()
    audit(
        db,
        principal,
        "team.updated",
        "member",
        row.user_id,
        role=role,
        active=active,
        job_functions=jobs,
    )
    db.commit()
    return member_view(row)


def sign_out_member(db: Session, principal: AuthPrincipal, user_id: str) -> int:
    tenant_lock(db, str(principal.tenant_id))
    row = find_member(db, principal, user_id)
    count = db.scalar(
        select(func.count())
        .select_from(BackendAuthSession)
        .where(
            BackendAuthSession.user_id == row.user_id,
            BackendAuthSession.tenant_id == row.tenant_id,
            BackendAuthSession.revoked_at.is_(None),
            BackendAuthSession.expires_at > utcnow(),
            BackendAuthSession.generation == row.session_generation,
        )
    )
    row.session_generation += 1
    audit(db, principal, "team.sessions_revoked", "member", row.user_id, sessions_revoked=count)
    db.commit()
    return count


def job_scope(principal: AuthPrincipal, *, oversight=False) -> list[JobFunction]:
    if principal.role == UserRole.OWNER_DIRECTOR or (
        oversight and principal.role == UserRole.COMPLIANCE
    ):
        return list(JobFunction)
    return [JobFunction(job) for job in principal.job_functions]
