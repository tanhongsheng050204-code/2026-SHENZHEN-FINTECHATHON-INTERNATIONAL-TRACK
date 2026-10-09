from datetime import UTC, datetime
from uuid import UUID

from app.auth.principal import AuthPrincipal
from app.models import DEFAULT_TENANT_ID
from app.schemas import UserRole

USER_IDS = {
    UserRole.GENERAL_EMPLOYEE: UUID("10000000-0000-0000-0000-000000000001"),
    UserRole.FINANCE_OPS: UUID("20000000-0000-0000-0000-000000000002"),
    UserRole.OWNER_DIRECTOR: UUID("30000000-0000-0000-0000-000000000003"),
    UserRole.COMPLIANCE: UUID("40000000-0000-0000-0000-000000000004"),
}

TENANT_A = UUID(DEFAULT_TENANT_ID)
TENANT_B = UUID("00000000-0000-0000-0000-000000000002")

ROLE_JOBS = {
    UserRole.OWNER_DIRECTOR: ("owner",),
    UserRole.FINANCE_OPS: ("finance", "hr"),
    UserRole.GENERAL_EMPLOYEE: ("sales", "customer_service"),
    UserRole.COMPLIANCE: ("compliance",),
}


def principal(
    role: UserRole = UserRole.GENERAL_EMPLOYEE, tenant_id: UUID = TENANT_A
) -> AuthPrincipal:
    return AuthPrincipal(
        user_id=USER_IDS[role],
        email=f"{role.value}@finbrain.test",
        role=role,
        tenant_id=tenant_id,
        job_functions=ROLE_JOBS[role],
        aal="aal2",
        mfa_verified_at=datetime.now(UTC),
    )
