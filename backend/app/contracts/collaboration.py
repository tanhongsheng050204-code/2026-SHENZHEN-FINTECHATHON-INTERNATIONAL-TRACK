"""Comments and @mentions on review items, the collections board, automations,
saved views and chat notifications."""

import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.contracts.common import DataMode, JobFunction

# ── Comments and mentions ───────────────────────────────────────────────────


class CommentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    mentions: list[JobFunction] = Field(default_factory=list, max_length=5)

    @field_validator("text")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("comment_empty")
        return value.strip()


class ReviewComment(BaseModel):
    id: str
    action_id: str
    author_role: str
    by_me: bool
    mentions: list[JobFunction]
    # Personal details are replaced by placeholders such as ‹name› before storage.
    text: str
    created_at: dt.datetime


class CommentsResponse(BaseModel):
    data_mode: DataMode
    comments: list[ReviewComment]


class Mention(BaseModel):
    comment_id: str
    action_id: str
    author_role: str
    mentions: list[JobFunction]
    created_at: dt.datetime


class MentionsResponse(BaseModel):
    data_mode: DataMode
    mentions: list[Mention]


# ── Collections board ───────────────────────────────────────────────────────

BoardStage = Literal["later", "due_soon", "overdue", "reminder", "paid"]


class BoardCard(BaseModel):
    ref: str
    label: str
    customer_id: int | None
    customer_label: str
    amount: Decimal
    due_date: dt.date | None
    days_overdue: int
    stage: BoardStage
    reminder_action_id: str | None = None


class BoardColumn(BaseModel):
    stage: BoardStage
    total: Decimal
    cards: list[BoardCard]


class CollectionsBoardResponse(BaseModel):
    data_mode: DataMode
    as_of: dt.date
    columns: list[BoardColumn]


class ReminderProposalResponse(BaseModel):
    data_mode: DataMode
    action_id: str


# ── Automations ─────────────────────────────────────────────────────────────

AutomationTrigger = Literal[
    "invoice_overdue_days", "cash_shortfall_within_days", "bill_due_within_days"
]
AutomationAction = Literal["draft_reminder", "reminder_sequence", "ask_review"]


class AutomationRequest(BaseModel):
    trigger: AutomationTrigger
    days: int = Field(ge=0, le=120)
    action: AutomationAction
    reviewer: JobFunction = JobFunction.FINANCE
    enabled: bool = True


class Automation(AutomationRequest):
    id: str
    created_at: dt.datetime


class AutomationsResponse(BaseModel):
    data_mode: DataMode
    automations: list[Automation]


class AutomationRunResponse(BaseModel):
    data_mode: DataMode
    proposals: list[str]


# ── Saved views ─────────────────────────────────────────────────────────────

SavedViewScreen = Literal["customers", "collections"]


class SavedViewFilters(BaseModel):
    """Filters only, no free text: a view's name is written from them."""

    priorities: list[Literal["urgent", "high", "monitoring", "healthy"]] = Field(
        default_factory=list, max_length=4
    )
    min_overdue: Decimal | None = Field(default=None, ge=0, le=100_000_000)
    min_outstanding: Decimal | None = Field(default=None, ge=0, le=100_000_000)
    unconfirmed_only: bool = False
    stages: list[BoardStage] = Field(default_factory=list, max_length=5)


class SavedViewRequest(BaseModel):
    screen: SavedViewScreen
    filters: SavedViewFilters
    shared: bool = False


class SavedView(SavedViewRequest):
    id: str
    mine: bool
    created_at: dt.datetime


class SavedViewsResponse(BaseModel):
    data_mode: DataMode
    views: list[SavedView]


# ── Chat notifications ──────────────────────────────────────────────────────

ChatChannel = Literal["slack", "whatsapp"]


class ChatChannelStatus(BaseModel):
    channel: ChatChannel
    configured: bool
    enabled: bool


class ChatNotificationsResponse(BaseModel):
    data_mode: DataMode
    channels: list[ChatChannelStatus]


class ChatTestResponse(BaseModel):
    data_mode: DataMode
    channel: ChatChannel
    status: Literal["sent", "simulated", "not_configured", "failed"]
