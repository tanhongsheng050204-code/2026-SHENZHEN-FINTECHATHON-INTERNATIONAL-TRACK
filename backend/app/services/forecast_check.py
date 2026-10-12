"""Forecast check: keep each day's forecast, then score it against the bank balance.

The forecast is deterministic, so its accuracy is a matter of record, not a claim.
The first time a company's live forecast is built on a given day, its likely, best
and worst balances 7, 14 and 30 days ahead are kept as a "forecast_snapshot" event
on the company's workflow chain (amounts only, no names). Once an imported bank
statement covers a target day, the balance at the end of that day is compared:
how far the likely balance was off, the accuracy (1 - |likely - actual| / actual),
and whether the real balance fell inside the best-to-worst range. The largest
differences are listed with the money in and out the forecast expected by that day,
so a person can see where to look.

Calibrated range (split conformal prediction): once a horizon has MIN_CALIBRATION
comparisons, the likely balance ± the ceil((n + 1) × 0.8)-th smallest past miss is
a range that held at least 80% of the time on this company's own days, with no
assumption about how errors are distributed. Fewer comparisons: not measured.

Nothing is scored until a statement covers a target day, and the synthetic demo
company is never scored: its figures are made up, so any accuracy would be too.
"""

import datetime as dt
import math
from decimal import Decimal

from sqlalchemy import func, select

from app.contracts.cashflow import (
    ForecastCheckHorizon,
    ForecastCheckResponse,
    ForecastDifference,
    ForecastResponse,
)
from app.contracts.common import DataMode
from app.models import BankTransaction, WorkflowAuditEntry
from app.services.workflow_audit import chain_scalar, chain_scalars, write_workflow_event

TARGET_DAYS = (7, 14, 30)
LARGEST_SHOWN = 3
MIN_CALIBRATION = 5
COVERAGE = Decimal("0.8")
EVENT = "forecast_snapshot"
_CENT = Decimal("0.01")


def _snapshots(db, tenant_id: str) -> list[WorkflowAuditEntry]:
    return chain_scalars(
        db,
        select(WorkflowAuditEntry)
        .where(WorkflowAuditEntry.tenant_id == tenant_id, WorkflowAuditEntry.event_type == EVENT)
        .order_by(WorkflowAuditEntry.id),
    )


def record(db, tenant_id: str, forecast: ForecastResponse) -> None:
    """Keep today's live forecast once; synthetic forecasts are never kept."""
    if forecast.data_mode != DataMode.LIVE:
        return
    day = forecast.as_of.isoformat()
    exists = chain_scalar(
        db,
        select(WorkflowAuditEntry.id)
        .where(
            WorkflowAuditEntry.tenant_id == tenant_id,
            WorkflowAuditEntry.event_type == EVENT,
            WorkflowAuditEntry.resource_id == day,
        )
        .limit(1),
    )
    if exists is not None:
        return
    points = {point.day: point for point in forecast.points}

    def expected(kind: str, days: int) -> str:
        total = sum(
            (
                d.amount_myr
                for d in forecast.drivers
                if d.kind == kind and d.likely_day is not None and d.likely_day <= days
            ),
            Decimal(0),
        )
        return str(total.quantize(_CENT))

    targets = [
        {
            "horizon_days": days,
            "date": points[days].date.isoformat(),
            "likely": str(points[days].likely.quantize(_CENT)),
            "best": str(points[days].best.quantize(_CENT)),
            "worst": str(points[days].worst.quantize(_CENT)),
            "expected_in": expected("inflow", days),
            "expected_out": expected("outflow", days),
        }
        for days in TARGET_DAYS
        if days in points
    ]
    if not targets:
        return
    write_workflow_event(
        db,
        event_type=EVENT,
        actor_role="system",
        actor_ref="system:forecast_check",
        resource_type="cash_forecast",
        resource_id=day,
        event_payload={"as_of": day, "targets": targets},
        tenant_id=tenant_id,
    )
    db.commit()


def _balance_at_end_of(db, tenant_id: str, day: dt.date) -> Decimal | None:
    bank = BankTransaction
    row = db.scalar(
        select(bank)
        .where(bank.tenant_id == tenant_id, bank.posted_on <= day, bank.balance.is_not(None))
        .order_by(bank.posted_on.desc(), bank.id.desc())
        .limit(1)
    )
    return None if row is None else Decimal(row.balance)


def _conformal(misses: list[Decimal]) -> Decimal | None:
    n = len(misses)
    if n < MIN_CALIBRATION:
        return None
    rank = math.ceil((n + 1) * COVERAGE)
    return None if rank > n else sorted(misses)[rank - 1].quantize(_CENT)


def _amount(value: str | None) -> Decimal | None:
    # Snapshots kept before the expected amounts were added have none.
    return None if value is None else Decimal(value)


def report(db, tenant_id: str, data_mode: DataMode) -> ForecastCheckResponse:
    empty = [
        ForecastCheckHorizon(horizon_days=d, compared=0, within_range=0, mean_abs_error_myr=None)
        for d in TARGET_DAYS
    ]
    if data_mode != DataMode.LIVE:
        return ForecastCheckResponse(
            data_mode=data_mode,
            status="not_measured",
            reason="synthetic_company",
            forecasts_kept=0,
            compared=0,
            within_range=0,
            first_comparison_on=None,
            by_horizon=empty,
        )
    snapshots = _snapshots(db, tenant_id)
    covered_until = db.scalar(
        select(func.max(BankTransaction.posted_on)).where(
            BankTransaction.tenant_id == tenant_id, BankTransaction.balance.is_not(None)
        )
    )
    errors: dict[int, list[Decimal]] = {d: [] for d in TARGET_DAYS}
    accuracy: dict[int, list[Decimal]] = {d: [] for d in TARGET_DAYS}
    inside: dict[int, int] = {d: 0 for d in TARGET_DAYS}
    differences: list[ForecastDifference] = []
    pending: list[dt.date] = []
    for snapshot in snapshots:
        for target in snapshot.event_payload["targets"]:
            day = dt.date.fromisoformat(target["date"])
            actual = (
                _balance_at_end_of(db, tenant_id, day)
                if covered_until is not None and covered_until >= day
                else None
            )
            if actual is None:
                pending.append(day)
                continue
            days = target["horizon_days"]
            likely = Decimal(target["likely"])
            errors.setdefault(days, []).append(abs(actual - likely))
            if actual != 0:
                score = max(Decimal(0), 1 - abs(actual - likely) / abs(actual))
                accuracy.setdefault(days, []).append(score)
            low, high = sorted((Decimal(target["worst"]), Decimal(target["best"])))
            inside[days] = inside.get(days, 0) + int(low <= actual <= high)
            differences.append(
                ForecastDifference(
                    date=day,
                    horizon_days=days,
                    likely_myr=likely,
                    actual_myr=actual,
                    difference_myr=(actual - likely).quantize(_CENT),
                    within_range=low <= actual <= high,
                    expected_in_myr=_amount(target.get("expected_in")),
                    expected_out_myr=_amount(target.get("expected_out")),
                )
            )
    by_horizon = [
        ForecastCheckHorizon(
            horizon_days=days,
            compared=len(errors[days]),
            within_range=inside[days],
            mean_abs_error_myr=(
                (sum(errors[days]) / len(errors[days])).quantize(_CENT) if errors[days] else None
            ),
            accuracy_pct=(
                (100 * sum(accuracy[days]) / len(accuracy[days])).quantize(Decimal("0.1"))
                if accuracy.get(days)
                else None
            ),
            calibrated_80_myr=_conformal(errors[days]),
            calibration_needs=max(0, MIN_CALIBRATION - len(errors[days])),
        )
        for days in TARGET_DAYS
    ]
    compared = sum(h.compared for h in by_horizon)
    reason = None
    if compared == 0:
        reason = "no_forecasts_kept" if not snapshots else "awaiting_bank_statement"
    return ForecastCheckResponse(
        data_mode=data_mode,
        status="measured" if compared else "not_measured",
        reason=reason,
        forecasts_kept=len(snapshots),
        compared=compared,
        within_range=sum(h.within_range for h in by_horizon),
        first_comparison_on=min(pending) if pending else None,
        by_horizon=by_horizon,
        largest_differences=sorted(
            differences, key=lambda d: (abs(d.difference_myr), d.date), reverse=True
        )[:LARGEST_SHOWN],
    )
