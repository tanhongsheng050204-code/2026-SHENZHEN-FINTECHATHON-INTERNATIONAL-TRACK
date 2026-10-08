"""Stub cash-flow engine over the synthetic demo company's cash signals.

Workstream B2 replaces it with app/services/cashflow.py, which reads signals written
by every agent. The arithmetic is the spec's deterministic model, so the frontend
already sees the demo story: the likely band breaches the RM50,000 minimum on day 23.
Signals after day 23 come from the other positions and never change that story.
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

OPENING_BALANCE = Decimal("116400.00")
MINIMUM_BALANCE = Decimal("50000.00")
_ZERO = Decimal("0.00")


class UnknownEventError(LookupError):
    def __init__(self, event_id: str) -> None:
        super().__init__(event_id)
        self.event_id = event_id


@dataclass(frozen=True)
class _Signal:
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

    def shifted(self, days: int) -> "_Signal":
        def move(day: int | None) -> int | None:
            return None if day is None else max(0, day + days)

        return replace(
            self,
            best_day=move(self.best_day),
            likely_day=move(self.likely_day),
            worst_day=move(self.worst_day),
        )


def _receivable(
    signal_id: str, label: str, amount: str, due: int, likely: int, worst: int
) -> _Signal:
    return _Signal(
        signal_id,
        "receivables",
        JobFunction.FINANCE,
        "inflow",
        label,
        Decimal(amount),
        due,
        due + likely,
        due + worst,
    )


def _outflow(
    signal_id: str, agent: str, job: JobFunction, label: str, amount: str, day: int
) -> _Signal:
    return _Signal(signal_id, agent, job, "outflow", label, Decimal(amount), day, day, day)


_SIGNALS: tuple[_Signal, ...] = (
    _receivable("R1", "INV-1041 · Customer A", "24500.00", 4, 7, 21),
    _receivable("R2", "INV-1043 · Customer B", "18200.00", 9, 12, 30),
    _receivable("R3", "INV-1047 · Customer C", "31000.00", 16, 14, 35),
    _receivable("R4", "INV-1052 · Customer A", "42000.00", 28, 10, 28),
    _receivable("R5", "INV-1058 · Customer D", "38500.00", 34, 9, 26),
    _receivable("R6", "INV-1063 · Customer B", "27600.00", 45, 9, 25),
    _receivable("R7", "INV-1066 · Customer E", "44200.00", 50, 11, 27),
    _receivable("R8", "INV-1071 · Customer C", "35400.00", 62, 8, 24),
    _receivable("R9", "INV-1077 · Customer A", "52300.00", 72, 8, 20),
    _receivable("R10", "INV-1082 · Customer F", "39800.00", 80, 7, 22),
    _outflow("P1", "payables", JobFunction.FINANCE, "Rent and utilities", "14800.00", 6),
    _outflow("P2", "hr_payroll", JobFunction.HR, "Payroll", "62000.00", 23),
    replace(
        _outflow(
            "P3",
            "purchasing",
            JobFunction.PROCUREMENT,
            "Shenzhen Supplier 1 · CNY 98,000",
            "61740.00",
            23,
        ),
        source_currency="CNY",
        source_amount=Decimal("98000.00"),
        fx_rate=Decimal("0.63"),
    ),
    _outflow("P4", "payables", JobFunction.FINANCE, "Rent and utilities", "14800.00", 36),
    _outflow("P5", "hr_payroll", JobFunction.HR, "Payroll", "62000.00", 53),
    _outflow("P6", "payables", JobFunction.FINANCE, "Local logistics supplier", "48300.00", 58),
    _outflow("P7", "payables", JobFunction.FINANCE, "Rent and utilities", "14800.00", 66),
    _outflow("P8", "hr_payroll", JobFunction.HR, "Payroll", "62000.00", 83),
    replace(
        _outflow(
            "PO2",
            "purchasing",
            JobFunction.PROCUREMENT,
            "Shenzhen Supplier 2 · CNY 60,000",
            "37800.00",
            75,
        ),
        source_currency="CNY",
        source_amount=Decimal("60000.00"),
        fx_rate=Decimal("0.63"),
    ),
    _Signal(
        "S1",
        "sales",
        JobFunction.SALES,
        "inflow",
        "Order SO-311 · Customer G",
        Decimal("26000.00"),
        52,
        60,
        None,
        probability=0.7,
    ),
    _Signal(
        "MK1",
        "marketing",
        JobFunction.MARKETING,
        "inflow",
        "Shopee payout",
        Decimal("9400.00"),
        26,
        26,
        33,
        probability=0.95,
    ),
    _outflow("MK2", "marketing", JobFunction.MARKETING, "11.11 campaign spend", "5500.00", 40),
    _outflow(
        "IN1", "inventory", JobFunction.LOGISTICS, "Reorder 3 fast-moving SKUs", "12600.00", 47
    ),
    _Signal(
        "CS1",
        "customer_service",
        JobFunction.CUSTOMER_SERVICE,
        "risk",
        "Complaint from Customer C may delay INV-1047",
        Decimal("31000.00"),
        16,
        None,
        None,
        probability=0.4,
        affects="R3",
    ),
)


def _shifted(signals: tuple[_Signal, ...], shifts: list[EventShift]) -> tuple[_Signal, ...]:
    known = {signal.id for signal in signals}
    total: dict[str, int] = {}
    for shift in shifts:
        if shift.event_id not in known:
            raise UnknownEventError(shift.event_id)
        total[shift.event_id] = total.get(shift.event_id, 0) + shift.shift_days
    return tuple(
        signal.shifted(total[signal.id]) if signal.id in total else signal for signal in signals
    )


def _balances(signals: tuple[_Signal, ...], horizon_days: int, band: str) -> list[Decimal]:
    deltas = [_ZERO] * (horizon_days + 1)
    for signal in signals:
        day = signal.day_for(band)
        if signal.kind == "risk" or day is None or day > horizon_days:
            continue
        deltas[day] += signal.amount if signal.kind == "inflow" else -signal.amount
    balances: list[Decimal] = []
    running = OPENING_BALANCE
    for delta in deltas:
        running += delta
        balances.append(running)
    return balances


def _first_shortfall(likely: list[Decimal], as_of: dt.date) -> Shortfall | None:
    for day, balance in enumerate(likely):
        if balance < MINIMUM_BALANCE:
            return Shortfall(
                day=day,
                date=as_of + dt.timedelta(days=day),
                likely_balance=balance,
                minimum_balance=MINIMUM_BALANCE,
                gap=MINIMUM_BALANCE - balance,
            )
    return None


def _alerts(
    signals: tuple[_Signal, ...],
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
                    f"RM{shortfall.gap:,.2f} below your RM{MINIMUM_BALANCE:,.2f} minimum."
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


def _contract(signal: _Signal) -> CashSignal:
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


def _in_horizon(signals: tuple[_Signal, ...], horizon_days: int) -> list[_Signal]:
    return sorted(
        (s for s in signals if s.best_day <= horizon_days), key=lambda s: (s.best_day, s.id)
    )


def build_forecast(
    *, horizon_days: int, as_of: dt.date, shifts: list[EventShift] | None = None
) -> ForecastResponse:
    signals = _shifted(_SIGNALS, shifts or [])
    best = _balances(signals, horizon_days, "best")
    likely = _balances(signals, horizon_days, "likely")
    worst = _balances(signals, horizon_days, "worst")
    shortfall = _first_shortfall(likely, as_of)
    return ForecastResponse(
        data_mode=DataMode.STUB,
        as_of=as_of,
        horizon_days=horizon_days,
        opening_balance=OPENING_BALANCE,
        minimum_balance=MINIMUM_BALANCE,
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
        alerts=_alerts(signals, shortfall, worst, as_of),
        drivers=[_contract(signal) for signal in _in_horizon(signals, horizon_days)],
    )


def _totals(signals: list[_Signal]) -> list[AgentCashTotal]:
    order = list(JobFunction)
    groups: dict[tuple[int, str], list[_Signal]] = {}
    for signal in signals:
        key = (order.index(signal.job_function), signal.agent)
        groups.setdefault(key, []).append(signal)
    totals: list[AgentCashTotal] = []
    for (_, agent), group in sorted(groups.items()):
        amounts = {
            kind: sum((s.amount for s in group if s.kind == kind), _ZERO)
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


def list_signals(*, horizon_days: int, job_function: JobFunction | None) -> CashSignalsResponse:
    selected = [
        signal
        for signal in _in_horizon(_SIGNALS, horizon_days)
        if job_function is None or signal.job_function == job_function
    ]
    return CashSignalsResponse(
        data_mode=DataMode.STUB,
        horizon_days=horizon_days,
        signals=[_contract(signal) for signal in selected],
        by_agent=_totals(selected),
    )
