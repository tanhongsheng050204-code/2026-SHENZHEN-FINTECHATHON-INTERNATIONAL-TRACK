"""Schema-validated initial settings and the three industry templates."""

import datetime as dt
from decimal import Decimal

from app.contracts.common import JobFunction
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
    TenantSettings,
)
from app.schemas import UserRole

DISPLAY_NAMES = {job: job.value.replace("_", " ").title() for job in JobFunction}

TEMPLATES: dict[IndustryTemplateId, IndustryTemplate] = {
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


def positions_for(template: IndustryTemplateId) -> list[PositionSetting]:
    enabled = set(TEMPLATES[template].enabled_positions)
    return [
        PositionSetting(job_function=job, enabled=job in enabled, display_name=DISPLAY_NAMES[job])
        for job in JobFunction
    ]


def default_settings(
    company_name: str, minimum_cash: str = "50000.00", session_idle_minutes: int = 30
) -> TenantSettings:
    return TenantSettings(
        profile=CompanyProfile(
            company_name=company_name,
            industry=IndustryTemplateId.TRADING,
            size="small",
            currency="MYR",
            fiscal_year_start_month=7,
            state="Penang",
            working_days=["mon", "tue", "wed", "thu", "fri", "sat"],
            languages=["en", "ms", "zh"],
        ),
        positions=positions_for(IndustryTemplateId.TRADING),
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
            session_idle_minutes=session_idle_minutes,
        ),
        branding=BrandingSettings(display_name=company_name, document_footer=None),
    )


AREAS = ("profile", "positions", "approvals", "alerts", "financing", "security", "branding")
