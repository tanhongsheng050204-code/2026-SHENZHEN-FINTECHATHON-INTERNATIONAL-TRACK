from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.contracts.agents import AgentCard
from app.contracts.common import DataMode, EvidenceRef, JobFunction


class PositionSummary(BaseModel):
    job_function: JobFunction
    display_name: str
    enabled: bool
    build_status: Literal["built", "designed"]
    agent_ids: list[str]


class PositionsResponse(BaseModel):
    data_mode: DataMode
    positions: list[PositionSummary]


class SkillResult(BaseModel):
    skill_id: str
    title: str
    value: str | None
    summary: str
    status: Literal["ok", "attention", "risk", "planned"]
    evidence: list[EvidenceRef]


class CashContribution(BaseModel):
    role: str
    inflow_total: Decimal
    outflow_total: Decimal
    at_risk_total: Decimal
    signal_ids: list[str]


class PositionWorkspace(BaseModel):
    data_mode: DataMode
    job_function: JobFunction
    display_name: str
    build_status: Literal["built", "designed"]
    agents: list[AgentCard]
    skill_results: list[SkillResult]
    cash_contribution: CashContribution
    inbox_count: int
