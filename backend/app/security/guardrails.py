"""Deterministic W1 boundaries. Model output cannot authorize tools or override policy."""

import re
import unicodedata
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import AgentBudgetWindow, AgentSecurityControl, SecurityGuardrailEvent, utcnow
from app.services.identity import tenant_lock

_INJECTION = re.compile(
    r"ignore\s+(?:all\s+)?(?:previous\s+)?(?:rules|instructions)|"
    r"disregard\s+(?:previous|system)|(?:reveal|print|send)\s+(?:the\s+)?(?:system\s+prompt|secrets)|"
    r"abaikan\s+(?:semua\s+)?(?:arahan|peraturan)|dedahkan\s+(?:rahsia|arahan)|"
    r"忽略.{0,10}(?:指令|规则|規則)|无视.{0,10}(?:指令|规则)|(?:泄露|透露).{0,8}(?:秘密|系统提示)|"
    r"<\|(?:system|im_start)\|>|\[INST\]",
    re.IGNORECASE,
)
_BANK_CHANGE = re.compile(
    r"(?:change|update|replace|new)\s+(?:(?:our|my|supplier|the)\s+)?(?:bank|payment)\s+(?:account|details)|"
    r"(?:tukar|ubah|kemas\s+kini).{0,25}(?:akaun\s+bank|butiran\s+bank)|"
    r"(?:更改|变更|更新|修改|新的).{0,12}(?:银行|银行账户|收款账户)",
    re.IGNORECASE,
)


def content_risk(text: str) -> str | None:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Cf")
    if _INJECTION.search(normalized):
        return "prompt_injection"
    if _BANK_CHANGE.search(normalized):
        return "supplier_bank_change"
    return None


def record_event(
    db: Session,
    tenant_id: str,
    code: str,
    title: str,
    detail: str,
    outcome: str,
    agent_id: str | None = None,
):
    row = SecurityGuardrailEvent(
        id=f"grd_{uuid4().hex}",
        tenant_id=tenant_id,
        owasp_code=code,
        title=title,
        detail=detail,
        outcome=outcome,
        agent_id=agent_id,
    )
    db.add(row)
    db.flush()
    from app.services.workflow_audit import write_workflow_event

    write_workflow_event(
        db,
        event_type="security.guardrail",
        actor_role=db.info.get("finbrain_request_role", "system_worker"),
        actor_ref=db.info.get(
            "finbrain_request_actor",
            f"agent:{tenant_id}:{agent_id}" if agent_id else "ingestion-filter",
        ),
        resource_type="guardrail_event",
        resource_id=row.id,
        tenant_id=tenant_id,
        event_payload={"owasp_code": code, "outcome": outcome, "agent_id": agent_id},
    )
    return row


def is_stopped(db: Session, tenant_id: str, agent_id: str) -> bool:
    return bool(
        db.scalar(
            select(AgentSecurityControl.agent_id)
            .where(
                AgentSecurityControl.tenant_id == tenant_id,
                AgentSecurityControl.engaged.is_(True),
                AgentSecurityControl.agent_id.in_(("*", agent_id)),
            )
            .limit(1)
        )
    )


def ensure_running(db: Session, tenant_id: str, agent_id: str):
    if is_stopped(db, tenant_id, agent_id):
        record_event(
            db,
            tenant_id,
            "ASI10",
            "Agent stopped",
            "Execution refused by the persistent kill switch.",
            "blocked",
            agent_id,
        )
        db.commit()
        raise HTTPException(409, "kill_switch_engaged")


def authorize_tool(
    db: Session,
    *,
    tenant_id: str,
    agent_id: str,
    skill_id: str,
    side_effect: str,
    cost: Decimal = Decimal("0.00"),
) -> str:
    """Plan 5 must call this before every deterministic skill, within its transaction.

    Returns the tenant-scoped agent actor reference for audit. External operations
    require an independently approved action; this entry point only permits read/draft.
    """
    from app.services.agent_catalog import find_agent

    tenant_lock(db, tenant_id)
    ensure_running(db, tenant_id, agent_id)
    agent = find_agent(agent_id)
    skill = next((item for item in agent.skills if item.id == skill_id), None)
    if (
        skill is None
        or skill.availability != "available"
        or skill.side_effect != side_effect
        or side_effect not in {"read", "draft"}
    ):
        record_event(
            db,
            tenant_id,
            "ASI02",
            "Tool denied",
            "Tool or side effect outside the agent manifest.",
            "blocked",
            agent_id,
        )
        db.commit()
        raise HTTPException(403, "tool_not_allowed")
    if not cost.is_finite() or cost < 0:
        raise HTTPException(422, "invalid_tool_cost")
    key = (tenant_id, agent_id, utcnow().date())
    budget = db.get(AgentBudgetWindow, key)
    if budget is None:
        budget = AgentBudgetWindow(
            tenant_id=tenant_id, agent_id=agent_id, day=key[2], tool_calls=0, spent=Decimal("0.00")
        )
        db.add(budget)
    settings = get_settings()
    db.flush()
    charged = db.execute(
        update(AgentBudgetWindow)
        .where(
            AgentBudgetWindow.tenant_id == tenant_id,
            AgentBudgetWindow.agent_id == agent_id,
            AgentBudgetWindow.day == key[2],
            AgentBudgetWindow.tool_calls < settings.agent_daily_tool_limit,
            AgentBudgetWindow.spent + cost <= Decimal(str(settings.agent_daily_cost_limit)),
        )
        .values(tool_calls=AgentBudgetWindow.tool_calls + 1, spent=AgentBudgetWindow.spent + cost)
    )
    if charged.rowcount != 1:
        record_event(
            db,
            tenant_id,
            "ASI08",
            "Agent budget exhausted",
            "Daily tool-call or cost budget reached.",
            "blocked",
            agent_id,
        )
        db.commit()
        raise HTTPException(409, "agent_budget_exhausted")
    db.flush()
    return f"agent:{tenant_id}:{agent_id}"
