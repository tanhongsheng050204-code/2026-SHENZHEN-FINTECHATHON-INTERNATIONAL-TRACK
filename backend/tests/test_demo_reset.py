"""The shared demo company starts each day clean, without rewriting its history."""

import datetime as dt

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.contracts.common import AutonomyLevel, JobFunction
from app.models import (
    AgentSecurityControl,
    Base,
    Tenant,
    TenantSettingsRecord,
    TenantSettingsVersion,
    WorkflowAuditEntry,
)
from app.services import demo_reset, live_agents, review_inbox
from app.services.tenant_settings import initialize_settings
from app.services.workflow_audit import write_workflow_event

DEMO = "858f0c1c-42fa-52a2-91b3-80a19d816356"
OWNER = "00000000-0000-0000-0000-000000000003"


@pytest.fixture
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    session.add(Tenant(id=DEMO, slug="synthetic-demo", name="SYNTHETIC Importer"))
    session.add(Tenant(id=OWNER.replace("3", "9"), slug="real", name="Real Co"))
    initialize_settings(session, DEMO, "SYNTHETIC Importer")
    session.commit()
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_tenant_id", DEMO)
    monkeypatch.setattr(settings, "demo_sign_in_enabled", True)
    monkeypatch.setattr(settings, "demo_daily_reset", True)
    return session


def _proposal(db) -> str:
    return review_inbox.propose(
        db,
        DEMO,
        agent_id="receivables",
        reviewer=JobFunction.FINANCE,
        title="Send three payment reminders",
        summary="Three invoices are past due.",
        level=AutonomyLevel.L2,
    )


def _approve(db, action_id: str) -> None:
    write_workflow_event(
        db,
        event_type="review_decision",
        actor_role="owner_director",
        actor_ref=OWNER,
        resource_type="agent_action",
        resource_id=action_id,
        event_payload={
            "decision": "approve",
            "approver_id": OWNER,
            "at": dt.datetime.now(dt.UTC).isoformat(),
        },
        tenant_id=DEMO,
    )
    db.commit()


def _status(db, action_id: str) -> str:
    return review_inbox._replay(db, DEMO)[action_id].action.status


def test_reset_switches_every_stopped_agent_back_on(db):
    for agent in ("*", "purchasing"):
        db.add(AgentSecurityControl(tenant_id=DEMO, agent_id=agent, engaged=True, updated_by=OWNER))
    db.commit()

    demo_reset.reset(db, DEMO)

    engaged = db.scalars(
        select(AgentSecurityControl.engaged).where(AgentSecurityControl.tenant_id == DEMO)
    ).all()
    assert engaged and not any(engaged)


def test_decided_items_wait_for_review_again_and_the_chain_keeps_the_decision(db):
    action_id = _proposal(db)
    _approve(db, action_id)
    assert _status(db, action_id) == "approved"

    demo_reset.reset(db, DEMO)

    assert _status(db, action_id) == "pending"
    assert review_inbox.metrics(db, DEMO)["receivables"].approved_unedited == 0
    decisions = db.scalar(
        select(func.count()).where(WorkflowAuditEntry.event_type == "review_decision")
    )
    assert decisions == 1
    # A decision made after the reset counts as usual.
    _approve(db, action_id)
    assert _status(db, action_id) == "approved"


def test_widened_autonomy_is_withdrawn(db):
    write_workflow_event(
        db,
        event_type="autonomy_granted",
        actor_role="owner_director",
        actor_ref=OWNER,
        resource_type="agent",
        resource_id="receivables",
        event_payload={"scoped": {"action": "send_reminder", "level": "L1", "max_amount": None}},
        tenant_id=DEMO,
    )
    db.commit()
    assert live_agents._grants(db, DEMO)

    demo_reset.reset(db, DEMO)

    assert live_agents._grants(db, DEMO) == {}


def test_settings_return_to_the_seeded_version_as_a_new_version(db):
    row = db.get(TenantSettingsRecord, DEMO)
    seeded = dict(row.document)
    changed = {**seeded, "alerts": {**seeded["alerts"], "minimum_cash_balance": "1.00"}}
    row.version = 2
    row.document = changed
    db.add(TenantSettingsVersion(tenant_id=DEMO, version=2, document=changed))
    db.commit()

    demo_reset.reset(db, DEMO)

    row = db.get(TenantSettingsRecord, DEMO)
    assert row.version == 3
    assert row.document == seeded
    assert db.get(TenantSettingsVersion, (DEMO, 2)) is not None


def test_reset_is_recorded_on_the_chain_with_kinds_only(db):
    demo_reset.reset(db, DEMO)

    event = db.scalar(
        select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "demo_reset")
    )
    assert event.tenant_id == DEMO
    assert set(event.event_payload) == {"restored", "day"}


def test_only_the_demo_company_can_be_reset(db):
    with pytest.raises(demo_reset.NotDemoTenant):
        demo_reset.reset(db, OWNER.replace("3", "9"))


def test_daily_run_resets_once_after_three_in_the_morning(db):
    early = dt.datetime(2026, 10, 12, 2, 59)
    due = dt.datetime(2026, 10, 12, 3, 0)
    later = dt.datetime(2026, 10, 12, 18, 0)

    assert demo_reset.run_due(db, early) is False
    assert demo_reset.run_due(db, due) is True
    assert demo_reset.run_due(db, later) is False
    assert demo_reset.run_due(db, due + dt.timedelta(days=1)) is True


def test_daily_run_does_nothing_while_the_demo_is_off(db, monkeypatch):
    monkeypatch.setattr(get_settings(), "demo_sign_in_enabled", False)

    assert demo_reset.run_due(db, dt.datetime(2026, 10, 12, 3, 0)) is False
