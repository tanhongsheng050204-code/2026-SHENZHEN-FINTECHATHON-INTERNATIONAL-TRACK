from app.routes.settings import router
from app.schemas import UserRole
from tests.contract_support import client_for


def _current() -> dict:
    return client_for(router).get("/settings").json()["settings"]


def _change(area: str, value) -> object:
    return client_for(router).post("/settings/changes", json={"area": area, "value": value})


def test_settings_start_from_the_trading_template():
    body = client_for(router, role=UserRole.FINANCE_OPS).get("/settings").json()

    assert (body["data_mode"], body["version"], body["template"]) == ("stub", 3, "trading")
    settings = body["settings"]
    assert settings["alerts"]["minimum_cash_balance"] == "50000.00"
    production = next(p for p in settings["positions"] if p["job_function"] == "production")
    assert production["enabled"] is False


def test_schema_describes_every_customizable_area():
    body = client_for(router).get("/settings/schema").json()

    assert set(body["json_schema"]["properties"]) == {
        "profile",
        "positions",
        "approvals",
        "alerts",
        "financing",
        "security",
        "branding",
    }


def test_an_alert_change_applies_with_a_preview():
    alerts = {**_current()["alerts"], "minimum_cash_balance": "60000.00"}

    response = _change("alerts", alerts)

    assert response.status_code == 200
    change = response.json()["change"]
    assert (change["status"], change["version"], change["requires_approval"]) == (
        "applied",
        4,
        False,
    )
    assert change["preview"] == ['alerts.minimum_cash_balance: "50000.00" → "60000.00"']
    assert response.json()["settings"]["alerts"]["minimum_cash_balance"] == "60000.00"


def test_positions_can_be_renamed_in_any_order():
    positions = list(reversed(_current()["positions"]))
    finance = next(p for p in positions if p["job_function"] == "finance")
    finance["display_name"] = "Akauntan"

    response = _change("positions", positions)

    assert response.json()["change"]["preview"] == ["finance: renamed to Akauntan"]
    ordered = [p["job_function"] for p in response.json()["settings"]["positions"]]
    assert ordered[0] == "owner"


def test_security_changes_wait_for_compliance():
    security = {
        **_current()["security"],
        "mfa_required_roles": ["owner_director", "finance_ops", "compliance", "general_employee"],
    }

    proposed = _change("security", security).json()
    change_id = proposed["change"]["id"]
    owner_approves = client_for(router).post(f"/settings/changes/{change_id}/approve")
    compliance_approves = client_for(router, role=UserRole.COMPLIANCE).post(
        f"/settings/changes/{change_id}/approve"
    )

    assert proposed["change"]["status"] == "pending_approval"
    assert "general_employee" not in proposed["settings"]["security"]["mfa_required_roles"]
    assert owner_approves.status_code == 403
    assert compliance_approves.json()["change"]["status"] == "applied"


def test_only_pending_security_changes_can_be_approved():
    response = client_for(router, role=UserRole.COMPLIANCE).post(
        "/settings/changes/chg_alerts_12345678/approve"
    )

    assert (response.status_code, response.json()["detail"]) == (404, "change_not_found")


def test_safety_floors_cannot_be_crossed():
    current = _current()
    weaker_mfa = {**current["security"], "mfa_required_roles": ["owner_director"]}
    long_session = {**current["security"], "session_idle_minutes": 120}
    silent_alerts = {**current["alerts"], "critical_alerts_enabled": False}
    no_owner_alerts = {**current["alerts"], "recipients": ["finance"]}
    no_owner = [
        {**p, "enabled": False} if p["job_function"] == "owner" else p for p in current["positions"]
    ]

    assert "mfa_required_for_privileged_roles" in _change("security", weaker_mfa).text
    assert _change("security", long_session).status_code == 422
    assert _change("alerts", silent_alerts).status_code == 422
    assert "owner_must_receive_critical_alerts" in _change("alerts", no_owner_alerts).text
    assert "owner_position_required" in _change("positions", no_owner).text


def test_positions_must_list_every_position_once():
    positions = _current()["positions"][:-1]

    response = _change("positions", positions)

    assert response.status_code == 422
    assert "every_position_listed_once" in response.text


def test_a_change_that_changes_nothing_is_refused():
    response = _change("branding", _current()["branding"])

    assert (response.status_code, response.json()["detail"]) == (409, "no_changes")


def test_equivalent_submissions_are_not_changes():
    current = _current()
    numeric_money = {**current["alerts"], "minimum_cash_balance": 50000}
    reordered_recipients = {
        **current["alerts"],
        "recipients": list(reversed(current["alerts"]["recipients"])),
    }
    reordered_mfa = {
        **current["security"],
        "mfa_required_roles": list(reversed(current["security"]["mfa_required_roles"])),
    }

    for area, value in [
        ("alerts", numeric_money),
        ("alerts", reordered_recipients),
        ("security", reordered_mfa),
    ]:
        response = _change(area, value)
        assert (response.status_code, response.json()["detail"]) == (409, "no_changes"), value


def test_money_is_kept_with_two_decimals():
    response = _change("alerts", {**_current()["alerts"], "minimum_cash_balance": 60000})

    assert response.json()["settings"]["alerts"]["minimum_cash_balance"] == "60000.00"
    assert response.json()["change"]["preview"] == [
        'alerts.minimum_cash_balance: "50000.00" → "60000.00"'
    ]


def test_applying_the_current_template_is_refused():
    response = client_for(router).post("/settings/templates/trading/apply")

    assert (response.status_code, response.json()["detail"]) == (409, "no_changes")


def test_rollback_restores_an_earlier_version_as_a_new_version():
    client = client_for(router)

    restored = client.post("/settings/rollback", json={"version": 1}).json()
    current = client.post("/settings/rollback", json={"version": 3})
    unknown = client.post("/settings/rollback", json={"version": 9})

    assert (restored["change"]["status"], restored["change"]["version"]) == ("applied", 4)
    assert restored["change"]["area"] == "rollback"
    assert restored["change"]["preview"] == ['alerts.minimum_cash_balance: "50000.00" → "30000.00"']
    assert restored["settings"]["alerts"]["minimum_cash_balance"] == "30000.00"
    assert (current.status_code, current.json()["detail"]) == (409, "invalid_rollback_version")
    assert unknown.status_code == 409


def test_rolling_back_security_settings_waits_for_compliance():
    rollback = client_for(router).post("/settings/rollback", json={"version": 2}).json()
    change = rollback["change"]
    approved = client_for(router, role=UserRole.COMPLIANCE).post(
        f"/settings/changes/{change['id']}/approve"
    )

    assert (change["status"], change["requires_approval"]) == ("pending_approval", True)
    assert "security.session_idle_minutes: 30 → 45" in change["preview"]
    assert rollback["settings"]["security"]["session_idle_minutes"] == 30
    assert rollback["settings"]["alerts"]["minimum_cash_balance"] == "50000.00"
    assert approved.json()["change"]["status"] == "applied"


def test_compliance_finds_pending_changes_and_can_reject_them():
    compliance = client_for(router, role=UserRole.COMPLIANCE)

    everything = compliance.get("/settings/changes").json()["changes"]
    pending = compliance.get("/settings/changes", params={"status": "pending_approval"}).json()
    rejected = compliance.post(f"/settings/changes/{pending['changes'][0]['id']}/reject")
    already_applied = compliance.post("/settings/changes/chg_alerts_0003/reject")
    owner_rejects = client_for(router).post("/settings/changes/chg_security_demo/reject")
    unknown = compliance.post("/settings/changes/chg_nothing/reject")

    assert [c["version"] for c in everything] == [2, 2, 3, 3, 4]
    assert [c["id"] for c in pending["changes"]] == ["chg_security_demo"]
    assert rejected.json()["change"]["status"] == "rejected"
    assert (already_applied.status_code, already_applied.json()["detail"]) == (
        409,
        "change_not_pending",
    )
    assert owner_rejects.status_code == 403
    assert (unknown.status_code, unknown.json()["detail"]) == (404, "change_not_found")


def test_three_industry_templates():
    body = client_for(router).get("/settings/templates").json()

    templates = {t["id"]: t for t in body["templates"]}
    assert body["current"] == "trading"
    assert list(templates) == ["trading", "services", "manufacturing"]
    assert templates["trading"]["demo_data"] == "full"
    assert templates["manufacturing"]["designed_positions"] == ["production"]


def test_template_previews_show_what_changes_and_keep_data():
    client = client_for(router)

    manufacturing = client.post("/settings/templates/manufacturing/preview").json()
    services = client.post("/settings/templates/services/preview").json()
    unknown = client.post("/settings/templates/airline/preview")

    assert manufacturing["positions_added"] == ["production"]
    assert manufacturing["designed_positions"] == ["production"]
    assert manufacturing["data_kept"] is True
    assert services["positions_removed"] == ["procurement", "logistics"]
    assert unknown.status_code == 422


def test_applying_manufacturing_adds_the_production_position():
    body = client_for(router).post("/settings/templates/manufacturing/apply").json()

    assert body["settings"]["profile"]["industry"] == "manufacturing"
    production = next(p for p in body["settings"]["positions"] if p["job_function"] == "production")
    assert production["enabled"] is True
    assert body["change"]["preview"] == ["production: enabled"]


def test_roles_for_settings():
    finance = client_for(router, role=UserRole.FINANCE_OPS)
    employee = client_for(router, role=UserRole.GENERAL_EMPLOYEE)

    assert (
        finance.post("/settings/changes", json={"area": "branding", "value": {}}).status_code == 403
    )
    assert employee.get("/settings").status_code == 403
