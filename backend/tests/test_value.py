"""The value DuitDuit adds, measured from the company's own records."""

from uuid import UUID

import pytest

from app.contracts.customization import ImportMappingRequest
from app.schemas import UserRole
from app.services import cash_basis, value
from app.services.business_imports import commit_import
from app.services.import_mappings import save
from seed.topic_e import datasets
from tests.auth_support import principal
from tests.test_bank_matching import AS_OF, TENANT, db  # noqa: F401

pytestmark = pytest.mark.skipif(
    not cash_basis._plan3_deployed(), reason="Plan 3 business tables not deployed"
)


def _owner():
    return principal(UserRole.OWNER_DIRECTOR, tenant_id=UUID(TENANT))


def _imported(db):  # noqa: F811
    for schema, (headers, columns, text) in datasets(AS_OF).items():
        mapping = save(
            db,
            _owner(),
            ImportMappingRequest(
                schema_name=schema, name="Synthetic", headers=headers, column_map=columns
            ),
        )
        commit_import(db, _owner(), schema, text, mapping.id)


def test_the_synthetic_company_s_value_is_measured_from_its_records(db, monkeypatch):  # noqa: F811
    from app.services import cashflow

    _imported(db)
    monkeypatch.setattr(
        cashflow, "basis_for", lambda db_, p, day: cash_basis.load(db_, TENANT, day)
    )

    report = value.report(db, _owner(), AS_OF)
    by_key = {m.key: m for m in report.metrics}

    assert by_key["shortfall_warning"].value == "23 days ahead"
    assert by_key["shortfall_warning"].kind == "measured"
    assert "RM29,440.00" in by_key["shortfall_warning"].detail
    assert by_key["gap_closable"].kind == "measured"
    assert by_key["bank_reconciled"].value == "9 of 10"
    assert by_key["unusual_caught"].value.startswith("1 ")
    assert by_key["hours_saved"].kind == "estimate"
    assert report.synthetic is False


def test_nothing_is_claimed_without_records(db):  # noqa: F811
    report = value.report(db, _owner(), AS_OF)
    by_key = {m.key: m for m in report.metrics}
    assert by_key["bank_reconciled"].kind == "not_measured"
    assert by_key["payments_two_people"].value == "0"
