"""Comments and @mentions on review items.

A comment's words go through the same protection as every other record: personal
details are tokenized into the vault before anything is stored, and text that reads
like an instruction to an AI is quarantined and refused. The protected text is kept
as a protected record (source_system "duitduit", record_type "review_comment"); the
workflow chain gets a "review_comment_added" event with ids and kinds only: the
item, the record id, the author's role and the positions mentioned.

Comments are shown with tokens replaced by placeholders such as ‹name›, and authors
by role, never by name. Anyone who can see an item can comment on it; a mention is
a notification to a position, never an approval.
"""

import datetime as dt
import re
import secrets

from sqlalchemy import select

from app.auth.principal import AuthPrincipal
from app.contracts.collaboration import Mention, ReviewComment
from app.contracts.common import JobFunction
from app.models import TokenizedContent, WorkflowAuditEntry
from app.schemas import CanonicalIngestionRecord, ProcessingStatus
from app.security.guardrails import content_risk
from app.services import job_scope
from app.services.workflow_audit import chain_scalars, write_workflow_event

EVENT = "review_comment_added"
MENTION_WINDOW = dt.timedelta(days=14)
_TOKEN = re.compile(r"AMOUNT_BAND_\d+_[0-9a-f]{10}|([A-Z]+)_[0-9a-f]{10}")
_PLACEHOLDERS = {
    "PERSON": "‹name›",
    "EMAIL": "‹email›",
    "PHONE": "‹phone›",
    "BANKACC": "‹bank account›",
    "CARD": "‹card›",
    "NRIC": "‹ID number›",
    "ADDR": "‹address›",
    "ORG": "‹company›",
}


class CommentError(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _shown(protected: str) -> str:
    def placeholder(match: re.Match) -> str:
        if match.group(0).startswith("AMOUNT_BAND_"):
            return "‹amount›"
        return _PLACEHOLDERS.get(match.group(1), "‹hidden›")

    return _TOKEN.sub(placeholder, protected)


def _visible_ids(db, principal: AuthPrincipal) -> set[str]:
    from app.services import live_agents

    _, actions = live_agents.inbox_for(db, principal, None)
    return {action.id for action in actions}


def _events(db, tenant_id: str, action_id: str | None = None):
    query = select(WorkflowAuditEntry).where(
        WorkflowAuditEntry.tenant_id == tenant_id, WorkflowAuditEntry.event_type == EVENT
    )
    if action_id is not None:
        query = query.where(WorkflowAuditEntry.resource_id == action_id)
    return chain_scalars(db, query.order_by(WorkflowAuditEntry.id))


def _comment(row: WorkflowAuditEntry, principal: AuthPrincipal, text: str) -> ReviewComment:
    payload = row.event_payload
    return ReviewComment(
        id=payload["comment_id"],
        action_id=row.resource_id,
        author_role=row.actor_role,
        by_me=row.actor_ref == str(principal.user_id),
        mentions=[JobFunction(job) for job in payload.get("mentions", [])],
        text=text,
        created_at=row.created_at,
    )


def add(db, principal: AuthPrincipal, action_id: str, text: str, mentions) -> ReviewComment:
    from app.services.ingestion import protect_canonical_record

    if action_id not in _visible_ids(db, principal):
        raise CommentError("action_not_found", 404)
    tenant_id = str(principal.tenant_id)
    comment_id = "cmt_" + secrets.token_hex(6)
    record_id = f"comment.{comment_id}"
    result = protect_canonical_record(
        db,
        CanonicalIngestionRecord(
            source_record_id=record_id,
            source_system="duitduit",
            record_type="review_comment",
            text=text,
            occurred_at=dt.datetime.now(dt.UTC),
            tenant_id=tenant_id,
        ),
    )
    # A comment that tries to instruct the AI is refused. One that discusses a bank
    # change is kept for people but quarantined from models, like any such record.
    if (
        result.processing_status == ProcessingStatus.QUARANTINED
        and content_risk(text) == "prompt_injection"
    ):
        raise CommentError("comment_quarantined", 422)
    row = write_workflow_event(
        db,
        event_type=EVENT,
        actor_role=principal.role.value,
        actor_ref=str(principal.user_id),
        resource_type="agent_action",
        resource_id=action_id,
        event_payload={
            "comment_id": comment_id,
            "record_id": record_id,
            "mentions": sorted({JobFunction(job).value for job in mentions}),
        },
        tenant_id=tenant_id,
    )
    db.commit()
    stored = db.scalar(
        select(TokenizedContent.content_text).where(TokenizedContent.source_record_id == record_id)
    )
    return _comment(row, principal, _shown(stored or ""))


def comments(db, principal: AuthPrincipal, action_id: str) -> list[ReviewComment]:
    if action_id not in _visible_ids(db, principal):
        raise CommentError("action_not_found", 404)
    rows = _events(db, str(principal.tenant_id), action_id)
    records = {
        row.source_record_id: row.content_text
        for row in db.scalars(
            select(TokenizedContent).where(
                TokenizedContent.tenant_id == str(principal.tenant_id),
                TokenizedContent.source_record_id.in_(
                    [row.event_payload["record_id"] for row in rows]
                ),
            )
        )
    }
    return [
        _comment(row, principal, _shown(records.get(row.event_payload["record_id"], "")))
        for row in rows
    ]


def mentions_for(db, principal: AuthPrincipal, now: dt.datetime | None = None) -> list[Mention]:
    """Recent comments that mention a position this person holds, newest first."""
    held = {job.value for job in job_scope.scope(principal)}
    since = (now or dt.datetime.now(dt.UTC)) - MENTION_WINDOW
    visible = _visible_ids(db, principal)
    found = []
    for row in reversed(_events(db, str(principal.tenant_id))):
        created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=dt.UTC)
        if created < since:
            break
        mentioned = set(row.event_payload.get("mentions", []))
        if (
            mentioned & held
            and row.actor_ref != str(principal.user_id)
            and row.resource_id in visible
        ):
            found.append(
                Mention(
                    comment_id=row.event_payload["comment_id"],
                    action_id=row.resource_id,
                    author_role=row.actor_role,
                    mentions=[JobFunction(job) for job in sorted(mentioned)],
                    created_at=created,
                )
            )
    return found
