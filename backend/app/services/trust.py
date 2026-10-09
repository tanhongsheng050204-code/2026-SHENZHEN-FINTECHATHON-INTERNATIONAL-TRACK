from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.principal import AuthPrincipal
from app.contracts.common import DataMode
from app.contracts.trust import GuardrailEvent, PostureMetric, PostureResponse
from app.models import AuthUserRole, SecurityGuardrailEvent, VaultKeyVersion, utcnow
from app.services.audit import verify_audit_chain
from app.services.workflow_audit import verify_workflow_chain


def guardrail_events(db: Session, principal: AuthPrincipal, limit: int):
    return [
        GuardrailEvent(
            id=row.id,
            occurred_at=row.occurred_at,
            agent_id=row.agent_id,
            owasp_code=row.owasp_code,
            title=row.title,
            detail=row.detail,
            outcome=row.outcome,
        )
        for row in db.scalars(
            select(SecurityGuardrailEvent)
            .where(SecurityGuardrailEvent.tenant_id == str(principal.tenant_id))
            .order_by(SecurityGuardrailEvent.occurred_at.desc(), SecurityGuardrailEvent.id)
            .limit(limit)
        )
    ]


def posture(db: Session, principal: AuthPrincipal):
    from app.models import TenantSettingsRecord

    setting = db.get(TenantSettingsRecord, str(principal.tenant_id))
    required = (
        setting.document["security"]["mfa_required_roles"]
        if setting
        else ["owner_director", "finance_ops", "compliance"]
    )
    people = db.scalars(
        select(AuthUserRole).where(
            AuthUserRole.tenant_id == str(principal.tenant_id), AuthUserRole.active.is_(True)
        )
    ).all()
    mandatory = [row for row in people if row.user_role in required]
    enrolled = sum(row.mfa_enrolled for row in mandatory)
    inactive = sum(row.last_active_at is None or _old(row.last_active_at) for row in people)
    disclosure_ok = verify_audit_chain(db, str(principal.tenant_id))
    workflow_ok = verify_workflow_chain(db, str(principal.tenant_id))
    events = db.scalar(
        select(func.count())
        .select_from(SecurityGuardrailEvent)
        .where(SecurityGuardrailEvent.tenant_id == str(principal.tenant_id))
    )
    key = db.scalar(select(VaultKeyVersion).where(VaultKeyVersion.status == "active"))
    metrics = [
        PostureMetric(
            key="mfa_coverage",
            label="Mandatory MFA",
            value=f"{enrolled}/{len(mandatory)}",
            status="good" if enrolled == len(mandatory) else "risk",
            detail="Verified enrolment recorded after provider TOTP verification.",
        ),
        PostureMetric(
            key="inactive_users",
            label="Access review",
            value=str(inactive),
            status="attention" if inactive else "good",
            detail="Active members never seen or inactive for 30 days.",
        ),
        PostureMetric(
            key="audit_integrity",
            label="Audit chains",
            value="verified" if disclosure_ok and workflow_ok else "failed",
            status="good" if disclosure_ok and workflow_ok else "risk",
            detail="Recomputed tenant disclosure and workflow hash chains.",
        ),
        PostureMetric(
            key="guardrail_events",
            label="Recorded guardrail events",
            value=str(events),
            status="good",
            detail="Persisted events; no sample attacks are included.",
        ),
        PostureMetric(
            key="vault_generation",
            label="Vault key",
            value=str(key.version) if key else "not initialized",
            status="good" if key else "attention",
            detail="Actual active vault key generation.",
        ),
    ]
    score = max(
        0,
        100
        - sum(
            25 if metric.status == "risk" else 10 if metric.status == "attention" else 0
            for metric in metrics
        ),
    )
    return PostureResponse(
        data_mode=DataMode.LIVE,
        score=score,
        metrics=metrics,
        recent_events=guardrail_events(db, principal, 10),
    )


def _old(value):
    from app.auth.sessions import aware

    return aware(value) < utcnow() - timedelta(days=30)
