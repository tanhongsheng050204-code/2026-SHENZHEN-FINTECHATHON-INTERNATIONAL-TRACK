"""Deterministic cash-flow engine: forecast bands, scenarios, alerts and agent totals.

Pure functions over a CashBasis (opening balance, minimum balance and the cash
signals every position contributes). Where the basis comes from is not this
module's concern: app.services.cashflow loads a tenant's imported records, and
app.stubs.cashflow supplies the synthetic demo company.

Bands: each signal carries the day it lands in the best, likely and worst case.
A day of None keeps the signal out of that band, which is how uncertain pipeline
is treated (see app.services.cash_basis). Risk signals annotate another signal and
never move cash themselves.
"""

import datetime as dt
from dataclasses import dataclass, replace
from decimal import Decimal

from app.contracts.cashflow import (
    AgentCashTotal,
    CashSignal,
    CashSignalsResponse,
    EventShift,
    ForecastAlert,
    ForecastPoint,
    ForecastResponse,
    Shortfall,
)
from app.contracts.common import DataMode, JobFunction

ZERO = Decimal("0.00")


class UnknownEventError(LookupError):
    def __init__(self, event_id: str) -> None:
        super().__init__(event_id)
        self.event_id = event_id


@dataclass(frozen=True)
class Signal:
    id: str
    agent: str
    job_function: JobFunction
    kind: str
    label: str
    amount: Decimal
    best_day: int
    likely_day: int | None
    worst_day: int | None
    probability: float = 1.0
    source_currency: str = "MYR"
    source_amount: Decimal | None = None
    fx_rate: Decimal | None = None
    affects: str | None = None

    def day_for(self, band: str) -> int | None:
        return {"best": self.best_day, "likely": self.likely_day, "worst": self.worst_day}[band]

    def shifted(self, days: int) -> "Signal":
        def move(day: int | None) -> int | None:
            return None if day is None else max(0, day + days)

        return replace(
            self,
            best_day=move(self.best_day),
            likely_day=move(self.likely_day),
            worst_day=move(self.worst_day),
        )


@dataclass(frozen=True)
class CashBasis:
    data_mode: DataMode
    opening_balance: Decimal
    minimum_balance: Decimal
    signals: tuple[Signal, ...]


def _shifted(signals: tuple[Signal, ...], shifts: list[EventShift]) -> tuple[Signal, ...]:
    known = {signal.id for signal in signals}
    total: dict[str, int] = {}
    for shift in shifts:
        if shift.event_id not in known:
            raise UnknownEventError(shift.event_id)
        total[shift.event_id] = total.get(shift.event_id, 0) + shift.shift_days
    return tuple(
        signal.shifted(total[signal.id]) if signal.id in total else signal for signal in signals
    )


def _balances(basis: CashBasis, signals, horizon_days: int, band: str) -> list[Decimal]:
    deltas = [ZERO] * (horizon_days + 1)
    for signal in signals:
        day = signal.day_for(band)
        if signal.kind == "risk" or day is None or day > horizon_days:
            continue
        deltas[day] += signal.amount if signal.kind == "inflow" else -signal.amount
    balances: list[Decimal] = []
    running = basis.opening_balance
    for delta in deltas:
        running += delta
        balances.append(running)
    return balances


def _first_shortfall(basis: CashBasis, likely: list[Decimal], as_of: dt.date) -> Shortfall | None:
    for day, balance in enumerate(likely):
        if balance < basis.minimum_balance:
            return Shortfall(
                day=day,
                date=as_of + dt.timedelta(days=day),
                likely_balance=balance,
                minimum_balance=basis.minimum_balance,
                gap=basis.minimum_balance - balance,
            )
    return None


def _alerts(
    basis: CashBasis,
    signals: tuple[Signal, ...],
    shortfall: Shortfall | None,
    worst: list[Decimal],
    as_of: dt.date,
) -> list[ForecastAlert]:
    alerts: list[ForecastAlert] = []
    if shortfall is not None:
        due = [s for s in signals if s.kind == "outflow" and s.likely_day == shortfall.day]
        causes = " and ".join(f"{s.label} (RM{s.amount:,.2f})" for s in due)
        alerts.append(
            ForecastAlert(
                id=f"shortfall-day-{shortfall.day}",
                severity="critical",
                title=f"Projected shortfall in {shortfall.day} days",
                detail=(
                    f"Likely balance RM{shortfall.likely_balance:,.2f} is "
                    f"RM{shortfall.gap:,.2f} below your RM{basis.minimum_balance:,.2f} minimum."
                    + (f" Due that day: {causes}." if causes else "")
                ),
                day=shortfall.day,
                date=shortfall.date,
            )
        )
    negative_day = next((day for day, balance in enumerate(worst) if balance < 0), None)
    if negative_day is not None:
        alerts.append(
            ForecastAlert(
                id=f"worst-negative-day-{negative_day}",
                severity="warning",
                title=f"Worst case goes negative on day {negative_day}",
                detail="If customers pay as late as their slowest history, the account overdraws.",
                day=negative_day,
                date=as_of + dt.timedelta(days=negative_day),
            )
        )
    return alerts


def _contract(signal: Signal) -> CashSignal:
    return CashSignal(
        id=signal.id,
        source_agent=signal.agent,
        job_function=signal.job_function,
        kind=signal.kind,
        label=signal.label,
        amount_myr=signal.amount,
        source_currency=signal.source_currency,
        source_amount=signal.source_amount,
        fx_rate=signal.fx_rate,
        best_day=signal.best_day,
        likely_day=signal.likely_day,
        worst_day=signal.worst_day,
        probability=signal.probability,
        affects=signal.affects,
    )


def _in_horizon(signals, horizon_days: int) -> list[Signal]:
    return sorted(
        (s for s in signals if s.best_day <= horizon_days), key=lambda s: (s.best_day, s.id)
    )


def build_forecast(
    basis: CashBasis,
    *,
    horizon_days: int,
    as_of: dt.date,
    shifts: list[EventShift] | None = None,
) -> ForecastResponse:
    signals = _shifted(basis.signals, shifts or [])
    best = _balances(basis, signals, horizon_days, "best")
    likely = _balances(basis, signals, horizon_days, "likely")
    worst = _balances(basis, signals, horizon_days, "worst")
    shortfall = _first_shortfall(basis, likely, as_of)
    return ForecastResponse(
        data_mode=basis.data_mode,
        as_of=as_of,
        horizon_days=horizon_days,
        opening_balance=basis.opening_balance,
        minimum_balance=basis.minimum_balance,
        points=[
            ForecastPoint(
                day=day,
                date=as_of + dt.timedelta(days=day),
                best=best[day],
                likely=likely[day],
                worst=worst[day],
            )
            for day in range(horizon_days + 1)
        ],
        shortfall=shortfall,
        alerts=_alerts(basis, signals, shortfall, worst, as_of),
        drivers=[_contract(signal) for signal in _in_horizon(signals, horizon_days)],
    )


def _totals(signals: list[Signal]) -> list[AgentCashTotal]:
    order = list(JobFunction)
    groups: dict[tuple[int, str], list[Signal]] = {}
    for signal in signals:
        key = (order.index(signal.job_function), signal.agent)
        groups.setdefault(key, []).append(signal)
    totals: list[AgentCashTotal] = []
    for (_, agent), group in sorted(groups.items()):
        amounts = {
            kind: sum((s.amount for s in group if s.kind == kind), ZERO)
            for kind in ("inflow", "outflow", "risk")
        }
        totals.append(
            AgentCashTotal(
                agent_id=agent,
                job_function=group[0].job_function,
                inflow_total=amounts["inflow"],
                outflow_total=amounts["outflow"],
                at_risk_total=amounts["risk"],
                signal_count=len(group),
            )
        )
    return totals


def list_signals(
    basis: CashBasis, *, horizon_days: int, job_function: JobFunction | None
) -> CashSignalsResponse:
    selected = [
        signal
        for signal in _in_horizon(basis.signals, horizon_days)
        if job_function is None or signal.job_function == job_function
    ]
    return CashSignalsResponse(
        data_mode=basis.data_mode,
        horizon_days=horizon_days,
        signals=[_contract(signal) for signal in selected],
        by_agent=_totals(selected),
    )
