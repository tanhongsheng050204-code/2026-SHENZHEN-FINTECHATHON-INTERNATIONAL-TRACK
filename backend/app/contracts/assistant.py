from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.common import AutonomyLevel

AssistantKind = Literal["navigate", "run_goal", "decide", "briefing", "answer", "refuse"]


class AssistantCommand(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class AssistantItem(BaseModel):
    """A review-inbox item the person asked DuitDuit to decide."""

    id: str
    title: str
    agent_id: str
    autonomy_level: AutonomyLevel
    amount: Decimal | None


class AssistantPlan(BaseModel):
    """What DuitDuit understood and will do. It never acts: the person confirms."""

    kind: AssistantKind
    message: str
    screen: str | None = None
    goal: str | None = None
    decision: Literal["approve", "reject"] | None = None
    items: list[AssistantItem] = Field(default_factory=list)
    needs_confirmation: bool = False
    needs_step_up: bool = False
    understood_by: Literal["rules", "model"] = "rules"
