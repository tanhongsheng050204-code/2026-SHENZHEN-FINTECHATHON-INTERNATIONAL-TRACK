"""General employees never receive exact customer email addresses or phone numbers."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Base, Tenant, TokenVaultEntry
from app.security.detect import Span
from app.security.detokenize import detokenize_response_with_trace, hash_query
from app.security.protection import protect_text
from app.security.tokenize import persist_vault_entries

TENANT = "00000000-0000-0000-0000-000000000001"


def _protected(text: str, kind: str) -> tuple[Session, str]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(Tenant(id=TENANT, name="Test", slug="test"))
    db.commit()
    token, entries = protect_text(
        text,
        f"contact-{kind.split()[0]}",
        TENANT,
        db,
        spans=[Span(0, len(text), text, kind, "test")],
    )
    persist_vault_entries(db, entries)
    db.commit()
    return db, token


def _read(db, token, role):
    return detokenize_response_with_trace(
        db, token, role, hash_query("contact"), tenant_id=TENANT, allow_exact=True
    )


@pytest.mark.parametrize(
    ("text", "kind"), [("buyer@example.com", "email"), ("012-345 6789", "phone number")]
)
def test_general_employee_sees_contact_details_masked(text, kind):
    db, token = _protected(text, kind)

    employee = _read(db, token, "general_employee")
    finance = _read(db, token, "finance_ops")

    assert text not in employee.text and employee.withheld_tokens == 1
    assert finance.text == text


def test_vault_rows_written_under_the_old_policy_are_masked_too():
    db, token = _protected("buyer@example.com", "email")
    # Rows written before the policy changed still list general_employee.
    for entry in db.scalars(select(TokenVaultEntry)):
        entry.allowed_roles = [*entry.allowed_roles, "general_employee"]
    db.commit()

    assert "buyer@example.com" not in _read(db, token, "general_employee").text
