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


class BriefingLine(BaseModel):
    kind: Literal["inbox", "cash", "sharing", "guardrails", "data"]
    text: str
    screen: str | None = None
    tone: Literal["ok", "attention", "risk"] = "ok"


class Briefing(BaseModel):
    """What needs this person today, built from their own records and role."""

    greeting: str
    lines: list[BriefingLine]


class BriefingPreferenceRequest(BaseModel):
    email: bool
    telegram_chat_id: str | None = Field(default=None, pattern=r"^\d{5,15}$")


class BriefingPreference(BaseModel):
    email: bool
    telegram: bool


class BriefingSendResult(BaseModel):
    sent: list[Literal["email", "telegram"]]
