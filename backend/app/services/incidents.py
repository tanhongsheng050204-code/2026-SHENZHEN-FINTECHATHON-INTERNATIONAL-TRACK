"""The incident register, for Malaysia's PDPA breach rules, and the data protection officer.

Since 1 June 2025 the amended PDPA requires a data protection officer, breach
notification to the Commissioner, and, where significant harm is likely, telling
the people affected. DuitDuit keeps the record and the checklist; it does not
decide the law for the company and it sends nothing. A notice is drafted as a
review-inbox proposal for Compliance, who sends it outside DuitDuit and then marks
the step done.

Incidents are kinds and numbers on the workflow chain ("incident_opened",
"incident_step"), with no free text, so no personal data reaches the record. The
officer is a member of the team ("dpo_assigned" with their user id).
"""

import datetime as dt
import secrets

from sqlalchemy import select

from app.auth.principal import AuthPrincipal
from app.contracts.common import AutonomyLevel, JobFunction
from app.contracts.security import ChecklistItem, Incident, IncidentRequest, Officer
from app.models import AuthUserRole, WorkflowAuditEntry
from app.services import review_inbox
from app.services.workflow_audit import chain_scalars, write_workflow_event

OPENED, STEP, DPO = "incident_opened", "incident_step", "dpo_assigned"
STEPS = ("contained", "assessed", "commissioner_notified", "individuals_notified", "closed")
_KIND_TEXT = {
    "unauthorized_access": "unauthorised access to personal data",
    "lost_or_stolen_device": "a lost or stolen device holding personal data",
    "data_sent_to_wrong_person": "personal data sent to the wrong person",
    "system_compromise": "a compromise of a system holding personal data",
    "vendor_breach": "a breach at a service provider holding our personal data",
    "other": "a personal data breach",
}
_DATA_TEXT = {
    "contact_details": "contact details",
    "identity_numbers": "identity numbers",
    "financial_records": "financial records",
    "employee_records": "employee records",
    "credentials": "sign-in credentials",
}


class IncidentError(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _aware(moment: dt.datetime) -> dt.datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=dt.UTC)


def _required(step: str, significant_harm: bool) -> bool:
    return step != "individuals_notified" or significant_harm


def incidents(db, tenant_id: str) -> list[Incident]:
    opened: dict[str, WorkflowAuditEntry] = {}
    done: dict[str, dict[str, WorkflowAuditEntry]] = {}
    for row in chain_scalars(
        db,
        select(WorkflowAuditEntry)
        .where(
            WorkflowAuditEntry.tenant_id == tenant_id,
            WorkflowAuditEntry.event_type.in_((OPENED, STEP)),
        )
        .order_by(WorkflowAuditEntry.id),
    ):
        if row.event_type == OPENED:
            opened[row.resource_id] = row
        else:
            done.setdefault(row.resource_id, {}).setdefault(row.event_payload["step"], row)
    found = []
    for incident_id, row in opened.items():
        request = IncidentRequest.model_construct(**row.event_payload)
        steps = done.get(incident_id, {})
        checklist = [
            ChecklistItem(
                step=step,
                required=_required(step, request.significant_harm),
                done=step in steps,
                done_at=_aware(steps[step].created_at) if step in steps else None,
                done_by_role=steps[step].actor_role if step in steps else None,
            )
            for step in STEPS
        ]
        found.append(
            Incident(
                id=incident_id,
                kind=request.kind,
                data_kinds=list(request.data_kinds),
                people_affected=request.people_affected,
                significant_harm=request.significant_harm,
                detected_on=dt.date.fromisoformat(str(request.detected_on)),
                opened_at=_aware(row.created_at),
                opened_by_role=row.actor_role,
                status="closed" if "closed" in steps else "open",
                checklist=checklist,
            )
        )
    return sorted(found, key=lambda i: i.opened_at, reverse=True)


def _one(db, tenant_id: str, incident_id: str) -> Incident:
    incident = next((i for i in incidents(db, tenant_id) if i.id == incident_id), None)
    if incident is None:
        raise IncidentError("incident_not_found", 404)
    return incident


def open_incident(db, principal: AuthPrincipal, request: IncidentRequest) -> Incident:
    incident_id = "inc_" + secrets.token_hex(6)
    write_workflow_event(
        db,
        event_type=OPENED,
        actor_role=principal.role.value,
        actor_ref=principal.actor_ref,
        resource_type="incident",
        resource_id=incident_id,
        event_payload=request.model_dump(mode="json"),
        tenant_id=str(principal.tenant_id),
    )
    db.commit()
    return _one(db, str(principal.tenant_id), incident_id)


def complete_step(db, principal: AuthPrincipal, incident_id: str, step: str) -> Incident:
    tenant_id = str(principal.tenant_id)
    incident = _one(db, tenant_id, incident_id)
    if incident.status == "closed":
        raise IncidentError("incident_closed", 409)
    if step == "closed" and any(
        item.required and not item.done for item in incident.checklist if item.step != "closed"
    ):
        raise IncidentError("required_steps_open", 409)
    if not any(item.step == step and item.done for item in incident.checklist):
        write_workflow_event(
            db,
            event_type=STEP,
            actor_role=principal.role.value,
            actor_ref=principal.actor_ref,
            resource_type="incident",
            resource_id=incident_id,
            event_payload={"step": step},
            tenant_id=tenant_id,
        )
        db.commit()
    return _one(db, tenant_id, incident_id)


def draft_notice(db, principal: AuthPrincipal, incident_id: str, audience: str) -> str:
    """A notice for the Commissioner or the people affected, as a proposal; nothing is sent."""
    tenant_id = str(principal.tenant_id)
    incident = _one(db, tenant_id, incident_id)
    what = _KIND_TEXT[incident.kind]
    data = ", ".join(_DATA_TEXT[kind] for kind in incident.data_kinds)
    when = f"{incident.detected_on:%d %B %Y}"
    if audience == "commissioner":
        title = "Breach notice to the Personal Data Protection Commissioner"
        draft = (
            f"We are notifying the Commissioner of {what}, detected on {when}. "
            f"Personal data involved: {data}. People affected (estimate): "
            f"{incident.people_affected}. Significant harm is "
            f"{'likely' if incident.significant_harm else 'not considered likely'}. "
            "We have contained the incident and are assessing it; our data protection officer "
            "is the contact for this notice. [Add the measures taken and planned.]"
        )
    else:
        title = "Breach notice to the people affected"
        draft = (
            f"We are writing to tell you about {what}, detected on {when}, which may involve "
            f"your {data}. [Say what happened, what we have done, what you can do to protect "
            "yourself, and how to contact our data protection officer.]"
        )
    return review_inbox.propose(
        db,
        tenant_id,
        agent_id="compliance",
        reviewer=JobFunction.COMPLIANCE,
        level=AutonomyLevel.L2,
        title=title,
        summary=f"Draft notice for incident {incident_id}. Check it against the Commissioner's "
        "guideline, complete the bracketed parts, and send it outside DuitDuit. "
        "Nothing has been sent.",
        draft=draft,
        evidence=[],
    )


def officer(db, tenant_id: str) -> Officer | None:
    rows = chain_scalars(
        db,
        select(WorkflowAuditEntry)
        .where(WorkflowAuditEntry.tenant_id == tenant_id, WorkflowAuditEntry.event_type == DPO)
        .order_by(WorkflowAuditEntry.id.desc())
        .limit(1),
    )
    if not rows:
        return None
    member = db.get(AuthUserRole, (rows[0].resource_id, tenant_id))
    if member is None or not member.active:
        return None  # the officer left the team: name a new one
    return Officer(
        user_id=member.user_id,
        display_name=member.display_name,
        email_masked=member.email_masked,
        role=member.user_role,
    )


def name_officer(db, principal: AuthPrincipal, user_id: str) -> Officer:
    tenant_id = str(principal.tenant_id)
    member = db.get(AuthUserRole, (user_id, tenant_id))
    if member is None or not member.active:
        raise IncidentError("member_not_found", 404)
    write_workflow_event(
        db,
        event_type=DPO,
        actor_role=principal.role.value,
        actor_ref=principal.actor_ref,
        resource_type="auth_user",
        resource_id=user_id,
        event_payload={"user_id": user_id},
        tenant_id=tenant_id,
    )
    db.commit()
    return officer(db, tenant_id)
