import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.contracts.common import AutonomyLevel, DataMode, EvidenceRef, JobFunction


class AgentSkill(BaseModel):
    id: str
    name: str
    wave: Literal["W1", "W2"]
    availability: Literal["available", "planned"]
    side_effect: Literal["read", "draft", "external", "money"]


class ScopedAutonomy(BaseModel):
    action: str
    level: AutonomyLevel
    max_amount: Decimal | None = None


class AgentMetrics(BaseModel):
    proposals: int
    approved_unedited: int
    approved_edited: int
    rejected: int
    unedited_approval_rate: float | None
    promotion_recommended: bool


class AgentCard(BaseModel):
    id: str
    name: str
    purpose: str
    job_function: JobFunction | None
    reviewer_job_function: JobFunction | None
    build_status: Literal["built", "designed"]
    autonomy_level: AutonomyLevel
    scoped_autonomy: list[ScopedAutonomy]
    skills: list[AgentSkill]
    kill_switch_engaged: bool
    metrics: AgentMetrics | None


class AgentListResponse(BaseModel):
    data_mode: DataMode
    global_kill_switch_engaged: bool
    agents: list[AgentCard]


class AgentCardResponse(BaseModel):
    data_mode: DataMode
    agent: AgentCard


class AgentRunRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=500)


class AgentRunCreated(BaseModel):
    data_mode: DataMode
    run_id: str
    events_url: str


class AgentRunEvent(BaseModel):
    run_id: str
    sequence: int
    type: Literal[
        "run_started",
        "tool_called",
        "proposal_created",
        "waiting_for_review",
        "run_completed",
    ]
    agent_id: str
    message: str
    action_id: str | None = None


class AutonomyChangeRequest(BaseModel):
    action: str = Field(min_length=1, max_length=64, pattern=r"^[a-z_]+$")
    level: AutonomyLevel
    max_amount: Decimal | None = Field(default=None, gt=0)


class KillSwitchRequest(BaseModel):
    agent_id: str | None = Field(default=None, max_length=64, description="None means every agent")
    engaged: bool


class ReviewAction(BaseModel):
    id: str
    agent_id: str
    title: str
    summary: str
    autonomy_level: AutonomyLevel
    reviewer_job_function: JobFunction
    status: Literal["pending", "approved", "edited", "rejected"]
    amount: Decimal | None
    draft: str | None
    evidence: list[EvidenceRef]
    created_at: dt.datetime


class ReviewInboxResponse(BaseModel):
    data_mode: DataMode
    job_functions: list[JobFunction]
    actions: list[ReviewAction]


class ReviewDecisionRequest(BaseModel):
    decision: Literal["approve", "edit", "reject"]
    edited_draft: str | None = Field(default=None, min_length=1, max_length=5000)
    reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _edit_needs_draft(self) -> "ReviewDecisionRequest":
        if self.decision == "edit" and self.edited_draft is None:
            raise ValueError("edited_draft_required")
        return self


class ReviewDecisionResponse(BaseModel):
    data_mode: DataMode
    action: ReviewAction


class JourneyAgent(BaseModel):
    agent_id: str
    name: str
    autonomy_level: AutonomyLevel
    build_status: Literal["built", "designed"]
    override_rate: float | None
    estimated_hours_saved: float


class JourneyFunction(BaseModel):
    job_function: JobFunction
    agents: list[JourneyAgent]


class JourneyResponse(BaseModel):
    data_mode: DataMode
    estimate_note: str
    functions: list[JourneyFunction]
