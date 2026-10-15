"""Reconciliation: each bank line with the record it matches, and unmatched ones to explain."""

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from app.contracts.common import JobFunction
from app.schemas import UserRole
from app.services import reconciliation, review_inbox
from tests.auth_support import principal
from tests.test_bank_matching import AS_OF, TENANT, _bank, _bill, db  # noqa: F401


def _owner():
    return principal(UserRole.OWNER_DIRECTOR, tenant_id=UUID(TENANT))


def _september(db):  # noqa: F811
    db.add_all(
        [
            _bank(1, date(2026, 9, 7), "out", "14800.00"),
            _bank(2, date(2026, 9, 27), "out", "1250.00"),
            _bill(1, date(2026, 9, 6), "14800.00"),
        ]
    )
    db.commit()


def test_each_line_names_the_record_it_matches_and_last_month_is_the_default(db):  # noqa: F811
    _september(db)

    sheet = reconciliation.statement(db, _owner(), None, AS_OF)

    assert (sheet.period, sheet.lines, sheet.matched) == ("2026-09", 2, 1)
    first, second = sheet.items
    assert (first.status, first.matched_to, first.amount) == (
        "matched", "Supplier bill", Decimal("14800.00")
    )
    assert (second.status, second.matched_to, second.direction) == ("unmatched", None, "debit")
    assert second.ref.startswith("bank:")


def test_another_month_can_be_chosen_and_a_bad_month_is_refused(db):  # noqa: F811
    _september(db)
    assert reconciliation.statement(db, _owner(), "2026-08", AS_OF).lines == 0
    with pytest.raises(reconciliation.ReconciliationError, match="invalid_period"):
        reconciliation.statement(db, _owner(), "2026-13", AS_OF)


def test_an_unmatched_line_becomes_one_review_item_for_finance_and_nothing_changes(db):  # noqa: F811
    _september(db)
    ref = reconciliation.statement(db, _owner(), None, AS_OF).items[1].ref

    first = reconciliation.explain(db, _owner(), ref, AS_OF)
    again = reconciliation.explain(db, _owner(), ref, AS_OF)

    assert first == again
    item = review_inbox._replay(db, TENANT)[first].action
    assert item.reviewer_job_function == JobFunction.FINANCE
    assert "RM1,250.00 out on 27 Sep" in item.title
    assert reconciliation.statement(db, _owner(), None, AS_OF).matched == 1


def test_a_matched_line_or_an_unknown_one_cannot_be_sent(db):  # noqa: F811
    _september(db)
    matched = reconciliation.statement(db, _owner(), None, AS_OF).items[0].ref
    with pytest.raises(reconciliation.ReconciliationError, match="line_already_matched"):
        reconciliation.explain(db, _owner(), matched, AS_OF)
    with pytest.raises(reconciliation.ReconciliationError, match="line_not_found"):
        reconciliation.explain(db, _owner(), "bank:999999", AS_OF)


def test_staff_cannot_read_it_and_compliance_cannot_send_lines(db):  # noqa: F811
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.auth.dependencies import get_current_user
    from app.db import get_db
    from app.routes.reconciliation import router

    _september(db)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    for role, method, path, status in [
        (UserRole.GENERAL_EMPLOYEE, "get", "/reconciliation", 403),
        (UserRole.COMPLIANCE, "get", "/reconciliation?period=2026-09", 200),
        (UserRole.COMPLIANCE, "post", "/reconciliation/bank:1/explain", 403),
    ]:
        app.dependency_overrides[get_current_user] = lambda role=role: principal(
            role, tenant_id=UUID(TENANT)
        )
        assert getattr(TestClient(app), method)(path).status_code == status, (role, path)
