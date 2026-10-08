from app.routes.customization import router
from app.schemas import UserRole
from tests.contract_support import client_for

REMINDER = {
    "kind": "payment_reminder",
    "language": "en",
    "tone": "friendly",
    "body": "Hi {customer_name}, a quick reminder about {invoice_no} for {amount}.",
}
PAYABLES_MAP = {
    "Bill": "bill_id",
    "Vendor": "supplier",
    "Total": "amount",
    "Ccy": "currency",
    "Due": "due_date",
}


def test_templates_in_three_languages():
    templates = client_for(router).get("/settings/message-templates").json()["templates"]

    assert [t["language"] for t in templates] == ["en", "ms", "zh"]
    assert [t["status"] for t in templates] == ["approved", "approved", "draft"]
    assert templates[0]["placeholders"] == [
        "customer_name",
        "invoice_no",
        "amount",
        "due_date",
        "sender_name",
        "company_name",
    ]


def test_finance_drafts_a_template_and_the_owner_approves():
    finance = client_for(router, role=UserRole.FINANCE_OPS)

    created = finance.post("/settings/message-templates", json=REMINDER).json()["template"]
    finance_approves = finance.post("/settings/message-templates/tpl_reminder_zh_friendly/approve")
    owner_approves = client_for(router).post(
        "/settings/message-templates/tpl_reminder_zh_friendly/approve"
    )

    assert (created["status"], created["placeholders"]) == (
        "draft",
        ["customer_name", "invoice_no", "amount"],
    )
    assert finance_approves.status_code == 403
    assert owner_approves.json()["template"]["status"] == "approved"


def test_templates_reject_unknown_placeholders_and_personal_data():
    client = client_for(router)

    unknown = client.post(
        "/settings/message-templates", json={**REMINDER, "body": "Pay to {iban} today please."}
    )
    email = client.post(
        "/settings/message-templates",
        json={**REMINDER, "body": "Reply to boss@company.example about {invoice_no}."},
    )
    phone = client.post(
        "/settings/message-templates",
        json={**REMINDER, "body": "Call 0123456789 about {invoice_no} soon."},
    )
    missing = client.post("/settings/message-templates/tpl_nothing/approve")

    assert "unknown_placeholder:iban" in unknown.text
    assert email.status_code == phone.status_code == 422
    assert "personal_data_in_template" in email.text
    assert (missing.status_code, missing.json()["detail"]) == (404, "template_not_found")


def test_a_saved_mapping_matches_the_same_headers_in_any_order_or_case():
    response = client_for(router, role=UserRole.FINANCE_OPS).post(
        "/settings/import-mappings/match",
        json={
            "schema_name": "bank_statement_v1",
            "headers": ["baki", "TARIKH", "Kredit", "Debit", "Keterangan"],
        },
    )

    assert response.status_code == 200
    assert response.json()["mapping"]["name"] == "Maybank CSV"


def test_unknown_headers_need_a_new_mapping():
    response = client_for(router).post(
        "/settings/import-mappings/match",
        json={"schema_name": "bank_statement_v1", "headers": ["Date", "Amount"]},
    )

    assert (response.status_code, response.json()["detail"]) == (404, "no_matching_mapping")


def test_finance_saves_a_new_mapping():
    response = client_for(router, role=UserRole.FINANCE_OPS).post(
        "/settings/import-mappings",
        json={
            "schema_name": "payables_register_v1",
            "name": "Supplier sheet",
            "column_map": PAYABLES_MAP,
        },
    )

    mapping = response.json()["mapping"]
    assert mapping["schema_name"] == "payables_register_v1"
    assert len(mapping["header_fingerprint"]) == 64


def test_mappings_must_fit_the_target_schema():
    client = client_for(router)

    def create(column_map: dict) -> str:
        return client.post(
            "/settings/import-mappings",
            json={"schema_name": "payables_register_v1", "name": "x", "column_map": column_map},
        ).text

    assert "unknown_target_field:iban" in create({**PAYABLES_MAP, "Iban": "iban"})
    assert "duplicate_target_field:amount" in create({**PAYABLES_MAP, "Gross": "amount"})
    missing = {k: v for k, v in PAYABLES_MAP.items() if v != "due_date"}
    assert "missing_required_field:due_date" in create(missing)


def test_alert_rules_use_fixed_measures():
    client = client_for(router)

    listed = client.get("/settings/alert-rules").json()["rules"]
    created = client.post(
        "/settings/alert-rules",
        json={
            "metric": "open_disputes",
            "operator": "above",
            "threshold": "2",
            "recipients": ["customer_service", "customer_service", "finance"],
            "channel": "email",
        },
    )
    unknown_metric = client.post(
        "/settings/alert-rules",
        json={
            "metric": "weather",
            "operator": "above",
            "threshold": "1",
            "recipients": ["owner"],
            "channel": "email",
        },
    )

    assert [rule["id"] for rule in listed] == ["rule_overdue_customer", "rule_stock_below_reorder"]
    rule = created.json()["rule"]
    assert (rule["enabled"], rule["recipients"]) == (True, ["customer_service", "finance"])
    assert unknown_metric.status_code == 422


def test_roles_for_customization_records():
    finance = client_for(router, role=UserRole.FINANCE_OPS)
    compliance = client_for(router, role=UserRole.COMPLIANCE)

    rule = finance.post(
        "/settings/alert-rules",
        json={
            "metric": "open_disputes",
            "operator": "above",
            "threshold": "1",
            "recipients": ["owner"],
            "channel": "email",
        },
    )

    assert rule.status_code == 403
    assert compliance.get("/settings/import-mappings").status_code == 403
    assert compliance.get("/settings/alert-rules").status_code == 200
