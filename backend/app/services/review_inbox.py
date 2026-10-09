"""The persisted review inbox: agent proposals and the people's decisions on them.

A proposal is an "agent_proposal_created" event on the tenant's workflow hash chain,
and every decision a "review_decision" event, so an item's status, its approvals
and the agent's review record are all replayed from the chain and audited by
construction. No table, no migration.

Deciding follows the autonomy ladder, as in the contract: L1 by a holder of the
reviewer position or the owner; L2 by the owner; L3 by a maker who holds the
position, then a different person, the owner, and never edited. Compliance reads
every item and decides none.

An agent's record (proposals, approved unedited, approved after an edit, rejected)
is counted from the same events, and promotion is recommended once the sample and
the unedited-approval rate reach the tenant's thresholds.
"""

import datetime as dt
import secrets
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select, text

from app.auth.principal import AuthPrincipal
from app.contracts.agents import (
    AgentMetrics,
    ReviewAction,
    ReviewApproval,
    ReviewDecisionRequest,
)
from app.contracts.common import AutonomyLevel, EvidenceRef, JobFunction
from app.models import WorkflowAuditEntry
from app.schemas import UserRole
from app.services import job_scope
from app.services.workflow_audit import write_workflow_event

PROMOTION_MIN_SAMPLE = 30
PROMOTION_MIN_UNEDITED_RATE = 0.9


class InboxError(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass
class _Item:
    action: ReviewAction
    edited: bool = False


def _events(db, tenant_id: str):
    return db.scalars(
        select(WorkflowAuditEntry)
        .where(
            WorkflowAuditEntry.tenant_id == tenant_id,
            WorkflowAuditEntry.resource_type == "agent_action",
        )
        .order_by(WorkflowAuditEntry.id)
    ).all()


def _replayable(action: ReviewAction, decision: str, approver_id: str) -> bool:
    """The ladder's invariants, enforced again on the recorded order of decisions."""
    if action.status in ("approved", "rejected"):
        return False
    if action.autonomy_level == AutonomyLevel.L3:
        if decision == "edit":
            return False
        if decision == "approve" and any(a.approver_id == approver_id for a in action.approvals):
            return False
    return True


def _replay(db, tenant_id: str) -> dict[str, _Item]:
    items: dict[str, _Item] = {}
    for row in _events(db, tenant_id):
        payload = row.event_payload
        if row.event_type == "agent_proposal_created":
            items[row.resource_id] = _Item(ReviewAction.model_validate(payload["action"]))
            continue
        item = items.get(row.resource_id)
        if item is None or row.event_type != "review_decision":
            continue
        action = item.action
        decision = payload["decision"]
        if not _replayable(action, decision, payload["approver_id"]):
            # A decision that lost a race (or was written around the checks) never
            # changes the item: the chain keeps it, the state ignores it.
            continue
        if decision == "edit":
            item.edited = True
            item.action = action.model_copy(
                update={"status": "edited", "draft": payload["edited_draft"]}
            )
        elif decision == "reject":
            item.action = action.model_copy(update={"status": "rejected"})
        else:
            approvals = [
                *action.approvals,
                ReviewApproval(
                    approver_id=payload["approver_id"],
                    approved_at=dt.datetime.fromisoformat(payload["at"]),
                ),
            ]
            if action.autonomy_level == AutonomyLevel.L3 and action.status == "pending":
                status = "awaiting_second_approval"
            else:
                status = "approved"
            item.action = action.model_copy(update={"status": status, "approvals": approvals})
    return items


def propose(
    db,
    tenant_id: str,
    *,
    agent_id: str,
    reviewer: JobFunction,
    title: str,
    summary: str,
    amount: Decimal | None = None,
    evidence: list[EvidenceRef] | None = None,
    draft: str | None = None,
    level: AutonomyLevel = AutonomyLevel.L1,
) -> str:
    """Record a proposal unless the same one is already open; return its id."""
    for item_id, item in _replay(db, tenant_id).items():
        action = item.action
        if (
            action.agent_id == agent_id
            and action.title == title
            and action.status in ("pending", "awaiting_second_approval", "edited")
        ):
            return item_id
    action = ReviewAction(
        id="act_" + secrets.token_hex(6),
        agent_id=agent_id,
        title=title,
        summary=summary,
        autonomy_level=level,
        reviewer_job_function=reviewer,
        status="pending",
        amount=amount,
        draft=draft,
        evidence=evidence or [],
        created_at=dt.datetime.now(dt.UTC).replace(microsecond=0),
    )
    write_workflow_event(
        db,
        event_type="agent_proposal_created",
        actor_role="agent",
        actor_ref=f"agent:{tenant_id}:{agent_id}",
        resource_type="agent_action",
        resource_id=action.id,
        event_payload={"action": action.model_dump(mode="json")},
        tenant_id=tenant_id,
    )
    db.commit()
    return action.id


def _refusal(action: ReviewAction, decision: str, principal: AuthPrincipal) -> InboxError | None:
    """Why this person may not take this decision now, or None if they may."""
    user_id = str(principal.user_id)
    is_owner = principal.role == UserRole.OWNER_DIRECTOR
    holds = action.reviewer_job_function in job_scope.held(principal)
    if principal.role == UserRole.COMPLIANCE:
        return InboxError("read_only_role", 403)
    if action.status in ("approved", "rejected"):
        return InboxError("already_decided", 409)
    if action.autonomy_level == AutonomyLevel.L3:
        if decision == "edit":
            return InboxError("edit_not_allowed_at_l3", 409)
        if decision == "reject":
            return None if is_owner or holds else InboxError("not_your_job_function", 403)
        if any(approval.approver_id == user_id for approval in action.approvals):
            return InboxError("same_person_cannot_approve_twice", 409)
        if action.status == "pending":
            return None if holds else InboxError("maker_approval_required", 409)
        return None if is_owner else InboxError("owner_approval_required", 403)
    if action.autonomy_level == AutonomyLevel.L2 and not is_owner:
        return InboxError("owner_approval_required", 403)
    if not (is_owner or holds):
        return InboxError("not_your_job_function", 403)
    return None


def inbox(
    db, principal: AuthPrincipal, job_function: JobFunction | None
) -> tuple[list[JobFunction], list[ReviewAction]]:
    readable = job_scope.readable(principal)
    if job_function is not None:
        if job_function not in readable:
            raise InboxError("not_your_job_function", 403)
        readable = [job_function]
    actions = [
        item.action.model_copy(
            update={"can_decide": _refusal(item.action, "approve", principal) is None}
        )
        for item in _replay(db, str(principal.tenant_id)).values()
        if item.action.reviewer_job_function in readable
    ]
    return job_scope.scope(principal), actions


def _lock(db, tenant_id: str) -> None:
    """Serialise check-then-write with the chain's own lock (PostgreSQL), so two
    decisions on one item cannot both pass the checks before either is written."""
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(
            text("select pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"finbrain:workflow-audit:{tenant_id}"},
        )


def decide(
    db, principal: AuthPrincipal, action_id: str, request: ReviewDecisionRequest
) -> ReviewAction:
    tenant_id = str(principal.tenant_id)
    _lock(db, tenant_id)
    item = _replay(db, tenant_id).get(action_id)
    if item is None:
        raise InboxError("action_not_found", 404)
    refusal = _refusal(item.action, request.decision, principal)
    if refusal is not None:
        raise refusal
    write_workflow_event(
        db,
        event_type="review_decision",
        actor_role=principal.role.value,
        actor_ref=str(principal.user_id),
        resource_type="agent_action",
        resource_id=action_id,
        event_payload={
            "decision": request.decision,
            "approver_id": str(principal.user_id),
            "at": dt.datetime.now(dt.UTC).isoformat(),
            "edited_draft": request.edited_draft,
            "reason": request.reason,
        },
        tenant_id=tenant_id,
    )
    db.commit()
    return _replay(db, tenant_id)[action_id].action


def pending_count(db, tenant_id: str, job_function: JobFunction) -> int:
    return sum(
        1
        for item in _replay(db, tenant_id).values()
        if item.action.reviewer_job_function == job_function
        and item.action.status in ("pending", "awaiting_second_approval", "edited")
    )


def metrics(db, tenant_id: str) -> dict[str, AgentMetrics]:
    """Each agent's review record, from the decisions people made on its proposals."""
    counts: dict[str, list[int]] = {}
    for item in _replay(db, tenant_id).values():
        tally = counts.setdefault(item.action.agent_id, [0, 0, 0, 0])
        tally[0] += 1
        if item.action.status == "approved":
            tally[2 if item.edited else 1] += 1
        elif item.action.status == "rejected":
            tally[3] += 1
    result = {}
    for agent_id, (proposals, unedited, edited, rejected) in counts.items():
        decided = unedited + edited + rejected
        rate = round(unedited / decided, 2) if decided else None
        result[agent_id] = AgentMetrics(
            proposals=proposals,
            approved_unedited=unedited,
            approved_edited=edited,
            rejected=rejected,
            unedited_approval_rate=rate,
            promotion_recommended=decided >= PROMOTION_MIN_SAMPLE
            and (rate or 0) >= PROMOTION_MIN_UNEDITED_RATE,
        )
    return result
