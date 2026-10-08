from scripts.export_contract import CONTRACT_PATH, build_contract_app, render_contract

CONTRACT_OPERATIONS = {
    ("get", "/cashflow/forecast"),
    ("post", "/cashflow/scenarios"),
    ("get", "/cashflow/signals"),
    ("get", "/agents"),
    ("post", "/agents/runs"),
    ("get", "/agents/runs/{run_id}/events"),
    ("post", "/agents/{agent_id}/autonomy"),
    ("post", "/agents/kill-switch"),
    ("get", "/agents/journey"),
    ("get", "/review-inbox"),
    ("post", "/review-inbox/{action_id}/decision"),
    ("get", "/positions"),
    ("get", "/positions/{job_function}/workspace"),
    ("get", "/financing/matches"),
    ("post", "/financing/application-packs"),
    ("post", "/passports"),
    ("get", "/passports/{passport_id}"),
    ("post", "/passports/{passport_id}/grants"),
    ("delete", "/passports/{passport_id}/grants/{grant_id}"),
    ("post", "/lender/verify"),
    ("get", "/lender/passports/{grant_token}"),
    ("post", "/audit-packs"),
    ("get", "/audit-packs/{pack_id}"),
    ("post", "/audit-packs/{pack_id}/grants"),
    ("delete", "/audit-packs/{pack_id}/grants/{grant_id}"),
    ("get", "/auditor/packs/{grant_token}"),
    ("get", "/trust/posture"),
    ("get", "/trust/guardrail-events"),
    ("get", "/team/members"),
    ("post", "/team/invitations"),
    ("patch", "/team/members/{user_id}"),
    ("post", "/team/members/{user_id}/sign-out"),
    ("get", "/settings"),
    ("get", "/settings/schema"),
    ("post", "/settings/changes"),
    ("post", "/settings/changes/{change_id}/approve"),
    ("post", "/settings/rollback"),
    ("get", "/settings/templates"),
    ("post", "/settings/templates/{template_id}/preview"),
    ("post", "/settings/templates/{template_id}/apply"),
    ("get", "/settings/message-templates"),
    ("post", "/settings/message-templates"),
    ("post", "/settings/message-templates/{template_id}/approve"),
    ("get", "/settings/import-mappings"),
    ("post", "/settings/import-mappings"),
    ("post", "/settings/import-mappings/match"),
    ("get", "/settings/alert-rules"),
    ("post", "/settings/alert-rules"),
}
STREAMING_OPERATIONS = {("get", "/agents/runs/{run_id}/events")}


def _operations(document: dict) -> set[tuple[str, str]]:
    return {(method, path) for path, item in document["paths"].items() for method in item}


def test_contract_exposes_every_agreed_operation():
    assert _operations(build_contract_app().openapi()) == CONTRACT_OPERATIONS


def test_every_json_response_declares_its_data_mode():
    document = build_contract_app().openapi()
    schemas = document["components"]["schemas"]
    for method, path in CONTRACT_OPERATIONS - STREAMING_OPERATIONS:
        content = document["paths"][path][method]["responses"]["200"]["content"]
        name = content["application/json"]["schema"]["$ref"].rsplit("/", 1)[1]
        assert "data_mode" in schemas[name]["properties"], f"{method} {path}"


def test_run_events_are_documented_as_a_stream():
    document = build_contract_app().openapi()
    content = document["paths"]["/agents/runs/{run_id}/events"]["get"]["responses"]["200"]
    assert "text/event-stream" in content["content"]


def test_committed_contract_matches_the_code():
    assert CONTRACT_PATH.read_text(encoding="utf-8") == render_contract(), (
        "Run `uv run python -m scripts.export_contract` from backend/ and commit the result."
    )


def test_main_app_serves_the_contract():
    from app.main import app

    assert _operations(app.openapi()) >= CONTRACT_OPERATIONS
