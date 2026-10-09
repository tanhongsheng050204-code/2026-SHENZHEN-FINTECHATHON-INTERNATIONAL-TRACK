"""Stub review inbox for the demo company: one or more items for every built position.

Workstream B2 replaces it with persisted agent_actions and agent_action_reviews.
A person sees every item whose reviewer job function they hold; the owner and
Compliance oversee every item. Deciding follows the autonomy ladder: L1 by a holder
of the reviewer job function (or the owner), L2 by the owner, L3 by a maker who holds
the job function and then a different checker, the owner. Decisions are echoed back.
"""

import datetime as dt
from decimal import Decimal

from app.contracts.agents import ReviewAction, ReviewApproval, ReviewDecisionRequest
from app.contracts.common import AutonomyLevel, EvidenceRef, JobFunction
from app.schemas import UserRole

_CREATED_AT = dt.datetime(2026, 10, 8, 9, 0, tzinfo=dt.UTC)
_FINANCE_HR_CLERK = "20000000-0000-0000-0000-000000000002"
_OVERSIGHT_ROLES = (UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)


class InboxError(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _action(
    action_id: str,
    agent_id: str,
    reviewer: JobFunction,
    level: AutonomyLevel,
    title: str,
    summary: str,
    amount: str | None,
    evidence: list[tuple[str, str]],
    draft: str | None = None,
    approved_by: str | None = None,
) -> ReviewAction:
    approvals = (
        [ReviewApproval(approver_id=approved_by, approved_at=_CREATED_AT + dt.timedelta(hours=1))]
        if approved_by
        else []
    )
    return ReviewAction(
        id=action_id,
        agent_id=agent_id,
        title=title,
        summary=summary,
        autonomy_level=level,
        reviewer_job_function=reviewer,
        status="awaiting_second_approval" if approvals else "pending",
        amount=Decimal(amount) if amount is not None else None,
        draft=draft,
        evidence=[EvidenceRef(label=label, source=source) for label, source in evidence],
        created_at=_CREATED_AT,
        approvals=approvals,
    )


_INBOX: tuple[ReviewAction, ...] = (
    _action(
        "act_cashflow_alert",
        "cashflow",
        JobFunction.OWNER,
        AutonomyLevel.L1,
        "Shortfall in 23 days",
        "Likely balance RM20,560.00 against a RM50,000.00 minimum on day 23.",
        "29440.00",
        [("90-day forecast", "cashflow:forecast")],
    ),
    _action(
        "act_financing_pack",
        "financing",
        JobFunction.OWNER,
        AutonomyLevel.L1,
        "Application pack: invoice financing",
        "Covers the RM29,440.00 gap with headroom; every eligibility rule passed.",
        "60000.00",
        [("Financing matches", "financing:matches")],
        draft="Request: RM60,000.00 against validated invoices INV-1041, INV-1047, INV-1052.",
    ),
    _action(
        "act_send_reminders",
        "receivables",
        JobFunction.OWNER,
        AutonomyLevel.L2,
        "Send 3 approved reminders by email",
        "External action: the owner approves before anything is sent.",
        "73700.00",
        [("Approved reminder drafts", "review:act_reminders")],
    ),
    _action(
        "act_stale_approvals",
        "operations",
        JobFunction.OPERATIONS,
        AutonomyLevel.L1,
        "Two approvals waiting more than 48 hours",
        "Nudge the reviewers or reassign the items.",
        None,
        [("Review inbox ages", "review:ages")],
    ),
    _action(
        "act_reminders",
        "receivables",
        JobFunction.FINANCE,
        AutonomyLevel.L1,
        "Review 3 reminder drafts",
        "Customers A, B and C, ranked by amount × days overdue × attention score.",
        "73700.00",
        [
            ("INV-1041 · RM24,500.00", "einvoice:INV-1041"),
            ("INV-1043 · RM18,200.00", "einvoice:INV-1043"),
            ("INV-1047 · RM31,000.00", "einvoice:INV-1047"),
        ],
        draft=(
            "Dear Customer A, our records show invoice INV-1041 for RM24,500.00 is now due. "
            "Could you confirm the expected payment date?"
        ),
    ),
    _action(
        "act_bank_change",
        "payables",
        JobFunction.FINANCE,
        AutonomyLevel.L3,
        "Supplier bank-account change (quarantined)",
        (
            "Shenzhen Supplier 1's emailed invoice names a bank account that differs from the "
            "verified one. Needs callback verification and two different approvers."
        ),
        "61740.00",
        [("Supplier email", "email:supplier-bank-change")],
    ),
    _action(
        "act_sales_followup",
        "sales",
        JobFunction.SALES,
        AutonomyLevel.L1,
        "Follow up quote Q-2207 with Customer G",
        "Order SO-311 is 70% likely; a follow-up keeps it on track.",
        "26000.00",
        [("Quote Q-2207", "pipeline:Q-2207")],
        draft="Hi Customer G, just checking whether quote Q-2207 works for your November order.",
    ),
    _action(
        "act_cs_reply",
        "customer_service",
        JobFunction.CUSTOMER_SERVICE,
        AutonomyLevel.L1,
        "Reply to Customer C's complaint",
        "A fast reply lowers the risk that INV-1047 (RM31,000.00) is disputed.",
        None,
        [("Complaint email", "email:customer-c-complaint")],
        draft="Dear Customer C, we are sorry about the damaged cartons and will replace them.",
    ),
    _action(
        "act_campaign",
        "marketing",
        JobFunction.MARKETING,
        AutonomyLevel.L1,
        "Approve the 11.11 campaign budget",
        "The last comparable campaign returned RM3.40 per RM1 spent.",
        "5500.00",
        [("Campaign history", "marketing:campaigns")],
    ),
    _action(
        "act_po_approval",
        "purchasing",
        JobFunction.PROCUREMENT,
        AutonomyLevel.L1,
        "Approve PO-778 · Shenzhen Supplier 2 · CNY 60,000",
        "Within the purchasing limit; payment falls due on day 75.",
        "37800.00",
        [("Supplier comparison", "purchasing:suppliers")],
    ),
    _action(
        "act_reorder",
        "inventory",
        JobFunction.LOGISTICS,
        AutonomyLevel.L1,
        "Reorder 3 fast-moving SKUs",
        "Three SKUs are below their reorder level.",
        "12600.00",
        [("Stock snapshot", "stock:latest")],
    ),
    _action(
        "act_payroll_run",
        "hr_payroll",
        JobFunction.HR,
        AutonomyLevel.L3,
        "Approve the October payroll run",
        "HR prepared and approved it; the owner checks. The transfer happens outside FinBrain.",
        "62000.00",
        [("Payroll register", "payroll:2026-10")],
        approved_by=_FINANCE_HR_CLERK,
    ),
    _action(
        "act_access_review",
        "compliance",
        JobFunction.COMPLIANCE,
        AutonomyLevel.L1,
        "Deactivate 1 account inactive for 45 days",
        "Access review: the marketing executive has not signed in for 45 days.",
        None,
        [("Team activity", "team:activity")],
    ),
)


def scope_for(role: UserRole, user_id: str, job_functions=()) -> list[JobFunction]:
    if role == UserRole.OWNER_DIRECTOR:
        return list(JobFunction)
    return [JobFunction(job) for job in job_functions]


def _readable(role: UserRole, user_id: str, job_functions=()) -> list[JobFunction]:
    if role in _OVERSIGHT_ROLES:
        return list(JobFunction)
    return [JobFunction(job) for job in job_functions]


def _refusal(
    action: ReviewAction, decision: str, role: UserRole, user_id: str, job_functions=()
) -> InboxError | None:
    """Why this person may not take this decision now, or None if they may."""
    is_owner = role == UserRole.OWNER_DIRECTOR
    holds_function = action.reviewer_job_function in job_functions
    if action.autonomy_level == AutonomyLevel.L3:
        if decision == "edit":
            return InboxError("edit_not_allowed_at_l3", 409)
        if decision == "reject":
            return None if is_owner or holds_function else InboxError("not_your_job_function", 403)
        if any(approval.approver_id == user_id for approval in action.approvals):
            return InboxError("same_person_cannot_approve_twice", 409)
        if action.status == "pending":
            return None if holds_function else InboxError("maker_approval_required", 409)
        return None if is_owner else InboxError("owner_approval_required", 403)
    if action.autonomy_level == AutonomyLevel.L2 and not is_owner:
        return InboxError("owner_approval_required", 403)
    if not (is_owner or holds_function):
        return InboxError("not_your_job_function", 403)
    return None


def review_inbox(
    role: UserRole, user_id: str, job_function: JobFunction | None, job_functions=()
) -> tuple[list[JobFunction], list[ReviewAction]]:
    readable = _readable(role, user_id, job_functions)
    if job_function is not None:
        if job_function not in readable:
            raise InboxError("not_your_job_function", 403)
        readable = [job_function]
    actions = [
        action.model_copy(
            update={"can_decide": _refusal(action, "approve", role, user_id, job_functions) is None}
        )
        for action in _INBOX
        if action.reviewer_job_function in readable
    ]
    return scope_for(role, user_id, job_functions), actions


def pending_count(job_function: JobFunction) -> int:
    return sum(
        1
        for action in _INBOX
        if action.reviewer_job_function == job_function and action.status == "pending"
    )


def decide(
    action_id: str, request: ReviewDecisionRequest, role: UserRole, user_id: str, job_functions=()
) -> ReviewAction:
    action = next((a for a in _INBOX if a.id == action_id), None)
    if action is None:
        raise InboxError("action_not_found", 404)
    refusal = _refusal(action, request.decision, role, user_id, job_functions)
    if refusal is not None:
        raise refusal
    if request.decision == "edit":
        return action.model_copy(update={"status": "edited", "draft": request.edited_draft})
    if request.decision == "reject":
        return action.model_copy(update={"status": "rejected"})
    if action.autonomy_level == AutonomyLevel.L3:
        approvals = [
            *action.approvals,
            ReviewApproval(approver_id=user_id, approved_at=dt.datetime.now(dt.UTC)),
        ]
        checked = action.status == "awaiting_second_approval"
        status = "approved" if checked else "awaiting_second_approval"
        return action.model_copy(update={"status": status, "approvals": approvals})
    return action.model_copy(update={"status": "approved"})
