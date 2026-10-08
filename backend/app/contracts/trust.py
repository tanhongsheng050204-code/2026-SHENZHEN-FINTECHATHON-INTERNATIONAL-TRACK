import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.common import DataMode, OwaspAgenticRisk


class PostureMetric(BaseModel):
    key: str
    label: str
    value: str
    status: Literal["good", "attention", "risk"]
    detail: str


class GuardrailEvent(BaseModel):
    id: str
    occurred_at: dt.datetime
    agent_id: str | None
    owasp_code: OwaspAgenticRisk
    title: str
    detail: str
    outcome: Literal["blocked", "quarantined", "escalated"]


class PostureResponse(BaseModel):
    data_mode: DataMode
    score: int = Field(ge=0, le=100)
    metrics: list[PostureMetric]
    recent_events: list[GuardrailEvent]


class GuardrailEventsResponse(BaseModel):
    data_mode: DataMode
    events: list[GuardrailEvent]
