from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.principal import AuthPrincipal
from app.contracts.agents import AgentListResponse, KillSwitchRequest
from app.contracts.common import DataMode
from app.models import AgentSecurityControl, utcnow
from app.services.agent_catalog import agents, find_agent
from app.services.identity import audit, tenant_lock


def list_agents(db: Session, principal: AuthPrincipal):
    controls = {
        row.agent_id: row.engaged
        for row in db.scalars(
            select(AgentSecurityControl).where(
                AgentSecurityControl.tenant_id == str(principal.tenant_id)
            )
        )
    }
    global_stop = controls.get("*", False)
    return AgentListResponse(
        data_mode=DataMode.LIVE,
        global_kill_switch_engaged=global_stop,
        agents=[
            agent.model_copy(
                update={"kill_switch_engaged": global_stop or controls.get(agent.id, False)}
            )
            for agent in agents()
        ],
    )


def kill_switch(db: Session, principal: AuthPrincipal, request: KillSwitchRequest):
    from fastapi import HTTPException

    if request.agent_id:
        try:
            find_agent(request.agent_id)
        except LookupError as error:
            raise HTTPException(404, "agent_not_found") from error
    tenant_id = str(principal.tenant_id)
    tenant_lock(db, tenant_id)
    key = (tenant_id, request.agent_id or "*")
    row = db.get(AgentSecurityControl, key)
    if row is None:
        row = AgentSecurityControl(
            tenant_id=tenant_id, agent_id=key[1], updated_by=str(principal.user_id)
        )
        db.add(row)
    row.engaged = request.engaged
    row.updated_by = str(principal.user_id)
    row.updated_at = utcnow()
    audit(db, principal, "agent.kill_switch", "agent", key[1], engaged=request.engaged)
    db.commit()
    return list_agents(db, principal)
