import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.common import DataMode


class ReconciliationLine(BaseModel):
    ref: str = Field(description="bank:<id>, used to send an unmatched line for review")
    posted_on: dt.date
    direction: Literal["credit", "debit"]
    amount: Decimal
    description: str = Field(description="The bank line's description, protected")
    status: Literal["matched", "unmatched"]
    matched_to: str | None = Field(description="The kind of record it matches, if any")
    review_action_id: str | None = Field(
        default=None, description="An open review item already asks someone to explain it"
    )


class ReconciliationResponse(BaseModel):
    data_mode: DataMode
    period: str
    label: str
    lines: int
    matched: int
    window_days: int
    items: list[ReconciliationLine]


class ExplainResponse(BaseModel):
    data_mode: DataMode
    action_id: str
