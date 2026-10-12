"""Unusual bills and payments, and privacy-protected benchmarks."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles
from app.auth.principal import AuthPrincipal
from app.contracts.common import DataMode
from app.contracts.insights import (
    AnomaliesResponse,
    AnomalyReviewResponse,
    BenchmarksResponse,
    PolicyChecksResponse,
)
from app.db import get_db
from app.schemas import UserRole
from app.services import anomalies, benchmarks, policy_checks

router = APIRouter(tags=["insights"])

_MONEY_READ = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)
_MONEY_WORK = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR)


@router.get("/insights/anomalies", response_model=AnomaliesResponse)
def list_anomalies(
    principal: AuthPrincipal = Depends(require_roles(*_MONEY_READ)),
    db: Session = Depends(get_db),
) -> AnomaliesResponse:
    found = anomalies.scan(db, str(principal.tenant_id))
    return AnomaliesResponse(
        data_mode=DataMode.LIVE,
        findings=found.findings,
        bills_checked=found.bills_checked,
        payments_checked=found.payments_checked,
    )


@router.post("/insights/anomalies/{ref}/review", response_model=AnomalyReviewResponse)
def send_anomaly_for_review(
    ref: str,
    principal: AuthPrincipal = Depends(require_roles(*_MONEY_WORK)),
    db: Session = Depends(get_db),
) -> AnomalyReviewResponse:
    try:
        action_id = anomalies.send_for_review(db, principal, ref)
    except anomalies.AnomalyError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return AnomalyReviewResponse(data_mode=DataMode.LIVE, action_id=action_id)


@router.get("/insights/checks/{action_id}", response_model=PolicyChecksResponse)
def review_item_checks(
    action_id: str,
    principal: AuthPrincipal = Depends(require_roles(*UserRole)),
    db: Session = Depends(get_db),
) -> PolicyChecksResponse:
    """The checker agent's findings on one review item the person can see."""
    try:
        checks = policy_checks.check(db, principal, action_id)
    except policy_checks.CheckError as error:
        raise HTTPException(status_code=error.status_code, detail=error.code) from error
    return PolicyChecksResponse(data_mode=DataMode.LIVE, action_id=action_id, checks=checks)


@router.get("/insights/benchmarks", response_model=BenchmarksResponse)
def peer_benchmarks(
    principal: AuthPrincipal = Depends(require_roles(*_MONEY_READ)),
    db: Session = Depends(get_db),
) -> BenchmarksResponse:
    """Your collection speed against other companies', with differential privacy."""
    return benchmarks.report(db, str(principal.tenant_id))
