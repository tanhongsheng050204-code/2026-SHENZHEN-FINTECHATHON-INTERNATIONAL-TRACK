from app.contracts.common import JobFunction
from app.routes.positions import router
from app.schemas import UserRole
from tests.contract_support import PURCHASING_STORES, client_as, client_for


def test_owner_sees_every_position_with_production_disabled():
    positions = client_for(router).get("/positions").json()["positions"]

    assert [p["job_function"] for p in positions] == [job.value for job in JobFunction]
    production = next(p for p in positions if p["job_function"] == "production")
    assert (production["enabled"], production["build_status"]) == (False, "designed")
    assert all(p["enabled"] for p in positions if p["job_function"] != "production")


def test_staff_see_only_their_positions():
    positions = (
        client_as(router, PURCHASING_STORES, UserRole.GENERAL_EMPLOYEE)
        .get("/positions")
        .json()["positions"]
    )

    assert [p["job_function"] for p in positions] == ["procurement", "logistics"]
    assert positions[0]["display_name"] == "Purchasing / Import"
    assert positions[0]["agent_ids"] == ["purchasing"]


def test_every_built_position_has_a_working_skill_and_its_cash_contribution():
    client = client_for(router)

    for job in JobFunction:
        if job == JobFunction.PRODUCTION:
            continue
        workspace = client.get(f"/positions/{job.value}/workspace").json()
        assert workspace["build_status"] == "built", job
        assert any(result["status"] != "planned" for result in workspace["skill_results"]), job
        assert workspace["cash_contribution"]["role"], job


def test_purchasing_workspace_shows_committed_rmb_outflows():
    workspace = (
        client_as(router, PURCHASING_STORES, UserRole.GENERAL_EMPLOYEE)
        .get("/positions/procurement/workspace")
        .json()
    )

    assert workspace["cash_contribution"]["outflow_total"] == "99540.00"
    assert workspace["cash_contribution"]["signal_ids"] == ["P3", "PO2"]
    assert workspace["inbox_count"] == 1
    assert [agent["id"] for agent in workspace["agents"]] == ["purchasing"]


def test_production_workspace_lists_planned_skills_only():
    workspace = client_for(router).get("/positions/production/workspace").json()

    assert workspace["build_status"] == "designed"
    assert workspace["skill_results"]
    assert all(result["status"] == "planned" for result in workspace["skill_results"])
    assert workspace["inbox_count"] == 0


def test_staff_cannot_open_other_positions_and_unknown_positions_fail():
    stores = client_as(router, PURCHASING_STORES, UserRole.GENERAL_EMPLOYEE)

    other = stores.get("/positions/hr/workspace")
    unknown = stores.get("/positions/pilot/workspace")

    assert (other.status_code, other.json()["detail"]) == (403, "not_your_job_function")
    assert unknown.status_code == 422
