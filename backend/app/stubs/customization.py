"""Stub message templates, import column mappings and custom alert rules.

Workstream B1 replaces templates and alert rules (message_templates, alert_rules);
workstream B3 replaces import mappings (import_mappings) as part of the importers.
Nothing is stored; created records are echoed back.
"""

import hashlib
from decimal import Decimal

from app.contracts.common import JobFunction
from app.contracts.customization import (
    AlertRule,
    AlertRuleRequest,
    ImportMapping,
    ImportMappingMatchRequest,
    ImportMappingRequest,
    MessageTemplate,
    MessageTemplateRequest,
    header_fingerprint,
    placeholders_in,
)


class CustomizationError(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _template(
    template_id: str, language: str, tone: str, body: str, status: str
) -> MessageTemplate:
    return MessageTemplate(
        id=template_id,
        kind="payment_reminder",
        language=language,
        tone=tone,
        body=body,
        placeholders=placeholders_in(body),
        status=status,
    )


_TEMPLATES: tuple[MessageTemplate, ...] = (
    _template(
        "tpl_reminder_en_formal",
        "en",
        "formal",
        "Dear {customer_name}, invoice {invoice_no} for {amount} was due on {due_date}. "
        "Could you confirm the payment date? {sender_name}, {company_name}",
        "approved",
    ),
    _template(
        "tpl_reminder_ms_formal",
        "ms",
        "formal",
        "Tuan/Puan {customer_name}, invois {invoice_no} berjumlah {amount} telah tamat tempoh "
        "pada {due_date}. Mohon sahkan tarikh pembayaran. {sender_name}, {company_name}",
        "approved",
    ),
    _template(
        "tpl_reminder_zh_friendly",
        "zh",
        "friendly",
        "{customer_name} 您好，发票 {invoice_no}（{amount}）已于 {due_date} 到期，"
        "请问预计何时付款？{sender_name}，{company_name}",
        "draft",
    ),
)

# "Tarikh Nilai" (value date) is in the file but not mapped; it still counts for matching.
_MAYBANK = ImportMapping(
    id="map_maybank_csv",
    schema_name="bank_statement_v1",
    name="Maybank CSV",
    column_map={
        "Tarikh": "date",
        "Keterangan": "description",
        "Debit": "debit",
        "Kredit": "credit",
        "Baki": "balance",
    },
    header_fingerprint=header_fingerprint(
        ["Tarikh", "Tarikh Nilai", "Keterangan", "Debit", "Kredit", "Baki"]
    ),
)

_RULES: tuple[AlertRule, ...] = (
    AlertRule(
        id="rule_overdue_customer",
        metric="overdue_amount_per_customer",
        operator="above",
        threshold=Decimal("10000.00"),
        recipients=[JobFunction.SALES, JobFunction.FINANCE],
        channel="in_app",
        enabled=True,
    ),
    AlertRule(
        id="rule_stock_below_reorder",
        metric="stock_below_reorder",
        operator="above",
        threshold=Decimal("0.00"),
        recipients=[JobFunction.LOGISTICS, JobFunction.PROCUREMENT],
        channel="in_app",
        enabled=True,
    ),
)


def _short_hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:8]


def templates() -> list[MessageTemplate]:
    return list(_TEMPLATES)


def create_template(request: MessageTemplateRequest) -> MessageTemplate:
    return MessageTemplate(
        id=f"tpl_{request.kind}_{request.language}_{_short_hash(request.body)}",
        kind=request.kind,
        language=request.language,
        tone=request.tone,
        body=request.body,
        placeholders=placeholders_in(request.body),
        status="draft",
    )


def approve_template(template_id: str) -> MessageTemplate:
    template = next((t for t in _TEMPLATES if t.id == template_id), None)
    if template is None:
        raise CustomizationError("template_not_found", 404)
    return template.model_copy(update={"status": "approved"})


def mappings() -> list[ImportMapping]:
    return [_MAYBANK]


def create_mapping(request: ImportMappingRequest) -> ImportMapping:
    fingerprint = header_fingerprint(request.headers)
    return ImportMapping(
        id=f"map_{request.schema_name}_{fingerprint[:8]}",
        schema_name=request.schema_name,
        name=request.name,
        column_map=request.column_map,
        header_fingerprint=fingerprint,
    )


def match_mapping(request: ImportMappingMatchRequest) -> ImportMapping:
    fingerprint = header_fingerprint(request.headers)
    for mapping in mappings():
        if (mapping.schema_name, mapping.header_fingerprint) == (
            request.schema_name,
            fingerprint,
        ):
            return mapping
    raise CustomizationError("no_matching_mapping", 404)


def rules() -> list[AlertRule]:
    return list(_RULES)


def create_rule(request: AlertRuleRequest) -> AlertRule:
    return AlertRule(
        id=f"rule_{request.metric}_{_short_hash(request.operator, str(request.threshold))}",
        metric=request.metric,
        operator=request.operator,
        threshold=request.threshold,
        recipients=list(dict.fromkeys(request.recipients)),
        channel=request.channel,
        enabled=True,
    )
