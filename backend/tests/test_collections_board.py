"""The collections board: five columns, and a reminder only ever as a proposal."""

import datetime as dt
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.contracts.common import DataMode
from app.db import get_db
from app.models import Base, Customer, SalesPipeline, Tenant
from app.routes.collaboration import router
from app.schemas import UserRole
from app.services import cashflow, collections, review_inbox
from app.services.cashflow_engine import CashBasis
from app.stubs import cashflow as demo
from tests.auth_support import TENANT_A, principal

TODAY = dt.date.today()
LIVE = CashBasis(DataMode.LIVE, demo.OPENING_BALANCE, demo.MINIMUM_BALANCE, ())


def _session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Tenant(id=str(TENANT_A), slug="tenant-a", name="Tenant A"))
    session.commit()
    return session


@pytest.fixture
def live_db(monkeypatch):
    session = _session()
    monkeypatch.setattr(cashflow, "basis_for", lambda *args: LIVE)
    session.add(
        Customer(id=7, tenant_id=str(TENANT_A), canonical_name="Kedai A", normalized_name="kedai a")
    )
    rows = [
        (1, "invoiced", "24500.00", -20),  # overdue
        (2, "invoiced", "18200.00", 5),  # due soon
        (3, "invoiced", "31000.00", 40),  # later
        (4, "paid", "52000.00", -10),  # paid recently
        (5, "paid", "45000.00", -60),  # paid long ago: off the board
    ]
    for n, stage, amount, offset in rows:
        session.add(
            SalesPipeline(
                id=n,
                tenant_id=str(TENANT_A),
                source_record_id=f"t1:INV-{n}",
                record_hash="0" * 64,
                batch_id="b1",
                customer_id=7,
                customer_token="tok",
                stage=stage,
                amount=Decimal(amount),
                expected_payment_date=TODAY + dt.timedelta(days=offset),
                probability=Decimal("1.00"),
            )
        )
    session.commit()
    return session


def _client(db, role=UserRole.FINANCE_OPS) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: principal(role)
    return TestClient(app)


def _columns(client) -> dict[str, list[str]]:
    body = client.get("/collections/board").json()
    return {
        column["stage"]: [card["label"] for card in column["cards"]] for column in body["columns"]
    }


def test_each_receivable_sits_in_one_column(live_db):
    columns = _columns(_client(live_db))

    assert columns == {
        "later": ["INV-3"],
        "due_soon": ["INV-2"],
        "overdue": ["INV-1"],
        "reminder": [],
        "paid": ["INV-4"],
    }


def test_column_totals_and_overdue_days(live_db):
    body = _client(live_db).get("/collections/board").json()
    overdue = next(c for c in body["columns"] if c["stage"] == "overdue")

    assert Decimal(overdue["total"]) == Decimal("24500.00")
    assert overdue["cards"][0]["days_overdue"] == 20
    assert overdue["cards"][0]["customer_label"] == "Kedai A"


def test_moving_a_card_to_reminder_creates_one_proposal_and_sends_nothing(live_db):
    client = _client(live_db)
    first = client.post("/collections/pipeline:1/reminder").json()["action_id"]
    again = client.post("/collections/pipeline:1/reminder").json()["action_id"]

    assert first == again
    assert _columns(client)["reminder"] == ["INV-1"]
    item = review_inbox._replay(live_db, str(TENANT_A))[first].action
    assert (item.status, item.autonomy_level.value) == ("pending", "L2")
    assert "Nothing has been sent" in item.summary


def test_paid_and_unknown_receivables_are_refused(live_db):
    client = _client(live_db)

    assert client.post("/collections/pipeline:4/reminder").status_code == 409
    assert client.post("/collections/pipeline:99/reminder").status_code == 404


def test_compliance_reads_the_board_but_cannot_ask_for_reminders(live_db):
    compliance = _client(live_db, UserRole.COMPLIANCE)

    assert compliance.get("/collections/board").status_code == 200
    assert compliance.post("/collections/pipeline:1/reminder").status_code == 403
    assert _client(live_db, UserRole.GENERAL_EMPLOYEE).get("/collections/board").status_code == 403


def test_the_demo_company_shows_its_sample_receivables():
    session = _session()
    body = collections.board(session, principal(UserRole.OWNER_DIRECTOR), TODAY)

    assert body.data_mode == DataMode.STUB
    labels = [card.label for column in body.columns for card in column.cards]
    assert "INV-1041" in labels and len(labels) == 10


def test_a_ledger_line_with_only_a_hash_is_named_by_its_due_date():
    due = dt.date(2026, 11, 8)

    assert collections.invoice_label("t1:" + "ab" * 32, due) == "Invoice due 08 Nov"
    assert collections.invoice_label("t1:INV-1041", due) == "INV-1041"
