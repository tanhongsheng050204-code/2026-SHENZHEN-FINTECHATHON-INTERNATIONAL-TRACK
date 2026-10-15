"""Bank reconciliation for one month: each line with the record it matches.

Matching is bank_matching's: same direction, the amount to the cent, dates at most
three days apart. Nothing is matched on a guess. An unmatched line can be sent to
Finance as an L1 review item to explain; that records a question, never a change
to the books.
"""

import datetime as dt

from app.auth.principal import AuthPrincipal
from app.contracts.common import AutonomyLevel, DataMode, EvidenceRef, JobFunction
from app.contracts.reconciliation import ReconciliationLine, ReconciliationResponse
from app.services import bank_matching, review_inbox
from app.services.workflow_audit import write_workflow_event

_OPEN = ("pending", "awaiting_second_approval", "edited")


class ReconciliationError(ValueError):
    def __init__(self, code: str, status_code: int = 422) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _month(period: str | None, as_of: dt.date) -> tuple[dt.date, dt.date]:
    if period is None:
        return bank_matching.last_month(as_of)
    try:
        start = dt.date.fromisoformat(f"{period}-01")
    except ValueError as error:
        raise ReconciliationError("invalid_period") from error
    end = (start + dt.timedelta(days=32)).replace(day=1)
    return start, end


def _open_items(db, tenant_id: str) -> dict[str, str]:
    """Bank line ref -> the open review item that asks about it."""
    found: dict[str, str] = {}
    for item_id, item in review_inbox._replay(db, tenant_id).items():
        if item.action.status in _OPEN:
            for evidence in item.action.evidence:
                if evidence.source.startswith("bank:"):
                    found[evidence.source] = item_id
    return found


def statement(
    db, principal: AuthPrincipal, period: str | None, as_of: dt.date
) -> ReconciliationResponse:
    tenant_id = str(principal.tenant_id)
    start, end = _month(period, as_of)
    lines = bank_matching.lines_between(db, tenant_id, start, end)
    asked = _open_items(db, tenant_id)
    items = [
        ReconciliationLine(
            ref=f"bank:{line.id}",
            posted_on=line.posted_on,
            direction=line.direction,
            amount=line.amount,
            description=line.description_token,
            status="matched" if line.matched_to else "unmatched",
            matched_to=line.matched_to,
            review_action_id=asked.get(f"bank:{line.id}"),
        )
        for line in lines
    ]
    return ReconciliationResponse(
        data_mode=DataMode.LIVE,
        period=start.strftime("%Y-%m"),
        label=start.strftime("%B %Y"),
        lines=len(items),
        matched=sum(1 for item in items if item.status == "matched"),
        window_days=bank_matching.WINDOW_DAYS,
        items=items,
    )


def _find(db, principal: AuthPrincipal, ref: str, as_of: dt.date) -> ReconciliationLine:
    tenant_id = str(principal.tenant_id)
    try:
        line_id = int(ref.removeprefix("bank:"))
    except ValueError as error:
        raise ReconciliationError("line_not_found", 404) from error
    from app.models import BankTransaction

    row = db.get(BankTransaction, line_id)
    if row is None or str(row.tenant_id) != tenant_id or not ref.startswith("bank:"):
        raise ReconciliationError("line_not_found", 404)
    sheet = statement(db, principal, row.posted_on.strftime("%Y-%m"), as_of)
    return next(item for item in sheet.items if item.ref == ref)


def explain(db, principal: AuthPrincipal, ref: str, as_of: dt.date) -> str:
    """Ask Finance to explain one unmatched line; the same open item is reused."""
    line = _find(db, principal, ref, as_of)
    if line.status == "matched":
        raise ReconciliationError("line_already_matched", 409)
    if line.review_action_id:
        return line.review_action_id
    tenant_id = str(principal.tenant_id)
    way = "in" if line.direction == "credit" else "out"
    action_id = review_inbox.propose(
        db,
        tenant_id,
        agent_id="payables",
        reviewer=JobFunction.FINANCE,
        level=AutonomyLevel.L1,
        title=f"Explain a bank line: RM{line.amount:,.2f} {way} on {line.posted_on:%d %b}",
        summary=(
            f"No record matches this bank line (same amount within "
            f"{bank_matching.WINDOW_DAYS} days). Find the bill, sale or payout behind it and "
            "import it, or note why there is none. Nothing has been changed."
        ),
        amount=line.amount,
        evidence=[EvidenceRef(label="Bank line", source=ref)],
    )
    write_workflow_event(
        db,
        event_type="bank_line_sent_for_review",
        actor_role=principal.role.value,
        actor_ref=principal.actor_ref,
        resource_type="bank_line",
        resource_id=ref,
        event_payload={"ref": ref, "action_id": action_id},
        tenant_id=tenant_id,
    )
    db.commit()
    return action_id
