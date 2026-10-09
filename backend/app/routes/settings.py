from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles, require_step_up
from app.auth.principal import AuthPrincipal
from app.contracts.common import DataMode
from app.contracts.settings import (
    IndustryTemplateId,
    RollbackRequest,
    SettingsChangeRequest,
    SettingsChangeResponse,
    SettingsChangesResponse,
    SettingsResponse,
    SettingsSchemaResponse,
    TemplatePreview,
    TemplatesResponse,
    TenantSettings,
)
from app.db import get_db
from app.schemas import UserRole
from app.services import tenant_settings as service

router = APIRouter(tags=["settings"])

_READ_ROLES = (UserRole.OWNER_DIRECTOR, UserRole.FINANCE_OPS, UserRole.COMPLIANCE)


@router.get("/settings", response_model=SettingsResponse)
def get_settings(
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
    db: Session = Depends(get_db),
) -> SettingsResponse:
    return service.current(db, principal)


@router.get("/settings/schema", response_model=SettingsSchemaResponse)
def get_settings_schema(
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
    db: Session = Depends(get_db),
) -> SettingsSchemaResponse:
    return SettingsSchemaResponse(
        data_mode=DataMode.LIVE, json_schema=TenantSettings.model_json_schema()
    )


@router.get("/settings/changes", response_model=SettingsChangesResponse)
def list_changes(
    status: Literal["applied", "pending_approval", "rejected"] | None = Query(default=None),
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
    db: Session = Depends(get_db),
) -> SettingsChangesResponse:
    return SettingsChangesResponse(
        data_mode=DataMode.LIVE, changes=service.changes(db, principal, status)
    )


@router.post("/settings/changes", response_model=SettingsChangeResponse)
def propose_change(
    request: SettingsChangeRequest,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> SettingsChangeResponse:
    return service.propose(db, principal, request)


@router.post("/settings/changes/{change_id}/approve", response_model=SettingsChangeResponse)
def approve_change(
    change_id: str,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.COMPLIANCE)),
    db: Session = Depends(get_db),
) -> SettingsChangeResponse:
    return service.decide(db, principal, change_id, approve=True)


@router.post("/settings/changes/{change_id}/reject", response_model=SettingsChangeResponse)
def reject_change(
    change_id: str,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.COMPLIANCE)),
    db: Session = Depends(get_db),
) -> SettingsChangeResponse:
    return service.decide(db, principal, change_id, approve=False)


@router.post("/settings/rollback", response_model=SettingsChangeResponse)
def rollback(
    request: RollbackRequest,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> SettingsChangeResponse:
    return service.rollback(db, principal, request.version)


@router.get("/settings/templates", response_model=TemplatesResponse)
def list_templates(
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
    db: Session = Depends(get_db),
) -> TemplatesResponse:
    return service.templates(db, principal)


@router.post("/settings/templates/{template_id}/preview", response_model=TemplatePreview)
def preview_template(
    template_id: IndustryTemplateId,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> TemplatePreview:
    return service.preview_template(db, principal, template_id)


@router.post("/settings/templates/{template_id}/apply", response_model=SettingsChangeResponse)
def apply_template(
    template_id: IndustryTemplateId,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> SettingsChangeResponse:
    return service.apply_template(db, principal, template_id)
