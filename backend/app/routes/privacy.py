from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles, require_step_up
from app.auth.principal import AuthPrincipal
from app.db import get_db
from app.schemas import PrivacyEraseResponse, PrivacyTokenResponse, UserRole
from app.security.detokenize import hash_query
from app.services.portability import export_customer
from app.services.privacy import erase_token, export_token

router = APIRouter(tags=["privacy"])


@router.get("/privacy/tokens/{token}", response_model=PrivacyTokenResponse)
def get_privacy_token(
    token: str,
    principal: AuthPrincipal = Depends(require_roles(UserRole.COMPLIANCE)),
    db: Session = Depends(get_db),
) -> PrivacyTokenResponse:
    try:
        return export_token(
            db,
            token,
            str(principal.tenant_id),
            role=principal.role,
            query_hash=hash_query(f"privacy-export:{token}"),
            actor_ref=principal.actor_ref,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/privacy/tokens/{token}/erase", response_model=PrivacyEraseResponse)
def erase_privacy_token(
    token: str,
    principal: AuthPrincipal = Depends(require_roles(UserRole.COMPLIANCE)),
    db: Session = Depends(get_db),
) -> PrivacyEraseResponse:
    try:
        return erase_token(
            db,
            token,
            str(principal.tenant_id),
            role=principal.role,
            actor_ref=principal.actor_ref,
        )
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/privacy/customers/{customer_id}/export")
def export_customer_data(
    customer_id: int,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.COMPLIANCE)),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """PDPA data portability: one customer's records as a JSON file, for Compliance."""
    try:
        document = export_customer(db, principal, customer_id)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return JSONResponse(
        document,
        headers={
            "Content-Disposition": f'attachment; filename="customer-{customer_id}-export.json"',
            "Cache-Control": "no-store",
        },
    )
