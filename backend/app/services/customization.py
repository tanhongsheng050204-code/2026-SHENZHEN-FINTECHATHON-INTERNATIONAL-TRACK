from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.principal import AuthPrincipal
from app.contracts.customization import (
    AlertRule,
    AlertRuleRequest,
    MessageTemplate,
    MessageTemplateRequest,
    placeholders_in,
)
from app.models import TenantCustomization
from app.services.identity import audit


def list_items(db: Session, principal: AuthPrincipal, kind: str):
    model = MessageTemplate if kind == "message_template" else AlertRule
    return [
        model.model_validate(row.document)
        for row in db.scalars(
            select(TenantCustomization)
            .where(
                TenantCustomization.tenant_id == str(principal.tenant_id),
                TenantCustomization.kind == kind,
            )
            .order_by(TenantCustomization.created_at, TenantCustomization.id)
        )
    ]


def create_template(db: Session, principal: AuthPrincipal, request: MessageTemplateRequest):
    template = MessageTemplate(
        id=f"tpl_{uuid4().hex}",
        **request.model_dump(),
        placeholders=placeholders_in(request.body),
        status="draft",
    )
    row = TenantCustomization(
        id=template.id,
        tenant_id=str(principal.tenant_id),
        kind="message_template",
        document=template.model_dump(mode="json"),
        created_by=str(principal.user_id),
    )
    db.add(row)
    audit(db, principal, "message_template.created", "message_template", row.id)
    db.commit()
    return template


def approve_template(db: Session, principal: AuthPrincipal, template_id: str):
    row = db.scalar(
        select(TenantCustomization)
        .where(
            TenantCustomization.id == template_id,
            TenantCustomization.tenant_id == str(principal.tenant_id),
            TenantCustomization.kind == "message_template",
        )
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "template_not_found")
    if row.document["status"] != "draft":
        raise HTTPException(409, "template_not_draft")
    row.document = {**row.document, "status": "approved"}
    audit(db, principal, "message_template.approved", "message_template", row.id)
    db.commit()
    return MessageTemplate.model_validate(row.document)


def create_rule(db: Session, principal: AuthPrincipal, request: AlertRuleRequest):
    # Every critical cash rule retains an Owner recipient.
    if request.metric == "projected_balance" and "owner" not in request.recipients:
        raise HTTPException(422, "owner_must_receive_critical_alerts")
    rule = AlertRule(id=f"rule_{uuid4().hex}", **request.model_dump(), enabled=True)
    row = TenantCustomization(
        id=rule.id,
        tenant_id=str(principal.tenant_id),
        kind="alert_rule",
        document=rule.model_dump(mode="json"),
        created_by=str(principal.user_id),
    )
    db.add(row)
    audit(db, principal, "alert_rule.created", "alert_rule", row.id, metric=request.metric)
    db.commit()
    return rule
