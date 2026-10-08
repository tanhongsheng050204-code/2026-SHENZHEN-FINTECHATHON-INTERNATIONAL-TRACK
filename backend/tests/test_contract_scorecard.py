from decimal import Decimal

from app.routes.financing import router
from app.schemas import UserRole
from app.stubs import financing as stub
from tests.contract_support import client_for


def test_demo_company_scores_695_grade_b_with_every_point_explained():
    body = client_for(router).get("/financing/scorecard").json()

    assert body["data_mode"] == "stub"
    assert (body["score"], body["grade"], body["min_score"], body["max_score"]) == (
        695,
        "B",
        300,
        800,
    )
    assert body["base_points"] + sum(f["points"] for f in body["factors"]) == body["score"]
    assert [f["key"] for f in body["factors"]] == [
        "validated_einvoice_share",
        "receivables_over_90_share",
        "months_trading",
        "cash_runway",
        "top_customer_share",
        "bank_lines_matched_share",
        "public_reputation",
    ]
    runway = next(f for f in body["factors"] if f["key"] == "cash_runway")
    assert (runway["points"], runway["max_points"]) == (20, 80)
    assert runway["value"] == "Shortfall on day 23"
    assert runway["evidence"][0]["source"] == "cashflow:forecast"
    assert body["method"] == "expert_weights"


def test_points_follow_the_published_bins():
    assert stub.factor_points("validated_einvoice_share", Decimal("0.70")) == 90
    assert stub.factor_points("validated_einvoice_share", Decimal("0.69")) == 60
    assert stub.factor_points("receivables_over_90_share", Decimal("0.10")) == 80
    assert stub.factor_points("receivables_over_90_share", Decimal("0.36")) == 0
    assert stub.factor_points("months_trading", Decimal("48")) == 70
    assert stub.factor_points("months_trading", Decimal("11")) == 0
    assert stub.factor_points("top_customer_share", Decimal("0.51")) == 0
    assert stub.factor_points("bank_lines_matched_share", Decimal("0.74")) == 10


def test_runway_points_depend_on_when_cash_falls_short():
    assert stub.runway_points(None) == 80
    assert stub.runway_points(75) == 60
    assert stub.runway_points(45) == 40
    assert stub.runway_points(23) == 20


def test_a_falling_public_rating_costs_points_without_moving_cash():
    steady = stub.reputation_points(Decimal("4.4"), Decimal("4.5"))
    slipping = stub.reputation_points(Decimal("4.1"), Decimal("4.4"))
    collapsing = stub.reputation_points(Decimal("3.5"), Decimal("4.3"))

    assert (steady, slipping, collapsing) == (50, 30, 0)


def test_public_signals_are_labelled_and_sourced():
    body = client_for(router).get("/financing/scorecard").json()

    sources = [s["source"] for s in body["public_signals"]]
    assert sources == ["google_maps", "shopee"]
    assert all(s["synthetic"] is True for s in body["public_signals"])
    assert all(s["status"] in {"ok", "watch", "risk"} for s in body["public_signals"])
    assert "official" in body["public_data_note"]


def test_grades_cover_the_whole_range():
    assert [stub.grade_for(s) for s in (800, 720, 719, 650, 649, 580, 579, 500, 499, 300)] == [
        "A",
        "A",
        "B",
        "B",
        "C",
        "C",
        "D",
        "D",
        "E",
        "E",
    ]


def test_only_finance_owner_and_compliance_see_the_scorecard():
    employee = client_for(router, role=UserRole.GENERAL_EMPLOYEE).get("/financing/scorecard")
    compliance = client_for(router, role=UserRole.COMPLIANCE).get("/financing/scorecard")

    assert employee.status_code == 403
    assert compliance.status_code == 200
