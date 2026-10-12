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

BoardStage = Literal["later", "due_soon", "overdue", "on_hold", "reminder", "paid"]
HoldKind = Literal["disputed", "promised", "paused"]


class HoldRequest(BaseModel):
    """Disputed or promised: one invoice. Paused: every invoice of one customer."""

    kind: HoldKind
    until: dt.date | None = None


class HoldInfo(BaseModel):
    kind: HoldKind
    until: dt.date | None = None
    # "customer:7" when the hold comes from the customer, else the invoice's own ref.
    target: str


class Hold(HoldInfo):
    # The invoice's label, or the customer's (masked) name for a paused customer.
    label: str
    customer_label: str
    set_at: dt.datetime
    set_by_role: str


class HoldsResponse(BaseModel):
    data_mode: DataMode
    holds: list[Hold]


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
    hold: HoldInfo | None = None
    # The day a promise to pay ran out while the invoice was still unpaid.
    promise_broken_on: dt.date | None = None


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
    "invoice_overdue_days",
    "invoice_due_within_days",
    "cash_shortfall_within_days",
    "bill_due_within_days",
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


SkipReason = Literal["on_hold", "waiting_for_decision", "stopped_after_rejection"]


class AutomationRun(BaseModel):
    at: dt.datetime
    proposed: list[str]
    skipped: dict[SkipReason, int]


class AutomationRunsResponse(BaseModel):
    data_mode: DataMode
    runs: list[AutomationRun]


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
    stages: list[BoardStage] = Field(default_factory=list, max_length=6)


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


# ── API keys for MCP ────────────────────────────────────────────────────────


McpTool = Literal[
    "get_cash_forecast",
    "get_forecast_check",
    "get_review_inbox",
    "get_collections_board",
    "get_financing_matches",
]
MCP_TOOLS: tuple[str, ...] = McpTool.__args__


class ApiKeyRequest(BaseModel):
    """Least privilege: only the tools the AI tool needs, for a limited time."""

    tools: list[McpTool] = Field(
        default_factory=lambda: list(MCP_TOOLS), min_length=1, max_length=5
    )
    expires_in_days: Literal[30, 90, 180, 365] = 90

    @field_validator("tools")
    @classmethod
    def _in_order(cls, value: list[str]) -> list[str]:
        return [tool for tool in MCP_TOOLS if tool in value]


class ApiKeyCall(BaseModel):
    tool: str
    at: dt.datetime


class ApiKeyView(BaseModel):
    id: str
    created_at: dt.datetime
    revoked: bool
    tools: list[str]
    expires_at: dt.datetime
    expired: bool
    last_used_at: dt.datetime | None
    recent_calls: list[ApiKeyCall]


class ApiKeysResponse(BaseModel):
    data_mode: DataMode
    keys: list[ApiKeyView]


class ApiKeyCreated(BaseModel):
    data_mode: DataMode
    key: ApiKeyView
    # Shown once; only an HMAC of it is kept.
    secret: str
