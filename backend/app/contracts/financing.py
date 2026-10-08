import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.agents import ReviewAction
from app.contracts.common import DataMode, EvidenceRef

Jurisdiction = Literal["MY", "CN"]


class RuleResult(BaseModel):
    rule: str
    passed: bool
    detail: str
    evidence: list[EvidenceRef]


class FinancingProduct(BaseModel):
    id: str
    jurisdiction: Jurisdiction
    category: str
    name: str
    illustrative_terms: str
    last_verified: dt.date | None
    source_url: str | None


class FinancingMatch(BaseModel):
    product: FinancingProduct
    eligible: bool
    fit_score: int = Field(ge=0, le=100)
    rules: list[RuleResult]
    explanation: str


class FinancingMatchesResponse(BaseModel):
    data_mode: DataMode
    jurisdiction: Jurisdiction
    disclaimer: str
    shortfall_gap: Decimal | None
    matches: list[FinancingMatch]


class ApplicationPackRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=64)


class ApplicationPackResponse(BaseModel):
    data_mode: DataMode
    action: ReviewAction


class ScoreFactor(BaseModel):
    key: str
    label: str
    value: str = Field(description="The input as a person reads it, e.g. '72%'")
    points: int
    max_points: int
    reason: str = Field(description="Which band the input falls in and why it earns these points")
    evidence: list[EvidenceRef]


class PublicSignal(BaseModel):
    source: Literal["google_maps", "shopee", "grabfood", "lazada"]
    metric: str
    value: str
    trend: str
    status: Literal["ok", "watch", "risk"]
    synthetic: bool = Field(
        description="True for demo data; real signals come only from official APIs or owner exports"
    )


class ScorecardResponse(BaseModel):
    data_mode: DataMode
    method: Literal["expert_weights", "calibrated"] = Field(
        description="expert_weights: published bins set by hand; calibrated: fitted on outcome data"
    )
    method_note: str
    score: int
    min_score: int
    max_score: int
    grade: Literal["A", "B", "C", "D", "E"]
    base_points: int
    factors: list[ScoreFactor]
    public_signals: list[PublicSignal]
    public_data_note: str
    disclaimer: str
