"""Which positions a person holds, reads and may decide for.

Plan 2 puts the person's job functions on the verified principal; before that they
come from the demo team roster. Owners hold every position; owners and Compliance
can read every position's items.
"""

import inspect

from app.auth.principal import AuthPrincipal
from app.contracts.common import JobFunction
from app.schemas import UserRole

_OVERSIGHT = (UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)


def held(principal: AuthPrincipal) -> list[JobFunction]:
    if hasattr(principal, "job_functions"):
        return [JobFunction(job) for job in principal.job_functions]
    from app.stubs import team

    return list(team.job_functions_for(str(principal.user_id)))


def scope(principal: AuthPrincipal) -> list[JobFunction]:
    """Positions this person works in."""
    return list(JobFunction) if principal.role == UserRole.OWNER_DIRECTOR else held(principal)


def readable(principal: AuthPrincipal) -> list[JobFunction]:
    """Positions whose items this person can see."""
    return list(JobFunction) if principal.role in _OVERSIGHT else held(principal)


def call_stub(function, *args, principal: AuthPrincipal):
    """Call a demo-company stub, passing job functions where its signature takes them."""
    if "job_functions" in inspect.signature(function).parameters:
        return function(*args, job_functions=tuple(job.value for job in held(principal)))
    return function(*args)
