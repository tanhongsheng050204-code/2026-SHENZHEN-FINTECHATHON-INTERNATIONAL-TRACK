"""Saved alert rules are checked against the company's own records and fire once a day."""

import json
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import models
from app.contracts.customization import AlertRuleRequest, ImportMappingRequest
from app.schemas import UserRole
from app.services import alerts, briefing, cash_basis, customization
from app.services.business_imports import commit_import
from app.services.import_mappings import save
from seed.topic_e import datasets
from tests.auth_support import principal

pytestmark = pytest.mark.skipif(
    not cash_basis._plan3_deployed(), reason="Plan 3 business tables not deployed"
)
TENANT = "00000000-0000-0000-0000-0000000000a1"
AS_OF = date(2026, 10, 9)


def _person(role, jobs):
    import dataclasses

    person = principal(role, tenant_id=UUID(TENANT))
    return dataclasses.replace(person, job_functions=jobs)


OWNER = _person(UserRole.OWNER_DIRECTOR, ("owner",))


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.add(models.Tenant(id=TENANT, slug="synthetic-alerts", name="SYNTHETIC alerts"))
        session.commit()
        for schema, (headers, columns, text) in datasets(AS_OF).items():
            mapping = save(
                session,
                OWNER,
                ImportMappingRequest(
                    schema_name=schema, name="Synthetic", headers=headers, column_map=columns
                ),
            )
            commit_import(session, OWNER, schema, text, mapping.id)
        yield session
    engine.dispose()


def _rule(db, metric, operator, threshold, recipients=("owner",), channel="in_app"):
    return customization.create_rule(
        db,
        OWNER,
        AlertRuleRequest(
            metric=metric,
            operator=operator,
            threshold=Decimal(threshold),
            recipients=list(recipients),
            channel=channel,
        ),
    )


def test_low_projected_balance_fires_once_a_day(db):
    _rule(db, "projected_balance", "below", "50000", ("owner", "finance"))

    first = alerts.evaluate(db, TENANT, AS_OF)
    again = alerts.evaluate(db, TENANT, AS_OF)
    next_day = alerts.evaluate(db, TENANT, AS_OF + timedelta(days=1))

    assert [(a.metric, a.value) for a in first] == [("projected_balance", Decimal("20560.00"))]
    assert again == []
    assert len(next_day) == 1


def test_stock_below_reorder_counts_items(db):
    _rule(db, "stock_below_reorder", "above", "0", ("procurement", "owner"))

    fired = alerts.evaluate(db, TENANT, AS_OF)

    assert [(a.metric, a.value) for a in fired] == [("stock_below_reorder", Decimal("3"))]


def test_overdue_per_customer_fires_per_customer_once_invoices_are_late(db):
    _rule(db, "overdue_amount_per_customer", "above", "20000", ("finance", "owner"))

    assert alerts.evaluate(db, TENANT, AS_OF) == []
    late = alerts.evaluate(db, TENANT, AS_OF + timedelta(days=15))

    assert [a.value for a in late] == [Decimal("24500.00")]
    assert late[0].subject.startswith("customer:")


def test_metrics_without_a_source_never_fire(db):
    _rule(db, "open_disputes", "above", "0")

    assert alerts.evaluate(db, TENANT, AS_OF) == []
    readings = {r.metric: r for r in alerts.readings(db, TENANT, AS_OF)}
    assert readings["open_disputes"].value is None
    # Completed July to September campaigns: RM69,500 attributed on RM16,500 spent.
    assert readings["marketing_return_per_ringgit"].value == Decimal("4.21")


def test_alert_events_hold_ids_and_values_never_names(db):
    _rule(db, "overdue_amount_per_customer", "above", "20000", ("finance", "owner"))
    alerts.evaluate(db, TENANT, AS_OF + timedelta(days=15))

    events = db.scalars(
        select(models.WorkflowAuditEntry).where(
            models.WorkflowAuditEntry.event_type == "alert_fired"
        )
    ).all()
    text = json.dumps([e.event_payload for e in events])

    assert len(events) == 1
    assert "SYNTHETIC Customer" not in text


def test_briefing_shows_fired_alerts_only_to_their_recipients(db):
    _rule(db, "stock_below_reorder", "above", "0", ("procurement", "owner"))
    alerts.evaluate(db, TENANT, date.today())
    sales = _person(UserRole.GENERAL_EMPLOYEE, ("sales",))

    owner_lines = [line for line in briefing.build(db, OWNER).lines if line.kind == "alerts"]
    sales_lines = [line for line in briefing.build(db, sales).lines if line.kind == "alerts"]

    assert owner_lines and "3 items below their reorder level" in owner_lines[0].text
    assert sales_lines == []


def test_email_alerts_go_to_opted_in_recipients_with_ranges_only(db, monkeypatch):
    from app.services import briefing_push

    sent = []
    monkeypatch.setattr(briefing_push, "_send_email", lambda to, s, body: sent.append(body))
    db.add(
        models.AuthUserRole(
            user_id=str(OWNER.user_id),
            tenant_id=TENANT,
            user_role="owner_director",
            job_functions=["owner"],
        )
    )
    db.commit()
    briefing_push.set_preference(db, OWNER, email=True, telegram_chat_id=None)
    _rule(db, "projected_balance", "below", "50000", ("owner",), channel="email")

    alerts.evaluate(db, TENANT, AS_OF)

    assert len(sent) == 1
    assert "RM20,560.00" not in sent[0] and "RM10K–25K" in sent[0]


def _client(db, person):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.auth.dependencies import get_current_user
    from app.db import get_db
    from app.routes.alerts import router
    from app.security import rate_limit

    rate_limit.reset()
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: person
    return TestClient(app)


def test_check_now_reports_what_fired_and_is_refused_to_employees(db):
    _rule(db, "stock_below_reorder", "above", "0", ("procurement", "owner"))

    response = _client(db, OWNER).post("/alerts/check")
    refused = _client(db, _person(UserRole.GENERAL_EMPLOYEE, ("sales",))).post("/alerts/check")

    assert response.status_code == 200, response.text
    assert response.json()["fired"] == ["3 items below their reorder level."]
    assert refused.status_code == 403


def test_a_committed_import_checks_the_rules(db, monkeypatch):
    from app.routes import imports

    calls = []
    monkeypatch.setattr(imports, "commit_import", lambda *a, **k: {"ok": True})
    monkeypatch.setattr(imports.alerts, "evaluate", lambda db, tenant, day: calls.append(tenant))

    imports._after_commit(db, OWNER)

    assert calls == [TENANT]
