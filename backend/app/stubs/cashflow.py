"""The synthetic demo company's cash signals, for tenants with no imported records.

The arithmetic lives in app.services.cashflow_engine; app.services.cashflow uses
this basis only when a tenant has no imported bank balance. The likely band
breaches the RM50,000 minimum on day 23, the demo story. Signals after day 23 come
from the other positions and never change that story.
"""

import datetime as dt
from dataclasses import replace
from decimal import Decimal

from app.contracts.cashflow import CashSignalsResponse, EventShift, ForecastResponse
from app.contracts.common import DataMode, JobFunction
from app.services import cashflow_engine
from app.services.cashflow_engine import CashBasis, UnknownEventError
from app.services.cashflow_engine import Signal as _Signal

__all__ = ["BASIS", "UnknownEventError", "build_forecast", "list_signals"]

OPENING_BALANCE = Decimal("116400.00")
MINIMUM_BALANCE = Decimal("50000.00")


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


BASIS = CashBasis(
    data_mode=DataMode.STUB,
    opening_balance=OPENING_BALANCE,
    minimum_balance=MINIMUM_BALANCE,
    signals=_SIGNALS,
)


def build_forecast(
    *, horizon_days: int, as_of: dt.date, shifts: list[EventShift] | None = None
) -> ForecastResponse:
    return cashflow_engine.build_forecast(
        BASIS, horizon_days=horizon_days, as_of=as_of, shifts=shifts
    )


def list_signals(*, horizon_days: int, job_function: JobFunction | None) -> CashSignalsResponse:
    return cashflow_engine.list_signals(BASIS, horizon_days=horizon_days, job_function=job_function)
