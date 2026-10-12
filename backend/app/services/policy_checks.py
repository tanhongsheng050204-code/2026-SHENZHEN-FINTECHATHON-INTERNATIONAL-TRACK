"""The checker agent: each review item is checked against company policy.

A second, deterministic agent reads a proposal before a person decides on it and
reports what it found. It cannot approve, reject or change anything; it adds
information. Checks:

- evidence: the proposal cites at least one record;
- owner_escalation: an amount at or above the company's owner escalation amount
  (Company settings, approvals) should reach the owner or need two approvals;
- two_person_rule: a payment (payables, payroll or purchasing with an amount)
  needs two people, which is level L3;
- holds: a reminder must not go to an invoice that is disputed, promised or whose
  customer is paused;
- anomalies: the cited bill or payment is not flagged as unusual.

Each check passes, warns or fails, with one sentence of detail.
"""

import datetime as dt
from decimal import Decimal

from app.auth.principal import AuthPrincipal
from app.contracts.common import AutonomyLevel, JobFunction
from app.contracts.insights import PolicyCheck
from app.models import TenantSettingsRecord
from app.services import anomalies, receivable_holds, review_inbox

DEFAULT_ESCALATION = Decimal("20000.00")  # settings_catalog default
_PAYMENT_AGENTS = ("payables", "hr_payroll", "purchasing")
_HOLD_TEXT = {"disputed": "disputed", "promised": "under a promise to pay", "paused": "paused"}


class CheckError(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _escalation(db, tenant_id: str) -> Decimal:
    record = db.get(TenantSettingsRecord, tenant_id)
    try:
        return Decimal(str(record.document["approvals"]["owner_escalation_amount"]))
    except (AttributeError, KeyError, TypeError):
        return DEFAULT_ESCALATION


def _money(amount: Decimal) -> str:
    return f"RM{amount:,.2f}"


def check(db, principal: AuthPrincipal, action_id: str) -> list[PolicyCheck]:
    tenant_id = str(principal.tenant_id)
    _, visible = review_inbox.inbox(db, principal, None)
    action = next((a for a in visible if a.id == action_id), None)
    if action is None:
        raise CheckError("action_not_found", 404)
    sources = [e.source for e in action.evidence]
    found: list[PolicyCheck] = []

    found.append(
        PolicyCheck(name="evidence", status="pass", detail=f"Cites {len(sources)} record(s).")
        if sources
        else PolicyCheck(
            name="evidence",
            status="warn",
            detail="Cites no record: ask where the figures come from.",
        )
    )

    limit = _escalation(db, tenant_id)
    large = action.amount is not None and action.amount >= limit
    if (
        large
        and action.reviewer_job_function != JobFunction.OWNER
        and (action.autonomy_level != AutonomyLevel.L3)
    ):
        found.append(
            PolicyCheck(
                name="owner_escalation",
                status="warn",
                detail=f"{_money(action.amount)} is at or above the owner escalation amount "
                f"({_money(limit)}); the owner should see it.",
            )
        )
    else:
        found.append(
            PolicyCheck(
                name="owner_escalation",
                status="pass",
                detail=f"Below the owner escalation amount ({_money(limit)}), or the owner "
                "decides it.",
            )
        )

    payment = action.agent_id in _PAYMENT_AGENTS and action.amount is not None
    if payment and action.autonomy_level != AutonomyLevel.L3:
        found.append(
            PolicyCheck(
                name="two_person_rule",
                status="fail",
                detail="A payment needs two people (L3), and this item has one approval step.",
            )
        )
    else:
        found.append(
            PolicyCheck(
                name="two_person_rule",
                status="pass",
                detail="Two approvals are required." if payment else "Not a payment.",
            )
        )

    holds = receivable_holds.stored(db, tenant_id)
    held = None
    if action.agent_id == "receivables":
        today = dt.date.today()
        # Invoice refs and the customer ref both: a paused customer holds every invoice.
        held = next(
            (holds[s] for s in sources if s in holds and receivable_holds.active(holds[s], today)),
            None,
        )
    found.append(
        PolicyCheck(
            name="holds",
            status="fail",
            detail=f"The invoice is {_HOLD_TEXT[held.kind]}: do not send a reminder.",
        )
        if held is not None
        else PolicyCheck(name="holds", status="pass", detail="No hold on what it cites.")
    )

    flagged = {f.ref: f for f in anomalies.scan(db, tenant_id).findings}
    hit = next((flagged[s] for s in sources if s in flagged), None)
    found.append(
        PolicyCheck(name="anomalies", status="warn", detail=f"Flagged as unusual: {hit.reason}")
        if hit is not None
        else PolicyCheck(name="anomalies", status="pass", detail="Nothing it cites looks unusual.")
    )
    return found
