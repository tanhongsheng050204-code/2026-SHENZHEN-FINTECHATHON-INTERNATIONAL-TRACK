import json
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.principal import AuthPrincipal
from app.contracts.common import DataMode, JobFunction
from app.contracts.settings import (
    IndustryTemplateId,
    SettingsChange,
    SettingsChangeRequest,
    SettingsChangeResponse,
    SettingsResponse,
    TemplatePreview,
    TemplatesResponse,
    TenantSettings,
)
from app.models import (
    Tenant,
    TenantSettingsChange,
    TenantSettingsRecord,
    TenantSettingsVersion,
    utcnow,
)
from app.services.identity import audit, tenant_lock
from app.services.settings_catalog import AREAS, TEMPLATES, default_settings, positions_for


def initialize_settings(db: Session, tenant_id: str, company_name: str) -> TenantSettingsRecord:
    document = default_settings(company_name).model_dump(mode="json")
    row = TenantSettingsRecord(tenant_id=tenant_id, version=1, document=document)
    db.add(row)
    db.add(TenantSettingsVersion(tenant_id=tenant_id, version=1, document=document))
    db.flush()
    return row


def current_row(db: Session, principal: AuthPrincipal) -> TenantSettingsRecord:
    tenant_id = str(principal.tenant_id)
    tenant_lock(db, tenant_id)
    row = db.get(TenantSettingsRecord, tenant_id)
    if row is None:
        tenant = db.get(Tenant, tenant_id)
        if tenant is None:
            raise HTTPException(403, "tenant_not_provisioned")
        row = initialize_settings(db, tenant_id, tenant.name)
    return row


def current(db: Session, principal: AuthPrincipal) -> SettingsResponse:
    row = current_row(db, principal)
    settings = TenantSettings.model_validate(row.document)
    db.commit()
    return SettingsResponse(
        data_mode=DataMode.LIVE,
        version=row.version,
        template=settings.profile.industry,
        settings=settings,
    )


def validated(data: dict) -> TenantSettings:
    try:
        return TenantSettings.model_validate(data)
    except ValidationError as error:
        raise HTTPException(
            422,
            [
                {"loc": [str(part) for part in item["loc"]], "msg": item["msg"]}
                for item in error.errors()
            ],
        ) from error


def _tighten(before: TenantSettings, after: TenantSettings):
    if after.security.session_idle_minutes > before.security.session_idle_minutes or not set(
        before.security.mfa_required_roles
    ).issubset(after.security.mfa_required_roles):
        raise HTTPException(409, "security_may_only_tighten")


def _preview(before: TenantSettings, after: TenantSettings) -> list[str]:
    # Approvers must see the proposed values, particularly the MFA/idle limits.
    old, new = before.model_dump(mode="json"), after.model_dump(mode="json")
    changes = [
        (
            f"{area}.{key}: {json.dumps(old[area].get(key))} → {json.dumps(new[area][key])}"
            if isinstance(new[area], dict)
            else f"{area}: changed"
        )
        for area in AREAS
        if area != "positions" and old[area] != new[area]
        for key in (new[area] if isinstance(new[area], dict) else ["positions"])
        if not isinstance(new[area], dict) or old[area].get(key) != new[area][key]
    ]
    old_positions = {item.job_function: item for item in before.positions}
    for item in after.positions:
        previous = old_positions[item.job_function]
        if item.enabled != previous.enabled:
            changes.append(f"{item.job_function}: {'enabled' if item.enabled else 'disabled'}")
        if item.display_name != previous.display_name:
            changes.append(f"{item.job_function}: renamed to {item.display_name}")
    return changes


def change_view(row: TenantSettingsChange) -> SettingsChange:
    return SettingsChange(
        id=row.id,
        area=row.area,
        status=row.status,
        requires_approval=row.requires_approval,
        version=row.version,
        preview=row.preview,
    )


def _apply(db: Session, current: TenantSettingsRecord, after: TenantSettings):
    version = current.version + 1
    document = after.model_dump(mode="json")
    updated = db.execute(
        update(TenantSettingsRecord)
        .where(
            TenantSettingsRecord.tenant_id == current.tenant_id,
            TenantSettingsRecord.version == current.version,
        )
        .values(version=version, document=document)
    )
    if updated.rowcount != 1:
        raise HTTPException(409, "settings_version_conflict")
    db.add(TenantSettingsVersion(tenant_id=current.tenant_id, version=version, document=document))
    db.flush()


def _propose(
    db: Session,
    principal: AuthPrincipal,
    current: TenantSettingsRecord,
    area: str,
    after: TenantSettings,
) -> SettingsChangeResponse:
    before = validated(current.document)
    if before == after:
        raise HTTPException(409, "no_changes")
    _tighten(before, after)
    pending = before.security != after.security
    row = TenantSettingsChange(
        id=f"chg_{uuid4().hex}",
        tenant_id=str(principal.tenant_id),
        area=area,
        status="pending_approval" if pending else "applied",
        requires_approval=pending,
        base_version=current.version,
        version=current.version + 1,
        proposed_document=after.model_dump(mode="json"),
        preview=_preview(before, after),
        proposer_id=str(principal.user_id),
        decided_at=None if pending else utcnow(),
    )
    db.add(row)
    if not pending:
        _apply(db, current, after)
    audit(
        db,
        principal,
        "settings.proposed" if pending else "settings.applied",
        "settings_change",
        row.id,
        area=area,
        base_version=row.base_version,
        version=row.version,
    )
    db.commit()
    return SettingsChangeResponse(
        data_mode=DataMode.LIVE, change=change_view(row), settings=before if pending else after
    )


def propose(db: Session, principal: AuthPrincipal, request: SettingsChangeRequest):
    row = current_row(db, principal)
    document = {**row.document, request.area: request.value}
    return _propose(db, principal, row, request.area, validated(document))


def changes(db: Session, principal: AuthPrincipal, status=None):
    query = select(TenantSettingsChange).where(
        TenantSettingsChange.tenant_id == str(principal.tenant_id)
    )
    if status:
        query = query.where(TenantSettingsChange.status == status)
    return [
        change_view(row)
        for row in db.scalars(query.order_by(TenantSettingsChange.created_at.desc()))
    ]


def decide(db: Session, principal: AuthPrincipal, change_id: str, *, approve: bool):
    current = current_row(db, principal)
    row = db.scalar(
        select(TenantSettingsChange)
        .where(
            TenantSettingsChange.id == change_id,
            TenantSettingsChange.tenant_id == str(principal.tenant_id),
        )
        .with_for_update()
    )
    if row is None:
        raise HTTPException(404, "change_not_found")
    if row.status != "pending_approval":
        raise HTTPException(409, "change_not_pending")
    if row.proposer_id == str(principal.user_id):
        raise HTTPException(409, "same_person_cannot_approve")
    if approve and row.base_version != current.version:
        raise HTTPException(409, "settings_version_conflict")
    after = validated(row.proposed_document)
    before = validated(current.document)
    if approve:
        _tighten(before, after)
        _apply(db, current, after)
    row.status = "applied" if approve else "rejected"
    row.reviewer_id = str(principal.user_id)
    row.decided_at = utcnow()
    audit(db, principal, f"settings.{row.status}", "settings_change", row.id, version=row.version)
    db.commit()
    return SettingsChangeResponse(
        data_mode=DataMode.LIVE, change=change_view(row), settings=after if approve else before
    )


def rollback(db: Session, principal: AuthPrincipal, version: int):
    current = current_row(db, principal)
    old = db.get(TenantSettingsVersion, (str(principal.tenant_id), version))
    if old is None or version >= current.version:
        raise HTTPException(409, "invalid_rollback_version")
    return _propose(db, principal, current, "rollback", validated(old.document))


def templates(db: Session, principal: AuthPrincipal):
    return TemplatesResponse(
        data_mode=DataMode.LIVE,
        current=current(db, principal).template,
        templates=list(TEMPLATES.values()),
    )


def preview_template(db: Session, principal: AuthPrincipal, template_id: IndustryTemplateId):
    before = validated(current_row(db, principal).document)
    enabled = {position.job_function for position in before.positions if position.enabled}
    target = TEMPLATES[template_id]
    next_enabled = set(target.enabled_positions)
    return TemplatePreview(
        data_mode=DataMode.LIVE,
        template_id=template_id,
        positions_added=[job for job in JobFunction if job in next_enabled - enabled],
        positions_removed=[job for job in JobFunction if job in enabled - next_enabled],
        designed_positions=target.designed_positions,
        data_kept=True,
    )


def apply_template(db: Session, principal: AuthPrincipal, template_id: IndustryTemplateId):
    current = current_row(db, principal)
    names = {item["job_function"]: item["display_name"] for item in current.document["positions"]}
    document = {
        **current.document,
        "profile": {**current.document["profile"], "industry": template_id.value},
        "positions": [
            {**position.model_dump(mode="json"), "display_name": names[position.job_function]}
            for position in positions_for(template_id)
        ],
    }
    return _propose(db, principal, current, "positions", validated(document))
