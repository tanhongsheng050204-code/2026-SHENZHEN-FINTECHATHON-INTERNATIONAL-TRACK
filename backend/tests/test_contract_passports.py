from app.contracts.passports import AuditPack, Passport, audit_pack_digest, passport_digest
from app.routes.passports import router
from app.schemas import UserRole
from tests.contract_support import client_for


def _issued() -> dict:
    return client_for(router).post("/passports").json()["passport"]


def test_issued_passport_hash_can_be_recomputed_by_anyone():
    document = _issued()

    assert document["sha256"] == passport_digest(Passport.model_validate(document))
    assert document["anchor"]["repository_path"] == "audit-anchors/2026-10-14.json"
    assert document["anchor"]["commit"] is None


def test_untouched_document_verifies():
    response = client_for(router, role=None).post("/lender/verify", json=_issued())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "verified"
    assert body["mismatched_fields"] == []
    assert body["computed_sha256"] == body["expected_sha256"]


def test_one_changed_figure_fails_and_is_named():
    document = _issued()
    revenue = next(m for m in document["metrics"] if m["key"] == "annual_revenue")
    revenue["value"] = "RM3.5M–4M"

    body = client_for(router, role=None).post("/lender/verify", json=document).json()

    assert body["status"] == "mismatch"
    assert body["mismatched_fields"] == ["annual_revenue"]
    assert body["computed_sha256"] != body["expected_sha256"]


def test_removed_and_added_metrics_are_both_reported():
    document = _issued()
    document["metrics"] = [m for m in document["metrics"] if m["key"] != "receivables_quality"]
    document["metrics"].append(
        {"key": "credit_rating", "label": "Credit rating", "value": "AAA", "evidence": []}
    )

    body = client_for(router, role=None).post("/lender/verify", json=document).json()

    assert body["status"] == "mismatch"
    assert body["mismatched_fields"] == ["credit_rating", "receivables_quality"]


def test_documents_with_content_that_was_never_issued_are_rejected():
    client = client_for(router, role=None)
    added_field = {**_issued(), "approved_credit_limit": "RM5,000,000.00"}
    added_in_metric = _issued()
    added_in_metric["metrics"][0]["note"] = "Pre-approved"

    top_level = client.post("/lender/verify", json=added_field)
    nested = client.post("/lender/verify", json=added_in_metric)

    assert top_level.status_code == 422
    assert "approved_credit_limit" in top_level.text
    assert nested.status_code == 422
    assert "note" in nested.text


def test_lists_show_passports_audit_packs_and_their_grants():
    owner = client_for(router)

    passports = owner.get("/passports").json()["passports"]
    packs = owner.get("/audit-packs").json()["packs"]
    lender_grants = owner.get("/passports/pp_demo_1/grants").json()["grants"]
    auditor_grants = owner.get("/audit-packs/ap_demo_2026/grants").json()["grants"]
    unknown = owner.get("/passports/pp_other/grants")

    assert [p["id"] for p in passports] == ["pp_demo_1"]
    assert [p["id"] for p in packs] == ["ap_demo_2026"]
    assert [(g["kind"], g["status"]) for g in lender_grants] == [("lender", "active")]
    assert [(g["kind"], g["status"]) for g in auditor_grants] == [("auditor", "active")]
    assert (unknown.status_code, unknown.json()["detail"]) == (404, "passport_not_found")


def test_readers_find_passports_but_only_the_owner_lists_grants():
    compliance = client_for(router, role=UserRole.COMPLIANCE)

    assert compliance.get("/passports").status_code == 200
    assert compliance.get("/audit-packs").status_code == 200
    assert compliance.get("/passports/pp_demo_1/grants").status_code == 403
    assert client_for(router, role=UserRole.GENERAL_EMPLOYEE).get("/passports").status_code == 403


def test_unknown_passport_id_is_reported_not_verified():
    document = {**_issued(), "id": "pp_other"}

    body = client_for(router, role=None).post("/lender/verify", json=document).json()

    assert body["status"] == "unknown_passport"
    assert body["expected_sha256"] is None


def test_owner_grants_lender_access_without_echoing_the_email():
    response = client_for(router).post(
        "/passports/pp_demo_1/grants",
        json={"grantee_email": "credit@lender.example", "expires_in_days": 7},
    )

    assert response.status_code == 200
    grant = response.json()["grant"]
    assert (grant["kind"], grant["scope"], grant["status"]) == (
        "lender",
        "passport:pp_demo_1",
        "active",
    )
    assert grant["grantee_email_token"].startswith("EMAIL_")
    assert "credit@lender.example" not in response.text


def test_grant_validation_and_revocation():
    client = client_for(router)

    too_long = client.post(
        "/passports/pp_demo_1/grants",
        json={"grantee_email": "credit@lender.example", "expires_in_days": 31},
    )
    bad_email = client.post(
        "/passports/pp_demo_1/grants", json={"grantee_email": "nope", "expires_in_days": 7}
    )
    revoked = client.delete("/passports/pp_demo_1/grants/grant_demo_lender")
    unknown = client.delete("/passports/pp_demo_1/grants/grant_other")

    assert too_long.status_code == 422
    assert bad_email.status_code == 422
    assert revoked.json()["grant"]["status"] == "revoked"
    assert unknown.status_code == 404


def test_shared_links_need_a_valid_token():
    client = client_for(router, role=None)

    lender = client.get("/lender/passports/demo-grant-token")
    auditor = client.get("/auditor/packs/demo-audit-token")
    guessed_lender = client.get("/lender/passports/guess")
    guessed_auditor = client.get("/auditor/packs/guess")

    assert lender.status_code == 200
    assert auditor.status_code == 200
    assert guessed_lender.json() == guessed_auditor.json() == {"detail": "grant_not_found"}


def test_finance_prepares_an_audit_pack_that_withholds_employee_lines():
    response = client_for(router, role=UserRole.FINANCE_OPS).post(
        "/audit-packs", json={"period": "2026"}
    )

    assert response.status_code == 200
    pack = response.json()["pack"]
    assert pack["sha256"] == audit_pack_digest(AuditPack.model_validate(pack))
    assert [item["key"] for item in pack["items"]] == [
        "ledger_export",
        "einvoice_register",
        "reconciliation_status",
        "audit_chain_proof",
        "payroll_summary",
    ]
    payroll = pack["items"][-1]
    assert "per-employee lines withheld" in payroll["description"]


def test_owner_shares_the_audit_pack_with_an_external_auditor():
    response = client_for(router).post(
        "/audit-packs/ap_demo_2026/grants",
        json={"grantee_email": "audit@firm.example", "expires_in_days": 14},
    )

    grant = response.json()["grant"]
    assert (grant["kind"], grant["scope"]) == ("auditor", "audit_pack:ap_demo_2026")
    assert grant["share_path"] == "/auditor/packs/demo-audit-token"
    assert "audit@firm.example" not in response.text


def test_audit_pack_validation_and_roles():
    owner = client_for(router)

    bad_period = owner.post("/audit-packs", json={"period": "last year"})
    unknown = owner.get("/audit-packs/ap_other")
    staff = client_for(router, role=UserRole.GENERAL_EMPLOYEE).post(
        "/audit-packs", json={"period": "2026"}
    )

    assert bad_period.status_code == 422
    assert (unknown.status_code, unknown.json()["detail"]) == (404, "audit_pack_not_found")
    assert staff.status_code == 403


def test_roles_for_issuing_and_reading_passports():
    assert client_for(router, role=UserRole.FINANCE_OPS).post("/passports").status_code == 403
    compliance = client_for(router, role=UserRole.COMPLIANCE)
    assert compliance.get("/passports/pp_demo_1").status_code == 200
    assert compliance.get("/passports/pp_other").status_code == 404
    assert client_for(router, role=None).get("/passports/pp_demo_1").status_code == 401
