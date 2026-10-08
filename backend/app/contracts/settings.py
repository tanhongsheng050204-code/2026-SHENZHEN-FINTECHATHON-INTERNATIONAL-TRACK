import datetime as dt
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.contracts.common import DataMode, JobFunction
from app.schemas import UserRole

PRIVILEGED_ROLES = frozenset(
    {UserRole.OWNER_DIRECTOR, UserRole.FINANCE_OPS, UserRole.COMPLIANCE}
)
MAX_SESSION_IDLE_MINUTES = 60

SettingsArea = Literal[
    "profile", "positions", "approvals", "alerts", "financing", "security", "branding"
]


class IndustryTemplateId(StrEnum):
    TRADING = "trading"
    SERVICES = "services"
    MANUFACTURING = "manufacturing"


class CompanyProfile(BaseModel):
    company_name: str = Field(min_length=1, max_length=120)
    industry: IndustryTemplateId
    size: Literal["micro", "small", "medium"]
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    fiscal_year_start_month: int = Field(ge=1, le=12)
    state: str = Field(min_length=1, max_length=40)
    working_days: list[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]] = Field(
        min_length=1
    )
    languages: list[Literal["en", "ms", "zh"]] = Field(min_length=1)


class PositionSetting(BaseModel):
    job_function: JobFunction
    enabled: bool
    display_name: str = Field(min_length=1, max_length=60)


class ApprovalSettings(BaseModel):
    owner_escalation_amount: Decimal = Field(gt=0)
    owner_escalation_customer_count: int = Field(ge=1)
    promotion_min_sample: int = Field(ge=5)
    promotion_min_unedited_rate: float = Field(ge=0.5, le=1.0)
    demotion_max_rejection_rate: float = Field(ge=0.0, le=0.5)
    quiet_hours_start: dt.time
    quiet_hours_end: dt.time


class AlertSettings(BaseModel):
    minimum_cash_balance: Decimal = Field(ge=0)
    alert_horizon_days: int = Field(ge=7, le=90)
    recipients: list[JobFunction] = Field(min_length=1)
    channels: list[Literal["in_app", "email", "telegram"]] = Field(min_length=1)
    critical_alerts_enabled: Literal[True] = True

    @model_validator(mode="after")
    def _owner_always_warned(self) -> "AlertSettings":
        if JobFunction.OWNER not in self.recipients:
            raise ValueError("owner_must_receive_critical_alerts")
        return self


class FinancingPreferences(BaseModel):
    islamic_only: bool = False
    excluded_categories: list[str] = Field(default_factory=list, max_length=20)
    jurisdictions: list[Literal["MY", "CN"]] = Field(min_length=1)


class SecuritySettings(BaseModel):
    mfa_required_roles: list[UserRole]
    session_idle_minutes: int = Field(ge=5, le=MAX_SESSION_IDLE_MINUTES)

    @model_validator(mode="after")
    def _privileged_roles_need_mfa(self) -> "SecuritySettings":
        if not PRIVILEGED_ROLES.issubset(self.mfa_required_roles):
            raise ValueError("mfa_required_for_privileged_roles")
        return self


class BrandingSettings(BaseModel):
    display_name: str = Field(min_length=1, max_length=120)
    document_footer: str | None = Field(default=None, max_length=200)


class TenantSettings(BaseModel):
    profile: CompanyProfile
    positions: list[PositionSetting]
    approvals: ApprovalSettings
    alerts: AlertSettings
    financing: FinancingPreferences
    security: SecuritySettings
    branding: BrandingSettings

    @model_validator(mode="after")
    def _positions_are_complete(self) -> "TenantSettings":
        listed = [position.job_function for position in self.positions]
        if sorted(listed) != sorted(JobFunction):
            raise ValueError("every_position_listed_once")
        owner = next(p for p in self.positions if p.job_function == JobFunction.OWNER)
        if not owner.enabled:
            raise ValueError("owner_position_required")
        return self


class SettingsResponse(BaseModel):
    data_mode: DataMode
    version: int
    template: IndustryTemplateId
    settings: TenantSettings


class SettingsSchemaResponse(BaseModel):
    data_mode: DataMode
    json_schema: dict[str, Any]


class SettingsChangeRequest(BaseModel):
    area: SettingsArea
    value: dict[str, Any] | list[dict[str, Any]]


class SettingsChange(BaseModel):
    id: str
    area: SettingsArea
    status: Literal["applied", "pending_approval"]
    requires_approval: bool
    version: int
    preview: list[str]


class SettingsChangeResponse(BaseModel):
    data_mode: DataMode
    change: SettingsChange
    settings: TenantSettings


class RollbackRequest(BaseModel):
    version: int = Field(ge=1)


class IndustryTemplate(BaseModel):
    id: IndustryTemplateId
    name: str
    description: str
    enabled_positions: list[JobFunction]
    designed_positions: list[JobFunction]
    demo_data: Literal["full", "settings_only"]


class TemplatesResponse(BaseModel):
    data_mode: DataMode
    current: IndustryTemplateId
    templates: list[IndustryTemplate]


class TemplatePreview(BaseModel):
    data_mode: DataMode
    template_id: IndustryTemplateId
    positions_added: list[JobFunction]
    positions_removed: list[JobFunction]
    designed_positions: list[JobFunction]
    data_kept: bool
