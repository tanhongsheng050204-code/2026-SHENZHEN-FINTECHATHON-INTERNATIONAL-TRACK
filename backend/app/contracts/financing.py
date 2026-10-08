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
