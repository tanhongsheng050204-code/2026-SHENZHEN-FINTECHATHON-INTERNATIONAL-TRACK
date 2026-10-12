"""Unusual bills and payments, found by robust statistics and explained in words.

Checks, each on the company's own records:

- unusual_amount: an open supplier bill whose amount is far from that supplier's
  other bills. Modified z-score with the median and the median absolute deviation
  (Iglewicz and Hoaglin), flagged above 3.5; needs MIN_HISTORY other bills. A
  median absolute deviation of zero falls back to "more than 50% away".
- possible_duplicate: an open bill with the same supplier and amount as another
  bill, with the same bill number (ignoring case and spaces) or due within
  DUPLICATE_DAYS of it. The later one is flagged.
- new_supplier_large: a supplier's only bill is at or above the company's 90th
  percentile bill, once the company has MIN_COMPANY_BILLS other bills.
- possible_duplicate_payment: two equal bank debits to the same payee within
  PAYMENT_DAYS of each other. The later one is flagged.

Nothing is changed or paid. A person can send a finding to the review inbox as an
L1 item for Finance. Statistics, not a trained model: every flag can be checked
by hand from the numbers it names.
"""

import statistics
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select

from app.contracts.common import AutonomyLevel, EvidenceRef, JobFunction
from app.contracts.insights import AnomalyFinding
from app.models import BankTransaction, Payable, ProtectedTokenRegistry, Supplier
from app.services import review_inbox
from app.services.workflow_audit import write_workflow_event

MIN_HISTORY = 5
MIN_COMPANY_BILLS = 10
THRESHOLD = 3.5
DUPLICATE_DAYS = 30
PAYMENT_DAYS = 3
_TITLES = {
    "unusual_amount": "Check an unusual bill: {label}",
    "possible_duplicate": "Check a possible duplicate bill: {label}",
    "new_supplier_large": "Check a large first bill: {label}",
    "possible_duplicate_payment": "Check a possible duplicate payment: {label}",
}


class AnomalyError(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass
class Scan:
    findings: list[AnomalyFinding]
    bills_checked: int
    payments_checked: int


def _money(amount) -> str:
    return f"RM{Decimal(amount):,.2f}"


def _masked(db, token: str | None, fallback: str) -> str:
    registry = db.get(ProtectedTokenRegistry, token) if token else None
    return registry.masked_value if registry else fallback


def _modified_z(value: float, others: list[float]) -> tuple[float, float]:
    median = statistics.median(others)
    mad = statistics.median([abs(x - median) for x in others])
    if mad == 0:
        return (float("inf") if median and abs(value - median) > 0.5 * median else 0.0), median
    return 0.6745 * (value - median) / mad, median


def _bills(db, tenant_id: str) -> list[Payable]:
    return list(
        db.scalars(
            select(Payable)
            .where(Payable.tenant_id == tenant_id)
            .order_by(Payable.due_date, Payable.id)
        )
    )


def scan(db, tenant_id: str) -> Scan:
    bills = _bills(db, tenant_id)
    suppliers = {
        s.id: s for s in db.scalars(select(Supplier).where(Supplier.tenant_id == tenant_id))
    }
    by_supplier: dict[int, list[Payable]] = {}
    for bill in bills:
        by_supplier.setdefault(bill.supplier_id, []).append(bill)
    findings: list[AnomalyFinding] = []

    def supplier_label(bill: Payable) -> str:
        supplier = suppliers.get(bill.supplier_id)
        return _masked(db, supplier.name_token if supplier else None, "Supplier")

    for bill in bills:
        if bill.status != "open":
            continue
        amount = float(bill.amount_myr)
        same = [b for b in by_supplier[bill.supplier_id] if b.id != bill.id]
        label = f"{bill.bill_no.strip()} · {supplier_label(bill)}"
        twin = next(
            (
                b
                for b in same
                if Decimal(b.amount_myr) == Decimal(bill.amount_myr)
                and (b.due_date, b.id) < (bill.due_date, bill.id)
                and (
                    b.bill_no.strip().casefold() == bill.bill_no.strip().casefold()
                    or abs((bill.due_date - b.due_date).days) <= DUPLICATE_DAYS
                )
            ),
            None,
        )
        if twin is not None:
            findings.append(
                AnomalyFinding(
                    ref=f"payable:{bill.id}",
                    kind="possible_duplicate",
                    severity="high",
                    label=label,
                    amount_myr=Decimal(bill.amount_myr),
                    score=None,
                    reason=f"Same supplier and amount ({_money(bill.amount_myr)}) as bill "
                    f"{twin.bill_no.strip()}, due "
                    f"{(bill.due_date - twin.due_date).days} days apart.",
                )
            )
            continue
        if len(same) >= MIN_HISTORY:
            z, median = _modified_z(amount, [float(b.amount_myr) for b in same])
            if abs(z) > THRESHOLD:
                findings.append(
                    AnomalyFinding(
                        ref=f"payable:{bill.id}",
                        kind="unusual_amount",
                        severity="medium",
                        label=label,
                        amount_myr=Decimal(bill.amount_myr),
                        score=round(abs(z), 1) if z != float("inf") else None,
                        reason=f"{_money(bill.amount_myr)} from a supplier usually around "
                        f"{_money(median)} across {len(same)} other bills.",
                    )
                )
            continue
        others = [float(b.amount_myr) for b in bills if b.supplier_id != bill.supplier_id]
        if not same and len(others) >= MIN_COMPANY_BILLS:
            ordered = sorted(others)
            high = ordered[max(0, -(-9 * len(ordered) // 10) - 1)]
            if amount >= high:
                findings.append(
                    AnomalyFinding(
                        ref=f"payable:{bill.id}",
                        kind="new_supplier_large",
                        severity="medium",
                        label=label,
                        amount_myr=Decimal(bill.amount_myr),
                        score=None,
                        reason=f"The first bill from this supplier is {_money(bill.amount_myr)}, "
                        f"at or above 90% of the company's bills ({_money(high)}).",
                    )
                )

    debits = list(
        db.scalars(
            select(BankTransaction)
            .where(BankTransaction.tenant_id == tenant_id, BankTransaction.direction == "debit")
            .order_by(BankTransaction.posted_on, BankTransaction.id)
        )
    )
    for index, line in enumerate(debits):
        if not line.counterparty_token:
            continue
        earlier = next(
            (
                d
                for d in debits[:index]
                if d.counterparty_token == line.counterparty_token
                and Decimal(d.amount) == Decimal(line.amount)
                and 0 <= (line.posted_on - d.posted_on).days <= PAYMENT_DAYS
            ),
            None,
        )
        if earlier is not None:
            payee = _masked(db, line.counterparty_token, "Payee")
            findings.append(
                AnomalyFinding(
                    ref=f"bank:{line.id}",
                    kind="possible_duplicate_payment",
                    severity="high",
                    label=f"Payment on {line.posted_on:%d %b} · {payee}",
                    amount_myr=Decimal(line.amount),
                    score=None,
                    reason=f"Same payee and amount ({_money(line.amount)}) as a payment "
                    f"{(line.posted_on - earlier.posted_on).days} days earlier.",
                )
            )
    order = {"high": 0, "medium": 1}
    findings.sort(key=lambda f: (order[f.severity], -f.amount_myr))
    return Scan(findings=findings, bills_checked=len(bills), payments_checked=len(debits))


def send_for_review(db, principal, ref: str) -> str:
    tenant_id = str(principal.tenant_id)
    finding = next((f for f in scan(db, tenant_id).findings if f.ref == ref), None)
    if finding is None:
        raise AnomalyError("finding_not_found", 404)
    for item_id, item in review_inbox._replay(db, tenant_id).items():
        action = item.action
        if action.status in ("pending", "awaiting_second_approval", "edited") and any(
            e.source == ref for e in action.evidence
        ):
            return item_id
    action_id = review_inbox.propose(
        db,
        tenant_id,
        agent_id="payables",
        reviewer=JobFunction.FINANCE,
        level=AutonomyLevel.L1,
        title=_TITLES[finding.kind].format(label=finding.label),
        summary=f"{finding.reason} Check it against the supplier and the bank before paying. "
        "Nothing has been paid or changed.",
        amount=finding.amount_myr,
        evidence=[EvidenceRef(label="Flagged record", source=ref)],
    )
    write_workflow_event(
        db,
        event_type="anomaly_sent_for_review",
        actor_role=principal.role.value,
        actor_ref=principal.actor_ref,
        resource_type="anomaly",
        resource_id=ref,
        event_payload={"kind": finding.kind, "ref": ref},
        tenant_id=tenant_id,
    )
    db.commit()
    return action_id
