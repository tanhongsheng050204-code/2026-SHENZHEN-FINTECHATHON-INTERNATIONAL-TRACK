"""Anomaly findings and privacy-protected industry benchmarks."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.contracts.common import DataMode

AnomalyKind = Literal[
    "unusual_amount", "possible_duplicate", "new_supplier_large", "possible_duplicate_payment"
]


class AnomalyFinding(BaseModel):
    # "payable:12" or "bank:5": the record the finding is about.
    ref: str
    kind: AnomalyKind
    severity: Literal["high", "medium"]
    # The bill number or payment date with a masked supplier or payee name.
    label: str
    amount_myr: Decimal
    # The modified z-score, for unusual amounts.
    score: float | None
    reason: str


class AnomaliesResponse(BaseModel):
    data_mode: DataMode
    findings: list[AnomalyFinding]
    bills_checked: int
    payments_checked: int


class AnomalyReviewResponse(BaseModel):
    data_mode: DataMode
    action_id: str


class PolicyCheck(BaseModel):
    name: Literal["evidence", "owner_escalation", "two_person_rule", "holds", "anomalies"]
    status: Literal["pass", "warn", "fail"]
    detail: str


class PolicyChecksResponse(BaseModel):
    data_mode: DataMode
    action_id: str
    checks: list[PolicyCheck]


class BenchmarkMetric(BaseModel):
    name: Literal["median_days_late"]
    # This company's own value, exact, shown only to itself.
    your_value: float | None
    # The average over every contributing company, with Laplace noise; None below the minimum.
    peer_value: float | None
    # The Laplace scale used: sensitivity / epsilon.
    noise_scale: float | None


class BenchmarksResponse(BaseModel):
    status: Literal["measured", "not_enough_companies"]
    epsilon: float
    min_companies: int
    metrics: list[BenchmarkMetric]
