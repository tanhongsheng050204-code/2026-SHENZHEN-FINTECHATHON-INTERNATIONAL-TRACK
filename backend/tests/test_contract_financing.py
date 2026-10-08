from app.routes.financing import router
from app.schemas import UserRole
from tests.contract_support import client_for


def test_malaysian_matches_list_eligible_products_first():
    body = client_for(router).get("/financing/matches").json()

    assert body["data_mode"] == "stub"
    assert body["jurisdiction"] == "MY"
    assert body["shortfall_gap"] == "29440.00"
    assert len(body["matches"]) == 8
    assert body["matches"][0]["product"]["id"] == "my_invoice_financing"
    assert body["matches"][0]["eligible"] is True
    eligibility = [match["eligible"] for match in body["matches"]]
    assert eligibility == sorted(eligibility, reverse=True)


def test_ineligible_product_explains_the_failing_rule():
    body = client_for(router).get("/financing/matches").json()

    term_loan = next(m for m in body["matches"] if m["product"]["id"] == "my_term_loan")
    failing = [rule for rule in term_loan["rules"] if not rule["passed"]]
    assert term_loan["eligible"] is False
    assert [rule["rule"] for rule in failing] == ["revenue_min"]
    assert failing[0]["detail"] == (
        "Annual revenue: RM2,640,000.00 (requires at least RM3,000,000.00)"
    )
    assert term_loan["explanation"].startswith("Not eligible: Annual revenue")


def test_every_rule_cites_evidence_and_terms_are_unverified():
    body = client_for(router).get("/financing/matches").json()

    for match in body["matches"]:
        assert match["rules"]
        assert all(rule["evidence"] for rule in match["rules"])
        assert match["product"]["last_verified"] is None
    assert "illustrative" in body["disclaimer"]


def test_china_pack_uses_its_own_catalogue():
    body = client_for(router).get("/financing/matches", params={"jurisdiction": "CN"}).json()

    assert {match["product"]["jurisdiction"] for match in body["matches"]} == {"CN"}
    assert len(body["matches"]) == 4


def test_unknown_jurisdiction_is_rejected():
    response = client_for(router).get("/financing/matches", params={"jurisdiction": "SG"})

    assert response.status_code == 422


def test_application_pack_is_an_l1_draft_for_the_owner():
    response = client_for(router, role=UserRole.FINANCE_OPS).post(
        "/financing/application-packs", json={"product_id": "my_invoice_financing"}
    )

    assert response.status_code == 200
    action = response.json()["action"]
    assert action["autonomy_level"] == "L1"
    assert action["reviewer_job_function"] == "owner"
    assert action["status"] == "pending"


def test_application_pack_refuses_ineligible_and_unknown_products():
    client = client_for(router)

    ineligible = client.post("/financing/application-packs", json={"product_id": "my_term_loan"})
    unknown = client.post("/financing/application-packs", json={"product_id": "nope"})

    assert (ineligible.status_code, ineligible.json()["detail"]) == (409, "product_not_eligible")
    assert (unknown.status_code, unknown.json()["detail"]) == (404, "product_not_found")


def test_general_employee_cannot_see_financing():
    response = client_for(router, role=UserRole.GENERAL_EMPLOYEE).get("/financing/matches")

    assert response.status_code == 403
