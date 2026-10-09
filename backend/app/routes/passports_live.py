"""Passport, audit packs and external grants on the tenant's audit chain (Plan 6).

Registered before app.routes.passports, so these handlers serve every path there;
the stub handlers no longer receive requests and are hidden from the published
schema here only to avoid duplicate operation ids (same paths and models).

Issuing and sharing use the step-up (recent TOTP) dependency where Plan 2 provides
it, and plain role checks before then.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import dependencies
from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
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
from app.db import get_db
from app.schemas import UserRole
from app.security import rate_limit
from app.services import external_grants, passports

router = APIRouter(tags=["passports"])

_READ_ROLES = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)
_PREPARE_ROLES = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR)
_owner_gate = getattr(dependencies, "require_step_up", require_roles)(UserRole.OWNER_DIRECTOR)
_hidden = {"include_in_schema": False}
# Unauthenticated endpoints: bound guessing of links and Passport ids per client.
_public_limit = Depends(rate_limit.limit("public-share", 30))


def _mode(db, principal: AuthPrincipal):
    return passports.data_mode_of(db, principal)


def _passport_or_404(db, principal: AuthPrincipal, passport_id: str) -> Passport:
    try:
        return passports.get(db, str(principal.tenant_id), passport_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="passport_not_found") from error


def _pack_or_404(db, principal: AuthPrincipal, pack_id: str):
    try:
        return passports.get_pack(db, str(principal.tenant_id), pack_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="audit_pack_not_found") from error


@router.post("/passports", response_model=PassportResponse, **_hidden)
def issue_passport(
    principal: AuthPrincipal = Depends(_owner_gate), db: Session = Depends(get_db)
) -> PassportResponse:
    passport = passports.issue(db, principal)
    return PassportResponse(data_mode=_mode(db, principal), passport=passport)


@router.get("/passports", response_model=PassportListResponse, **_hidden)
def list_passports(
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PassportListResponse:
    return PassportListResponse(
        data_mode=_mode(db, principal),
        passports=passports.list_for(db, str(principal.tenant_id)),
    )


@router.get("/passports/{passport_id}", response_model=PassportResponse, **_hidden)
def get_passport(
    passport_id: str,
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
    db: Session = Depends(get_db),
) -> PassportResponse:
    passport = _passport_or_404(db, principal, passport_id)
    return PassportResponse(data_mode=_mode(db, principal), passport=passport)


@router.get("/passports/{passport_id}/grants", response_model=ExternalGrantsResponse, **_hidden)
def list_lender_grants(
    passport_id: str,
    principal: AuthPrincipal = Depends(require_roles(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> ExternalGrantsResponse:
    _passport_or_404(db, principal, passport_id)
    grants = external_grants.list_for(db, str(principal.tenant_id), "lender", passport_id)
    return ExternalGrantsResponse(data_mode=_mode(db, principal), grants=grants)


@router.post("/passports/{passport_id}/grants", response_model=ExternalGrantResponse, **_hidden)
def grant_lender(
    passport_id: str,
    request: GrantRequest,
    principal: AuthPrincipal = Depends(_owner_gate),
    db: Session = Depends(get_db),
) -> ExternalGrantResponse:
    _passport_or_404(db, principal, passport_id)
    grant = external_grants.create(db, principal, "lender", passport_id, request)
    return ExternalGrantResponse(data_mode=_mode(db, principal), grant=grant)


@router.delete(
    "/passports/{passport_id}/grants/{grant_id}", response_model=ExternalGrantResponse, **_hidden
)
def revoke_lender(
    passport_id: str,
    grant_id: str,
    principal: AuthPrincipal = Depends(_owner_gate),
    db: Session = Depends(get_db),
) -> ExternalGrantResponse:
    try:
        grant = external_grants.revoke(db, principal, "lender", passport_id, grant_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="grant_not_found") from error
    return ExternalGrantResponse(data_mode=_mode(db, principal), grant=grant)


@router.post(
    "/lender/verify", response_model=VerificationResult, **_hidden, dependencies=[_public_limit]
)
def verify_passport(document: Passport, db: Session = Depends(get_db)) -> VerificationResult:
    """Public: anyone holding a Passport document can check it against the audit chain."""
    return passports.verify(db, document)


def _open(db, kind, token: str):
    try:
        return external_grants.open_link(db, kind, token)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="grant_not_found") from error
    except external_grants.GrantClosed as closed:
        raise HTTPException(status_code=410, detail=closed.code) from closed


@router.get(
    "/lender/passports/{grant_token}",
    response_model=PassportResponse,
    **_hidden,
    dependencies=[_public_limit],
)
def lender_passport(grant_token: str, db: Session = Depends(get_db)) -> PassportResponse:
    """Public with a valid, unexpired, unrevoked link; every view is audited."""
    opened = _open(db, "lender", grant_token)
    entries = passports._issued(db, tenant_id=opened.tenant_id, passport_id=opened.scope_id)
    if not entries:
        raise HTTPException(status_code=404, detail="grant_not_found")
    return PassportResponse(data_mode="live", passport=passports._passport(db, entries[0]))


@router.get("/audit-packs", response_model=AuditPackListResponse, **_hidden)
def list_audit_packs(
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
    db: Session = Depends(get_db),
) -> AuditPackListResponse:
    return AuditPackListResponse(
        data_mode=_mode(db, principal), packs=passports.list_packs(db, str(principal.tenant_id))
    )


@router.post("/audit-packs", response_model=AuditPackResponse, **_hidden)
def prepare_audit_pack(
    request: AuditPackRequest,
    principal: AuthPrincipal = Depends(require_roles(*_PREPARE_ROLES)),
    db: Session = Depends(get_db),
) -> AuditPackResponse:
    pack = passports.prepare_pack(db, principal, request.period)
    return AuditPackResponse(data_mode=_mode(db, principal), pack=pack)


@router.get("/audit-packs/{pack_id}", response_model=AuditPackResponse, **_hidden)
def get_audit_pack(
    pack_id: str,
    principal: AuthPrincipal = Depends(require_roles(*_READ_ROLES)),
    db: Session = Depends(get_db),
) -> AuditPackResponse:
    return AuditPackResponse(
        data_mode=_mode(db, principal), pack=_pack_or_404(db, principal, pack_id)
    )


@router.get("/audit-packs/{pack_id}/grants", response_model=ExternalGrantsResponse, **_hidden)
def list_auditor_grants(
    pack_id: str,
    principal: AuthPrincipal = Depends(require_roles(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> ExternalGrantsResponse:
    _pack_or_404(db, principal, pack_id)
    grants = external_grants.list_for(db, str(principal.tenant_id), "auditor", pack_id)
    return ExternalGrantsResponse(data_mode=_mode(db, principal), grants=grants)


@router.post("/audit-packs/{pack_id}/grants", response_model=ExternalGrantResponse, **_hidden)
def grant_auditor(
    pack_id: str,
    request: GrantRequest,
    principal: AuthPrincipal = Depends(_owner_gate),
    db: Session = Depends(get_db),
) -> ExternalGrantResponse:
    _pack_or_404(db, principal, pack_id)
    grant = external_grants.create(db, principal, "auditor", pack_id, request)
    return ExternalGrantResponse(data_mode=_mode(db, principal), grant=grant)


@router.delete(
    "/audit-packs/{pack_id}/grants/{grant_id}", response_model=ExternalGrantResponse, **_hidden
)
def revoke_auditor(
    pack_id: str,
    grant_id: str,
    principal: AuthPrincipal = Depends(_owner_gate),
    db: Session = Depends(get_db),
) -> ExternalGrantResponse:
    try:
        grant = external_grants.revoke(db, principal, "auditor", pack_id, grant_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="grant_not_found") from error
    return ExternalGrantResponse(data_mode=_mode(db, principal), grant=grant)


@router.get(
    "/auditor/packs/{grant_token}",
    response_model=AuditPackResponse,
    **_hidden,
    dependencies=[_public_limit],
)
def auditor_pack(grant_token: str, db: Session = Depends(get_db)) -> AuditPackResponse:
    """Public with a valid, unexpired, unrevoked link; every view is audited."""
    opened = _open(db, "auditor", grant_token)
    entries = passports._packs(db, tenant_id=opened.tenant_id, pack_id=opened.scope_id)
    if not entries:
        raise HTTPException(status_code=404, detail="grant_not_found")
    return AuditPackResponse(data_mode="live", pack=passports._pack(entries[0]))
