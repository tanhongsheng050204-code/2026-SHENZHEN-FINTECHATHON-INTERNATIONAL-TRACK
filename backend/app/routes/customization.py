from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles, require_step_up
from app.auth.principal import AuthPrincipal
from app.contracts.common import DataMode
from app.contracts.customization import (
    AlertRuleRequest,
    AlertRuleResponse,
    AlertRulesResponse,
    ImportMappingMatchRequest,
    ImportMappingRequest,
    ImportMappingResponse,
    ImportMappingsResponse,
    MessageTemplateRequest,
    MessageTemplateResponse,
    MessageTemplatesResponse,
)
from app.db import get_db
from app.schemas import UserRole
from app.services import customization as service
from app.services import import_mappings

router = APIRouter(tags=["settings"])

_READ_ROLES = (UserRole.OWNER_DIRECTOR, UserRole.FINANCE_OPS, UserRole.COMPLIANCE)
_FINANCE_ROLES = (UserRole.OWNER_DIRECTOR, UserRole.FINANCE_OPS)


@router.get("/settings/message-templates", response_model=MessageTemplatesResponse)
def list_templates(
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
    db: Session = Depends(get_db),
) -> MessageTemplatesResponse:
    return MessageTemplatesResponse(
        data_mode=DataMode.LIVE, templates=service.list_items(db, principal, "message_template")
    )


@router.post("/settings/message-templates", response_model=MessageTemplateResponse)
def create_template(
    request: MessageTemplateRequest,
    principal: AuthPrincipal = Depends(require_step_up(*_FINANCE_ROLES)),
    db: Session = Depends(get_db),
) -> MessageTemplateResponse:
    return MessageTemplateResponse(
        data_mode=DataMode.LIVE, template=service.create_template(db, principal, request)
    )


@router.post(
    "/settings/message-templates/{template_id}/approve", response_model=MessageTemplateResponse
)
def approve_template(
    template_id: str,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> MessageTemplateResponse:
    template = service.approve_template(db, principal, template_id)
    return MessageTemplateResponse(data_mode=DataMode.LIVE, template=template)


@router.get("/settings/import-mappings", response_model=ImportMappingsResponse)
def list_mappings(
    principal: AuthPrincipal = Depends(require_roles(*_FINANCE_ROLES)),
    db: Session = Depends(get_db),
) -> ImportMappingsResponse:
    return ImportMappingsResponse(
        data_mode=DataMode.LIVE, mappings=import_mappings.list_mappings(db, principal)
    )


@router.post("/settings/import-mappings", response_model=ImportMappingResponse)
def create_mapping(
    request: ImportMappingRequest,
    principal: AuthPrincipal = Depends(require_step_up(*_FINANCE_ROLES)),
    db: Session = Depends(get_db),
) -> ImportMappingResponse:
    return ImportMappingResponse(
        data_mode=DataMode.LIVE, mapping=import_mappings.save(db, principal, request)
    )


@router.post("/settings/import-mappings/match", response_model=ImportMappingResponse)
def match_mapping(
    request: ImportMappingMatchRequest,
    principal: AuthPrincipal = Depends(require_roles(*_FINANCE_ROLES)),
    db: Session = Depends(get_db),
) -> ImportMappingResponse:
    mapping = import_mappings.match(
        db, str(principal.tenant_id), request.schema_name, request.headers
    )
    if mapping is None:
        raise HTTPException(404, "no_matching_mapping")
    return ImportMappingResponse(data_mode=DataMode.LIVE, mapping=import_mappings.view(mapping))


@router.get("/settings/alert-rules", response_model=AlertRulesResponse)
def list_rules(
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
    db: Session = Depends(get_db),
) -> AlertRulesResponse:
    return AlertRulesResponse(
        data_mode=DataMode.LIVE, rules=service.list_items(db, principal, "alert_rule")
    )


@router.post("/settings/alert-rules", response_model=AlertRuleResponse)
def create_rule(
    request: AlertRuleRequest,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> AlertRuleResponse:
    return AlertRuleResponse(
        data_mode=DataMode.LIVE, rule=service.create_rule(db, principal, request)
    )
