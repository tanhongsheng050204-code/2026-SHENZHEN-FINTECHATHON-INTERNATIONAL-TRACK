"""Stub company settings: versioned customization, safety floors and industry templates.

Workstream B1 replaces it with tenant_settings and tenant_setting_changes. Settings are
data, never code: every change is validated against the TenantSettings schema (which
holds the safety floors), previewed, versioned and, for security, approved by a
second person. Nothing is stored; the stub echoes the resulting settings.
"""

import datetime as dt
import hashlib
import json
from decimal import Decimal

from pydantic import ValidationError

from app.contracts.common import DataMode, JobFunction
from app.contracts.settings import (
    AlertSettings,
    ApprovalSettings,
    BrandingSettings,
    CompanyProfile,
    FinancingPreferences,
    IndustryTemplate,
    IndustryTemplateId,
    PositionSetting,
    SecuritySettings,
    SettingsChange,
    SettingsChangeRequest,
    SettingsChangeResponse,
    SettingsResponse,
    SettingsSchemaResponse,
    TemplatePreview,
    TemplatesResponse,
    TenantSettings,
)
from app.schemas import UserRole
from app.stubs.positions import DISPLAY_NAMES

CURRENT_VERSION = 3


class SettingsError(ValueError):
    def __init__(self, detail: str | list[dict], status_code: int) -> None:
        super().__init__(str(detail))
        self.detail = detail
        self.status_code = status_code


_TEMPLATES: dict[IndustryTemplateId, IndustryTemplate] = {
    IndustryTemplateId.TRADING: IndustryTemplate(
        id=IndustryTemplateId.TRADING,
        name="Trading and distribution",
        description="Imports, stock and wholesale customers. Full synthetic demo data.",
        enabled_positions=[job for job in JobFunction if job != JobFunction.PRODUCTION],
        designed_positions=[],
        demo_data="full",
    ),
    IndustryTemplateId.SERVICES: IndustryTemplate(
        id=IndustryTemplateId.SERVICES,
        name="Services",
        description="Projects and retainers, no stock. Settings only.",
        enabled_positions=[
            JobFunction.OWNER,
            JobFunction.OPERATIONS,
            JobFunction.FINANCE,
            JobFunction.SALES,
            JobFunction.CUSTOMER_SERVICE,
            JobFunction.MARKETING,
            JobFunction.HR,
            JobFunction.COMPLIANCE,
        ],
        designed_positions=[],
        demo_data="settings_only",
    ),
    IndustryTemplateId.MANUFACTURING: IndustryTemplate(
        id=IndustryTemplateId.MANUFACTURING,
        name="Manufacturing",
        description="Production, materials and stock. Production is designed, not built.",
        enabled_positions=list(JobFunction),
        designed_positions=[JobFunction.PRODUCTION],
        demo_data="settings_only",
    ),
}


def _positions_for(template: IndustryTemplateId) -> list[PositionSetting]:
    enabled = set(_TEMPLATES[template].enabled_positions)
    return [
        PositionSetting(job_function=job, enabled=job in enabled, display_name=DISPLAY_NAMES[job])
        for job in JobFunction
    ]


def _settings(minimum_cash: str) -> TenantSettings:
    return TenantSettings(
        profile=CompanyProfile(
            company_name="Synthetic Trading Co.",
            industry=IndustryTemplateId.TRADING,
            size="small",
            currency="MYR",
            fiscal_year_start_month=7,
            state="Penang",
            working_days=["mon", "tue", "wed", "thu", "fri", "sat"],
            languages=["en", "ms", "zh"],
        ),
        positions=_positions_for(IndustryTemplateId.TRADING),
        approvals=ApprovalSettings(
            owner_escalation_amount=Decimal("20000.00"),
            owner_escalation_customer_count=10,
            promotion_min_sample=30,
            promotion_min_unedited_rate=0.9,
            demotion_max_rejection_rate=0.2,
            quiet_hours_start=dt.time(21, 0),
            quiet_hours_end=dt.time(8, 0),
        ),
        alerts=AlertSettings(
            minimum_cash_balance=Decimal(minimum_cash),
            alert_horizon_days=30,
            recipients=[JobFunction.OWNER, JobFunction.FINANCE],
            channels=["in_app", "email"],
        ),
        financing=FinancingPreferences(jurisdictions=["MY", "CN"]),
        security=SecuritySettings(
            mfa_required_roles=[
                UserRole.OWNER_DIRECTOR,
                UserRole.FINANCE_OPS,
                UserRole.COMPLIANCE,
            ],
            session_idle_minutes=30,
        ),
        branding=BrandingSettings(
            display_name="Synthetic Trading Co.", document_footer="Synthetic demo company"
        ),
    )


_HISTORY: dict[int, TenantSettings] = {
    1: _settings("30000.00"),
    2: _settings("40000.00"),
    3: _settings("50000.00"),
}


def current() -> SettingsResponse:
    return SettingsResponse(
        data_mode=DataMode.STUB,
        version=CURRENT_VERSION,
        template=IndustryTemplateId.TRADING,
        settings=_HISTORY[CURRENT_VERSION],
    )


def schema() -> SettingsSchemaResponse:
    return SettingsSchemaResponse(
        data_mode=DataMode.STUB, json_schema=TenantSettings.model_json_schema()
    )


def _validated(data: dict) -> TenantSettings:
    try:
        return TenantSettings.model_validate(data)
    except ValidationError as error:
        details = [
            {"loc": [str(part) for part in item["loc"]], "msg": item["msg"]}
            for item in error.errors()
        ]
        raise SettingsError(details, 422) from error


def _preview(area: str, before: TenantSettings, after: TenantSettings) -> list[str]:
    if area == "positions":
        lines: list[str] = []
        for old, new in zip(before.positions, after.positions, strict=True):
            if old.enabled != new.enabled:
                state = "enabled" if new.enabled else "disabled"
                lines.append(f"{new.job_function.value}: {state}")
            if old.display_name != new.display_name:
                lines.append(f"{new.job_function.value}: renamed to {new.display_name}")
        return lines
    old_values = getattr(before, area).model_dump(mode="json")
    new_values = getattr(after, area).model_dump(mode="json")
    return [
        f"{area}.{key}: {json.dumps(old_values[key])} → {json.dumps(new_values[key])}"
        for key in new_values
        if old_values.get(key) != new_values[key]
    ]


def _in_position_order(settings: TenantSettings) -> TenantSettings:
    order = list(JobFunction)
    ordered = sorted(settings.positions, key=lambda position: order.index(position.job_function))
    return settings.model_copy(update={"positions": ordered})


def propose(request: SettingsChangeRequest) -> SettingsChangeResponse:
    before = _HISTORY[CURRENT_VERSION]
    data = before.model_dump(mode="json")
    data[request.area] = request.value
    after = _in_position_order(_validated(data))
    lines = _preview(request.area, before, after)
    if not lines:
        raise SettingsError("no_changes", 409)
    pending = request.area == "security"
    digest = hashlib.sha256(json.dumps(request.value, sort_keys=True).encode()).hexdigest()[:8]
    change = SettingsChange(
        id=f"chg_{request.area}_{digest}",
        area=request.area,
        status="pending_approval" if pending else "applied",
        requires_approval=pending,
        version=CURRENT_VERSION + 1,
        preview=lines,
    )
    return SettingsChangeResponse(
        data_mode=DataMode.STUB, change=change, settings=before if pending else after
    )


def approve(change_id: str) -> SettingsChange:
    if not change_id.startswith("chg_security_"):
        raise SettingsError("change_not_found", 404)
    return SettingsChange(
        id=change_id,
        area="security",
        status="applied",
        requires_approval=True,
        version=CURRENT_VERSION + 1,
        preview=["Applied after Compliance approval"],
    )


def rollback(version: int) -> SettingsResponse:
    if version not in _HISTORY or version >= CURRENT_VERSION:
        raise SettingsError("invalid_rollback_version", 409)
    return SettingsResponse(
        data_mode=DataMode.STUB,
        version=CURRENT_VERSION + 1,
        template=_HISTORY[version].profile.industry,
        settings=_HISTORY[version],
    )


def templates() -> TemplatesResponse:
    return TemplatesResponse(
        data_mode=DataMode.STUB,
        current=IndustryTemplateId.TRADING,
        templates=list(_TEMPLATES.values()),
    )


def preview_template(template_id: IndustryTemplateId) -> TemplatePreview:
    enabled_now = {p.job_function for p in _HISTORY[CURRENT_VERSION].positions if p.enabled}
    target = _TEMPLATES[template_id]
    enabled_next = set(target.enabled_positions)
    order = list(JobFunction)
    return TemplatePreview(
        data_mode=DataMode.STUB,
        template_id=template_id,
        positions_added=sorted(enabled_next - enabled_now, key=order.index),
        positions_removed=sorted(enabled_now - enabled_next, key=order.index),
        designed_positions=target.designed_positions,
        data_kept=True,
    )


def apply_template(template_id: IndustryTemplateId) -> SettingsChangeResponse:
    before = _HISTORY[CURRENT_VERSION]
    profile = before.profile.model_copy(update={"industry": template_id})
    after = before.model_copy(
        update={"profile": profile, "positions": _positions_for(template_id)}
    )
    preview = preview_template(template_id)
    lines = [f"{job.value}: enabled" for job in preview.positions_added] + [
        f"{job.value}: disabled" for job in preview.positions_removed
    ]
    change = SettingsChange(
        id=f"chg_template_{template_id.value}",
        area="positions",
        status="applied",
        requires_approval=False,
        version=CURRENT_VERSION + 1,
        preview=lines or ["No position changes"],
    )
    return SettingsChangeResponse(data_mode=DataMode.STUB, change=change, settings=after)
