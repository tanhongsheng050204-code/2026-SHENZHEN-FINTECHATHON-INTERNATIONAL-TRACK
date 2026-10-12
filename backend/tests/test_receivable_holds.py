"""Disputes, promises to pay and paused customers stop chasing, never hide the debt."""

import datetime as dt

from sqlalchemy import select

from app.models import SalesPipeline, WorkflowAuditEntry
from app.schemas import UserRole
from app.services import collections
from tests.auth_support import TENANT_A, principal
from tests.test_collections_board import TODAY, _client, _columns, live_db  # noqa: F401


def _board(client) -> dict[str, list[dict]]:
    body = client.get("/collections/board").json()
    return {column["stage"]: column["cards"] for column in body["columns"]}


def test_a_disputed_invoice_moves_on_hold_and_keeps_its_age(live_db):  # noqa: F811
    finance = _client(live_db)
    response = finance.put("/collections/holds/pipeline:1", json={"kind": "disputed"})
    assert response.status_code == 200

    board = _board(finance)
    [card] = board["on_hold"]
    assert card["label"] == "INV-1" and card["days_overdue"] == 20
    assert card["hold"]["kind"] == "disputed"
    assert board["overdue"] == []
    # No reminder while it is disputed.
    refused = finance.post("/collections/pipeline:1/reminder")
    assert (refused.status_code, refused.json()["detail"]) == (409, "receivable_on_hold")


def test_a_kept_promise_holds_and_a_broken_one_comes_back(live_db):  # noqa: F811
    finance = _client(live_db)
    until = (TODAY + dt.timedelta(days=5)).isoformat()
    finance.put("/collections/holds/pipeline:1", json={"kind": "promised", "until": until})
    assert [c["label"] for c in _board(finance)["on_hold"]] == ["INV-1"]

    # Ten days later the promise date has passed and INV-1 is still unpaid.
    later = collections.board(live_db, principal(UserRole.FINANCE_OPS), TODAY + dt.timedelta(10))
    overdue = next(c for c in later.columns if c.stage == "overdue")
    card = next(c for c in overdue.cards if c.label == "INV-1")
    assert card.hold is None and card.promise_broken_on == TODAY + dt.timedelta(days=5)


def test_pausing_a_customer_holds_every_unpaid_invoice(live_db):  # noqa: F811
    finance = _client(live_db)
    assert finance.put("/collections/holds/customer:7", json={"kind": "paused"}).status_code == 200

    columns = _columns(finance)
    assert sorted(columns["on_hold"]) == ["INV-1", "INV-2", "INV-3"]
    assert columns["paid"] == ["INV-4"]
    [paused] = finance.get("/collections/holds").json()["holds"]
    assert (paused["target"], paused["kind"], paused["label"]) == (
        "customer:7",
        "paused",
        "Kedai A",
    )


def test_clearing_a_hold_puts_the_invoice_back(live_db):  # noqa: F811
    finance = _client(live_db)
    finance.put("/collections/holds/pipeline:1", json={"kind": "disputed"})

    assert finance.delete("/collections/holds/pipeline:1").status_code == 204
    assert _columns(finance)["overdue"] == ["INV-1"]
    assert finance.delete("/collections/holds/pipeline:1").status_code == 404


def test_holds_are_checked_before_they_are_kept(live_db):  # noqa: F811
    finance = _client(live_db)
    past = (TODAY - dt.timedelta(days=1)).isoformat()
    far = (TODAY + dt.timedelta(days=200)).isoformat()

    assert (
        finance.put("/collections/holds/pipeline:1", json={"kind": "promised"}).status_code == 422
    )
    for until in (past, far):
        response = finance.put(
            "/collections/holds/pipeline:1", json={"kind": "promised", "until": until}
        )
        assert response.status_code == 422
    # A customer is paused, an invoice is disputed or promised; not the other way round.
    assert finance.put("/collections/holds/pipeline:1", json={"kind": "paused"}).status_code == 422
    assert (
        finance.put("/collections/holds/customer:7", json={"kind": "disputed"}).status_code == 422
    )
    assert (
        finance.put("/collections/holds/pipeline:99", json={"kind": "disputed"}).status_code == 404
    )
    assert (
        finance.put("/collections/holds/pipeline:4", json={"kind": "disputed"}).status_code == 409
    )


def test_only_money_roles_that_work_receivables_set_holds(live_db):  # noqa: F811
    compliance = _client(live_db, UserRole.COMPLIANCE)

    assert (
        compliance.put("/collections/holds/pipeline:1", json={"kind": "disputed"}).status_code
        == 403
    )
    assert compliance.get("/collections/holds").status_code == 200


def test_holds_are_kept_on_the_chain_with_kinds_and_ids(live_db):  # noqa: F811
    until = (TODAY + dt.timedelta(days=3)).isoformat()
    _client(live_db).put("/collections/holds/pipeline:1", json={"kind": "promised", "until": until})

    event = live_db.scalar(
        select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "receivable_hold_set")
    )
    assert event.resource_id == "pipeline:1"
    assert event.event_payload == {"kind": "promised", "until": until}
    assert str(event.tenant_id) == str(TENANT_A)


def test_a_paid_invoice_leaves_the_hold_column(live_db):  # noqa: F811
    finance = _client(live_db)
    finance.put("/collections/holds/pipeline:1", json={"kind": "disputed"})
    row = live_db.get(SalesPipeline, 1)
    row.stage, row.expected_payment_date = "paid", TODAY - dt.timedelta(days=1)
    live_db.commit()

    columns = _columns(finance)
    assert columns["on_hold"] == [] and "INV-1" in columns["paid"]
