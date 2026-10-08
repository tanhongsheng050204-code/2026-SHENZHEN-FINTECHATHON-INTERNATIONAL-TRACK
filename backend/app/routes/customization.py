from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import require_roles
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
from app.schemas import UserRole
from app.stubs import customization as stub

router = APIRouter(tags=["settings"])

_READ_ROLES = (UserRole.OWNER_DIRECTOR, UserRole.FINANCE_OPS, UserRole.COMPLIANCE)
_FINANCE_ROLES = (UserRole.OWNER_DIRECTOR, UserRole.FINANCE_OPS)


@router.get("/settings/message-templates", response_model=MessageTemplatesResponse)
def list_templates(
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
) -> MessageTemplatesResponse:
    return MessageTemplatesResponse(data_mode=DataMode.STUB, templates=stub.templates())


@router.post("/settings/message-templates", response_model=MessageTemplateResponse)
def create_template(
    request: MessageTemplateRequest,
    principal: AuthPrincipal = Depends(require_roles(*_FINANCE_ROLES)),
) -> MessageTemplateResponse:
    return MessageTemplateResponse(data_mode=DataMode.STUB, template=stub.create_template(request))


@router.post(
    "/settings/message-templates/{template_id}/approve", response_model=MessageTemplateResponse
)
def approve_template(
    template_id: str,
    principal: AuthPrincipal = Depends(require_roles(UserRole.OWNER_DIRECTOR)),
) -> MessageTemplateResponse:
    try:
        template = stub.approve_template(template_id)
    except stub.CustomizationError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return MessageTemplateResponse(data_mode=DataMode.STUB, template=template)


@router.get("/settings/import-mappings", response_model=ImportMappingsResponse)
def list_mappings(
    principal: AuthPrincipal = Depends(require_roles(*_FINANCE_ROLES)),
) -> ImportMappingsResponse:
    return ImportMappingsResponse(data_mode=DataMode.STUB, mappings=stub.mappings())


@router.post("/settings/import-mappings", response_model=ImportMappingResponse)
def create_mapping(
    request: ImportMappingRequest,
    principal: AuthPrincipal = Depends(require_roles(*_FINANCE_ROLES)),
) -> ImportMappingResponse:
    return ImportMappingResponse(data_mode=DataMode.STUB, mapping=stub.create_mapping(request))


@router.post("/settings/import-mappings/match", response_model=ImportMappingResponse)
def match_mapping(
    request: ImportMappingMatchRequest,
    principal: AuthPrincipal = Depends(require_roles(*_FINANCE_ROLES)),
) -> ImportMappingResponse:
    try:
        mapping = stub.match_mapping(request)
    except stub.CustomizationError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return ImportMappingResponse(data_mode=DataMode.STUB, mapping=mapping)


@router.get("/settings/alert-rules", response_model=AlertRulesResponse)
def list_rules(
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
) -> AlertRulesResponse:
    return AlertRulesResponse(data_mode=DataMode.STUB, rules=stub.rules())


@router.post("/settings/alert-rules", response_model=AlertRuleResponse)
def create_rule(
    request: AlertRuleRequest,
    principal: AuthPrincipal = Depends(require_roles(UserRole.OWNER_DIRECTOR)),
) -> AlertRuleResponse:
    return AlertRuleResponse(data_mode=DataMode.STUB, rule=stub.create_rule(request))
