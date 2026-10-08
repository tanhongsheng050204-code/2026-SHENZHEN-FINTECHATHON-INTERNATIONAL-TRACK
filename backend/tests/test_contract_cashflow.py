from decimal import Decimal

from app.routes.cashflow import router
from app.schemas import UserRole
from tests.contract_support import client_for

AS_OF = "2026-10-08"


def _scenario(shifts: list[dict], horizon_days: int = 90) -> dict:
    return (
        client_for(router)
        .post(
            "/cashflow/scenarios",
            json={"as_of": AS_OF, "horizon_days": horizon_days, "shifts": shifts},
        )
        .json()
    )


def test_forecast_finds_the_demo_shortfall_on_day_23():
    response = client_for(router).get(
        "/cashflow/forecast", params={"horizon_days": 90, "as_of": AS_OF}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data_mode"] == "stub"
    assert len(body["points"]) == 91
    assert body["shortfall"] == {
        "day": 23,
        "date": "2026-10-31",
        "likely_balance": "20560.00",
        "minimum_balance": "50000.00",
        "gap": "29440.00",
    }
    day_23 = body["points"][23]
    assert (day_23["best"], day_23["likely"], day_23["worst"]) == (
        "51560.00",
        "20560.00",
        "-22140.00",
    )
    assert body["alerts"][0]["severity"] == "critical"
    assert body["alerts"][0]["day"] == 23
    assert "Payroll (RM62,000.00)" in body["alerts"][0]["detail"]


def test_bands_are_ordered_on_every_day():
    body = client_for(router).get("/cashflow/forecast", params={"as_of": AS_OF}).json()

    for point in body["points"]:
        assert Decimal(point["best"]) >= Decimal(point["likely"]) >= Decimal(point["worst"])


def test_horizon_limits_points_and_drivers():
    body = (
        client_for(router)
        .get("/cashflow/forecast", params={"horizon_days": 30, "as_of": AS_OF})
        .json()
    )

    assert len(body["points"]) == 31
    assert [driver["id"] for driver in body["drivers"]] == [
        "R1",
        "P1",
        "R2",
        "CS1",
        "R3",
        "P2",
        "P3",
        "MK1",
        "R4",
    ]
    rmb_payment = next(driver for driver in body["drivers"] if driver["id"] == "P3")
    assert rmb_payment["source_agent"] == "purchasing"
    assert rmb_payment["source_currency"] == "CNY"
    assert rmb_payment["source_amount"] == "98000.00"


def test_unknown_horizon_is_rejected():
    response = client_for(router).get("/cashflow/forecast", params={"horizon_days": 45})

    assert response.status_code == 422
    assert response.json()["detail"] == "invalid_horizon"


def test_scenario_delaying_customer_a_pushes_day_23_below_zero():
    shortfall = _scenario([{"event_id": "R1", "shift_days": 30}])["shortfall"]

    assert shortfall["day"] == 23
    assert shortfall["likely_balance"] == "-3940.00"
    assert shortfall["gap"] == "53940.00"


def test_repeated_shifts_for_one_event_add_up():
    once = _scenario([{"event_id": "R1", "shift_days": 30}])
    twice = _scenario([{"event_id": "R1", "shift_days": 15}, {"event_id": "R1", "shift_days": 15}])

    assert twice["points"] == once["points"]


def test_shift_before_today_lands_on_day_zero():
    body = _scenario([{"event_id": "R1", "shift_days": -90}])

    assert body["points"][0]["best"] == "140900.00"
    assert body["drivers"][0]["id"] == "R1"
    assert body["drivers"][0]["best_day"] == 0


def test_shortfall_beyond_the_horizon_is_not_reported():
    body = _scenario(
        [{"event_id": "P2", "shift_days": 40}, {"event_id": "P3", "shift_days": 40}],
        horizon_days=30,
    )

    assert body["shortfall"] is None
    assert body["alerts"] == []


def test_risk_signals_never_move_the_balance():
    baseline = client_for(router).get("/cashflow/forecast", params={"as_of": AS_OF}).json()
    moved = _scenario([{"event_id": "CS1", "shift_days": 100}])

    assert moved["points"] == baseline["points"]


def test_scenario_rejects_unknown_event():
    response = client_for(router).post(
        "/cashflow/scenarios", json={"shifts": [{"event_id": "R99", "shift_days": 5}]}
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "unknown_event:R99"


def test_scenario_rejects_unsupported_horizon():
    response = client_for(router).post("/cashflow/scenarios", json={"horizon_days": 45})

    assert response.status_code == 422


def test_every_position_feeds_the_cash_signals():
    body = client_for(router).get("/cashflow/signals").json()

    totals = {total["agent_id"]: total for total in body["by_agent"]}
    assert list(totals) == [
        "payables",
        "receivables",
        "sales",
        "customer_service",
        "marketing",
        "purchasing",
        "inventory",
        "hr_payroll",
    ]
    assert totals["receivables"]["inflow_total"] == "353500.00"
    assert totals["purchasing"]["outflow_total"] == "99540.00"
    assert totals["hr_payroll"]["outflow_total"] == "186000.00"
    assert totals["customer_service"]["at_risk_total"] == "31000.00"


def test_signals_filter_by_position():
    body = (
        client_for(router).get("/cashflow/signals", params={"job_function": "procurement"}).json()
    )

    assert [signal["id"] for signal in body["signals"]] == ["P3", "PO2"]
    assert [total["agent_id"] for total in body["by_agent"]] == ["purchasing"]


def test_signals_reject_unknown_positions_and_horizons():
    client = client_for(router)

    assert client.get("/cashflow/signals", params={"job_function": "pilot"}).status_code == 422
    assert client.get("/cashflow/signals", params={"horizon_days": 45}).status_code == 422


def test_general_employee_cannot_read_forecast():
    response = client_for(router, role=UserRole.GENERAL_EMPLOYEE).get("/cashflow/forecast")

    assert response.status_code == 403


def test_compliance_can_read_but_not_run_scenarios():
    client = client_for(router, role=UserRole.COMPLIANCE)

    assert client.get("/cashflow/forecast").status_code == 200
    assert client.post("/cashflow/scenarios", json={}).status_code == 403


def test_unauthenticated_request_is_rejected():
    response = client_for(router, role=None).get("/cashflow/forecast")

    assert response.status_code == 401
