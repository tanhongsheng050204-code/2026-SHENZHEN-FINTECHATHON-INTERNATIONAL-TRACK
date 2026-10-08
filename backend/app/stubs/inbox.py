"""Stub review inbox for the demo company: one or more items for every built position.

Workstream B2 replaces it with persisted agent_actions and agent_action_reviews.
A person's inbox is every item whose reviewer job function they hold; the owner
oversees every position. Decisions are echoed back, not stored.
"""

import datetime as dt
from decimal import Decimal

from app.contracts.agents import ReviewAction, ReviewDecisionRequest
from app.contracts.common import AutonomyLevel, EvidenceRef, JobFunction
from app.schemas import UserRole
from app.stubs import team

_CREATED_AT = dt.datetime(2026, 10, 8, 9, 0, tzinfo=dt.UTC)


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
) -> ReviewAction:
    return ReviewAction(
        id=action_id,
        agent_id=agent_id,
        title=title,
        summary=summary,
        autonomy_level=level,
        reviewer_job_function=reviewer,
        status="pending",
        amount=Decimal(amount) if amount is not None else None,
        draft=draft,
        evidence=[EvidenceRef(label=label, source=source) for label, source in evidence],
        created_at=_CREATED_AT,
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
        "HR prepares, the owner checks; the bank transfer happens outside FinBrain.",
        "62000.00",
        [("Payroll register", "payroll:2026-10")],
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


def scope_for(role: UserRole, user_id: str) -> list[JobFunction]:
    if role == UserRole.OWNER_DIRECTOR:
        return list(JobFunction)
    return team.job_functions_for(user_id)


def review_inbox(
    role: UserRole, user_id: str, job_function: JobFunction | None
) -> tuple[list[JobFunction], list[ReviewAction]]:
    scope = scope_for(role, user_id)
    if job_function is not None:
        if job_function not in scope:
            raise InboxError("not_your_job_function", 403)
        scope = [job_function]
    return scope, [action for action in _INBOX if action.reviewer_job_function in scope]


def pending_count(job_function: JobFunction) -> int:
    return sum(
        1
        for action in _INBOX
        if action.reviewer_job_function == job_function and action.status == "pending"
    )


def decide(
    action_id: str, request: ReviewDecisionRequest, role: UserRole, user_id: str
) -> ReviewAction:
    action = next((a for a in _INBOX if a.id == action_id), None)
    if action is None:
        raise InboxError("action_not_found", 404)
    if action.autonomy_level == AutonomyLevel.L3:
        raise InboxError("maker_checker_required", 409)
    if action.autonomy_level == AutonomyLevel.L2 and role != UserRole.OWNER_DIRECTOR:
        raise InboxError("owner_approval_required", 403)
    if action.reviewer_job_function not in scope_for(role, user_id):
        raise InboxError("not_your_job_function", 403)
    if request.decision == "edit":
        return action.model_copy(update={"status": "edited", "draft": request.edited_draft})
    status = "approved" if request.decision == "approve" else "rejected"
    return action.model_copy(update={"status": status})
