from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.contracts.common import JobFunction
from app.contracts.positions import PositionsResponse, PositionWorkspace
from app.schemas import UserRole
from app.stubs import positions as stub

router = APIRouter(tags=["positions"])

_ALL_ROLES = tuple(UserRole)


@router.get("/positions", response_model=PositionsResponse)
def list_positions(
    principal: AuthPrincipal = Depends(require_roles(*_ALL_ROLES)),
) -> PositionsResponse:
    return stub.positions(principal.role, str(principal.user_id))


@router.get("/positions/{job_function}/workspace", response_model=PositionWorkspace)
def position_workspace(
    job_function: JobFunction,
    principal: AuthPrincipal = Depends(require_roles(*_ALL_ROLES)),
) -> PositionWorkspace:
    try:
        return stub.workspace(job_function, principal.role, str(principal.user_id))
    except stub.PositionError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
