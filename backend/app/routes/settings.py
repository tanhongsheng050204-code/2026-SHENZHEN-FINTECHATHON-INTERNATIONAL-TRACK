from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.contracts.common import DataMode
from app.contracts.settings import (
    IndustryTemplateId,
    RollbackRequest,
    SettingsChangeRequest,
    SettingsChangeResponse,
    SettingsResponse,
    SettingsSchemaResponse,
    TemplatePreview,
    TemplatesResponse,
)
from app.schemas import UserRole
from app.stubs import settings as stub

router = APIRouter(tags=["settings"])

_READ_ROLES = (UserRole.OWNER_DIRECTOR, UserRole.FINANCE_OPS, UserRole.COMPLIANCE)


def _raise(error: stub.SettingsError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.detail)


@router.get("/settings", response_model=SettingsResponse)
def get_settings(
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
) -> SettingsResponse:
    return stub.current()


@router.get("/settings/schema", response_model=SettingsSchemaResponse)
def get_settings_schema(
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
) -> SettingsSchemaResponse:
    return stub.schema()


@router.post("/settings/changes", response_model=SettingsChangeResponse)
def propose_change(
    request: SettingsChangeRequest,
    principal: AuthPrincipal = Depends(require_roles(UserRole.OWNER_DIRECTOR)),
) -> SettingsChangeResponse:
    try:
        return stub.propose(request)
    except stub.SettingsError as error:
        raise _raise(error) from error


@router.post("/settings/changes/{change_id}/approve", response_model=SettingsChangeResponse)
def approve_change(
    change_id: str,
    principal: AuthPrincipal = Depends(require_roles(UserRole.COMPLIANCE)),
) -> SettingsChangeResponse:
    try:
        change = stub.approve(change_id)
    except stub.SettingsError as error:
        raise _raise(error) from error
    return SettingsChangeResponse(
        data_mode=DataMode.STUB, change=change, settings=stub.current().settings
    )


@router.post("/settings/rollback", response_model=SettingsResponse)
def rollback(
    request: RollbackRequest,
    principal: AuthPrincipal = Depends(require_roles(UserRole.OWNER_DIRECTOR)),
) -> SettingsResponse:
    try:
        return stub.rollback(request.version)
    except stub.SettingsError as error:
        raise _raise(error) from error


@router.get("/settings/templates", response_model=TemplatesResponse)
def list_templates(
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
) -> TemplatesResponse:
    return stub.templates()


@router.post("/settings/templates/{template_id}/preview", response_model=TemplatePreview)
def preview_template(
    template_id: IndustryTemplateId,
    principal: AuthPrincipal = Depends(require_roles(UserRole.OWNER_DIRECTOR)),
) -> TemplatePreview:
    return stub.preview_template(template_id)


@router.post("/settings/templates/{template_id}/apply", response_model=SettingsChangeResponse)
def apply_template(
    template_id: IndustryTemplateId,
    principal: AuthPrincipal = Depends(require_roles(UserRole.OWNER_DIRECTOR)),
) -> SettingsChangeResponse:
    return stub.apply_template(template_id)
