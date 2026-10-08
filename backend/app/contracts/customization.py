import hashlib
import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.contracts.common import DataMode, JobFunction

TEMPLATE_PLACEHOLDERS = frozenset(
    {"customer_name", "invoice_no", "amount", "due_date", "company_name", "sender_name"}
)
_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
_EMAIL_LIKE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_LONG_NUMBER = re.compile(r"\d{9,}")

IMPORT_FIELDS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    # schema: (all target fields, required target fields)
    "bank_statement_v1": (
        frozenset(
            {"date", "description", "debit", "credit", "balance", "counterparty", "reference"}
        ),
        frozenset({"date", "description", "debit", "credit"}),
    ),
    "payables_register_v1": (
        frozenset(
            {"bill_id", "supplier", "amount", "currency", "due_date", "status", "bank_account"}
        ),
        frozenset({"bill_id", "supplier", "amount", "currency", "due_date"}),
    ),
}

ImportSchema = Literal["bank_statement_v1", "payables_register_v1"]
AlertMetric = Literal[
    "projected_balance",
    "overdue_amount_per_customer",
    "stock_below_reorder",
    "payroll_coverage_days",
    "marketing_return_per_ringgit",
    "open_disputes",
]


def placeholders_in(body: str) -> list[str]:
    return list(dict.fromkeys(_PLACEHOLDER.findall(body)))


class MessageTemplate(BaseModel):
    id: str
    kind: Literal["payment_reminder", "customer_reply", "supplier_query"]
    language: Literal["en", "ms", "zh"]
    tone: Literal["formal", "friendly"]
    body: str
    placeholders: list[str]
    status: Literal["draft", "approved"]


class MessageTemplateRequest(BaseModel):
    kind: Literal["payment_reminder", "customer_reply", "supplier_query"]
    language: Literal["en", "ms", "zh"]
    tone: Literal["formal", "friendly"]
    body: str = Field(min_length=10, max_length=2000)

    @field_validator("body")
    @classmethod
    def _safe_body(cls, body: str) -> str:
        unknown = [name for name in placeholders_in(body) if name not in TEMPLATE_PLACEHOLDERS]
        if unknown:
            raise ValueError(f"unknown_placeholder:{unknown[0]}")
        if _EMAIL_LIKE.search(body) or _LONG_NUMBER.search(body):
            raise ValueError("personal_data_in_template")
        return body


class MessageTemplatesResponse(BaseModel):
    data_mode: DataMode
    templates: list[MessageTemplate]


class MessageTemplateResponse(BaseModel):
    data_mode: DataMode
    template: MessageTemplate


class ImportMapping(BaseModel):
    id: str
    schema_name: ImportSchema
    name: str
    column_map: dict[str, str]
    header_fingerprint: str


def header_fingerprint(headers: list[str]) -> str:
    normalized = sorted(header.strip().casefold() for header in headers)
    return hashlib.sha256("\n".join(normalized).encode()).hexdigest()


class ImportMappingRequest(BaseModel):
    schema_name: ImportSchema
    name: str = Field(min_length=1, max_length=60)
    column_map: dict[str, str] = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def _targets_fit_the_schema(self) -> "ImportMappingRequest":
        fields, required = IMPORT_FIELDS[self.schema_name]
        targets = list(self.column_map.values())
        unknown = [target for target in targets if target not in fields]
        if unknown:
            raise ValueError(f"unknown_target_field:{unknown[0]}")
        duplicates = sorted({t for t in targets if targets.count(t) > 1})
        if duplicates:
            raise ValueError(f"duplicate_target_field:{duplicates[0]}")
        missing = sorted(required - set(targets))
        if missing:
            raise ValueError(f"missing_required_field:{missing[0]}")
        return self


class ImportMappingMatchRequest(BaseModel):
    schema_name: ImportSchema
    headers: list[str] = Field(min_length=1, max_length=40)


class ImportMappingsResponse(BaseModel):
    data_mode: DataMode
    mappings: list[ImportMapping]


class ImportMappingResponse(BaseModel):
    data_mode: DataMode
    mapping: ImportMapping


class AlertRule(BaseModel):
    id: str
    metric: AlertMetric
    operator: Literal["above", "below"]
    threshold: Decimal
    recipients: list[JobFunction]
    channel: Literal["in_app", "email", "telegram"]
    enabled: bool


class AlertRuleRequest(BaseModel):
    metric: AlertMetric
    operator: Literal["above", "below"]
    threshold: Decimal = Field(ge=0)
    recipients: list[JobFunction] = Field(min_length=1, max_length=11)
    channel: Literal["in_app", "email", "telegram"]


class AlertRulesResponse(BaseModel):
    data_mode: DataMode
    rules: list[AlertRule]


class AlertRuleResponse(BaseModel):
    data_mode: DataMode
    rule: AlertRule
