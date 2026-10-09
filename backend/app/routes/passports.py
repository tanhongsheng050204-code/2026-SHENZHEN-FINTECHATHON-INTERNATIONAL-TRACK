from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import require_roles, require_step_up
from app.auth.principal import AuthPrincipal
from app.contracts.common import DataMode
from app.contracts.passports import (
    AuditPackListResponse,
    AuditPackRequest,
    AuditPackResponse,
    ExternalGrantResponse,
    ExternalGrantsResponse,
    GrantRequest,
    Passport,
    PassportListResponse,
    PassportResponse,
    VerificationResult,
)
from app.schemas import UserRole
from app.stubs import passports as stub

router = APIRouter(tags=["passports"])

_READ_ROLES = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)
_PREPARE_ROLES = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR)


@router.post("/passports", response_model=PassportResponse)
def issue_passport(
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
) -> PassportResponse:
    return stub.issue()


@router.get("/passports", response_model=PassportListResponse)
def list_passports(
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
) -> PassportListResponse:
    return PassportListResponse(data_mode=DataMode.STUB, passports=stub.list_passports())


@router.get("/passports/{passport_id}", response_model=PassportResponse)
def get_passport(
    passport_id: str,
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
) -> PassportResponse:
    try:
        return stub.get(passport_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="passport_not_found") from error


@router.get("/passports/{passport_id}/grants", response_model=ExternalGrantsResponse)
def list_lender_grants(
    passport_id: str,
    principal: AuthPrincipal = Depends(require_roles(UserRole.OWNER_DIRECTOR)),
) -> ExternalGrantsResponse:
    try:
        grants = stub.list_grants("lender", passport_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="passport_not_found") from error
    return ExternalGrantsResponse(data_mode=DataMode.STUB, grants=grants)


@router.get("/audit-packs", response_model=AuditPackListResponse)
def list_audit_packs(
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
) -> AuditPackListResponse:
    return AuditPackListResponse(data_mode=DataMode.STUB, packs=stub.list_audit_packs())


@router.get("/audit-packs/{pack_id}/grants", response_model=ExternalGrantsResponse)
def list_auditor_grants(
    pack_id: str,
    principal: AuthPrincipal = Depends(require_roles(UserRole.OWNER_DIRECTOR)),
) -> ExternalGrantsResponse:
    try:
        grants = stub.list_grants("auditor", pack_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="audit_pack_not_found") from error
    return ExternalGrantsResponse(data_mode=DataMode.STUB, grants=grants)


@router.post("/passports/{passport_id}/grants", response_model=ExternalGrantResponse)
def grant_lender(
    passport_id: str,
    request: GrantRequest,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
) -> ExternalGrantResponse:
    try:
        grant = stub.create_grant("lender", passport_id, request, str(principal.tenant_id))
    except LookupError as error:
        raise HTTPException(status_code=404, detail="passport_not_found") from error
    return ExternalGrantResponse(data_mode=DataMode.STUB, grant=grant)


@router.delete("/passports/{passport_id}/grants/{grant_id}", response_model=ExternalGrantResponse)
def revoke_lender(
    passport_id: str,
    grant_id: str,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
) -> ExternalGrantResponse:
    try:
        grant = stub.revoke_grant("lender", passport_id, grant_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="grant_not_found") from error
    return ExternalGrantResponse(data_mode=DataMode.STUB, grant=grant)


@router.post("/lender/verify", response_model=VerificationResult)
def verify_passport(document: Passport) -> VerificationResult:
    """Public: anyone holding a Passport document can check it against the audit chain."""
    return stub.verify(document)


@router.get("/lender/passports/{grant_token}", response_model=PassportResponse)
def lender_passport(grant_token: str) -> PassportResponse:
    """Public in the stub. Workstream B1 adds the expiring grant and, in Wave 2, email codes."""
    try:
        return stub.lender_view(grant_token)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="grant_not_found") from error


@router.post("/audit-packs", response_model=AuditPackResponse)
def prepare_audit_pack(
    request: AuditPackRequest,
    principal: AuthPrincipal = Depends(require_roles(*_PREPARE_ROLES)),
) -> AuditPackResponse:
    return stub.prepare_audit_pack(request.period)


@router.get("/audit-packs/{pack_id}", response_model=AuditPackResponse)
def get_audit_pack(
    pack_id: str,
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
) -> AuditPackResponse:
    try:
        return stub.get_audit_pack(pack_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="audit_pack_not_found") from error


@router.post("/audit-packs/{pack_id}/grants", response_model=ExternalGrantResponse)
def grant_auditor(
    pack_id: str,
    request: GrantRequest,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
) -> ExternalGrantResponse:
    try:
        grant = stub.create_grant("auditor", pack_id, request, str(principal.tenant_id))
    except LookupError as error:
        raise HTTPException(status_code=404, detail="audit_pack_not_found") from error
    return ExternalGrantResponse(data_mode=DataMode.STUB, grant=grant)


@router.delete("/audit-packs/{pack_id}/grants/{grant_id}", response_model=ExternalGrantResponse)
def revoke_auditor(
    pack_id: str,
    grant_id: str,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
) -> ExternalGrantResponse:
    try:
        grant = stub.revoke_grant("auditor", pack_id, grant_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="grant_not_found") from error
    return ExternalGrantResponse(data_mode=DataMode.STUB, grant=grant)


@router.get("/auditor/packs/{grant_token}", response_model=AuditPackResponse)
def auditor_pack(grant_token: str) -> AuditPackResponse:
    """Public in the stub. Workstream B1 adds the expiring grant check."""
    try:
        return stub.auditor_view(grant_token)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="grant_not_found") from error
