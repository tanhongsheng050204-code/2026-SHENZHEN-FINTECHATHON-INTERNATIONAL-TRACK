"""Unusual bills and payments: found by robust statistics, explained, and sent to a person."""

import datetime as dt
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.db import get_db
from app.models import BankTransaction, Base, Payable, Supplier, Tenant, WorkflowAuditEntry
from app.schemas import UserRole
from app.services import anomalies, review_inbox
from tests.auth_support import TENANT_A, principal

TODAY = dt.date(2026, 10, 12)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Tenant(id=str(TENANT_A), slug="tenant-a", name="Tenant A"))
    for n in (1, 2, 3):
        session.add(
            Supplier(
                id=n,
                tenant_id=str(TENANT_A),
                normalized_name=f"supplier {n}",
                name_token=f"tok-{n}",
                currency="MYR",
            )
        )
    session.commit()
    return session


_ids = iter(range(1, 10_000))


def _bill(db, supplier: int, amount: str, days: int, bill_no: str | None = None, status="open"):
    n = next(_ids)
    db.add(
        Payable(
            id=n,
            tenant_id=str(TENANT_A),
            source_record_id=f"p{n}",
            record_hash="0" * 64,
            batch_id="b1",
            supplier_id=supplier,
            bill_no=bill_no or f"BILL-{n}",
            amount=Decimal(amount),
            currency="MYR",
            amount_myr=Decimal(amount),
            due_date=TODAY + dt.timedelta(days=days),
            status=status,
        )
    )
    db.commit()
    return n


def _client(db, role=UserRole.FINANCE_OPS) -> TestClient:
    from app.routes.insights import router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: principal(role)
    return TestClient(app)


def _history(db, supplier=1, amounts=("5000", "5200", "4900", "5100", "5050", "4950")):
    for n, amount in enumerate(amounts):
        _bill(db, supplier, amount, -60 + n * 7, status="paid")


def test_an_ordinary_set_of_bills_raises_nothing(db):
    _history(db)
    _bill(db, 1, "5100", 10)

    found = anomalies.scan(db, str(TENANT_A))
    assert found.findings == [] and found.bills_checked == 7


def test_a_bill_far_outside_a_suppliers_usual_range_is_flagged(db):
    _history(db)
    ref = f"payable:{_bill(db, 1, '48000', 10)}"

    [finding] = anomalies.scan(db, str(TENANT_A)).findings
    assert (finding.ref, finding.kind) == (ref, "unusual_amount")
    assert finding.score > 3.5
    assert "usually around RM5,025.00" in finding.reason


def test_the_same_bill_twice_is_flagged_as_a_possible_duplicate(db):
    _bill(db, 2, "12800", 5, "INV-77")
    second = _bill(db, 2, "12800", 9, "INV-77 ")

    [finding] = anomalies.scan(db, str(TENANT_A)).findings
    assert (finding.ref, finding.kind, finding.severity) == (
        f"payable:{second}",
        "possible_duplicate",
        "high",
    )


def test_a_large_first_bill_from_a_new_supplier_is_flagged(db):
    _history(db)
    _history(db, supplier=2, amounts=("3000", "3100", "2900", "3050"))
    first = _bill(db, 3, "60000", 3)

    kinds = {(f.ref, f.kind) for f in anomalies.scan(db, str(TENANT_A)).findings}
    assert (f"payable:{first}", "new_supplier_large") in kinds


def test_two_equal_payments_to_the_same_payee_days_apart(db):
    for n, day in enumerate((1, 3)):
        db.add(
            BankTransaction(
                id=n + 1,
                tenant_id=str(TENANT_A),
                source_record_id=f"bt{n}",
                record_hash="0" * 64,
                batch_id="b1",
                posted_on=TODAY - dt.timedelta(days=day),
                description_token="tok",
                direction="debit",
                amount=Decimal("8800.00"),
                counterparty_token="payee-tok",
            )
        )
    db.commit()

    [finding] = anomalies.scan(db, str(TENANT_A)).findings
    assert (finding.ref, finding.kind) == ("bank:1", "possible_duplicate_payment")


def test_finance_sends_a_finding_to_the_review_inbox_once(db):
    _history(db)
    ref = f"payable:{_bill(db, 1, '48000', 10)}"
    client = _client(db)

    assert client.get("/insights/anomalies").json()["findings"][0]["ref"] == ref
    first = client.post(f"/insights/anomalies/{ref}/review").json()["action_id"]
    again = client.post(f"/insights/anomalies/{ref}/review").json()["action_id"]
    assert first == again
    action = review_inbox._replay(db, str(TENANT_A))[first].action
    assert (action.autonomy_level.value, action.reviewer_job_function.value) == ("L1", "finance")
    assert "Nothing has been paid or changed" in action.summary
    assert client.post("/insights/anomalies/payable:999/review").status_code == 404


def test_staff_cannot_see_anomalies_and_the_review_is_kinds_only(db):
    _history(db)
    ref = f"payable:{_bill(db, 1, '48000', 10)}"
    assert _client(db, UserRole.GENERAL_EMPLOYEE).get("/insights/anomalies").status_code == 403

    _client(db).post(f"/insights/anomalies/{ref}/review")
    event = db.scalar(
        select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "anomaly_sent_for_review")
    )
    assert event.event_payload == {"kind": "unusual_amount", "ref": ref}
