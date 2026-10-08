from fastapi import APIRouter, Depends

from app.auth.dependencies import require_roles
from app.contracts.common import AutonomyLevel, JobFunction, OwaspAgenticRisk, autonomy_rank
from app.schemas import UserRole
from tests.contract_support import MARKETING_EXEC, client_as, client_for


def test_autonomy_levels_rank_in_ladder_order():
    ranks = [autonomy_rank(level) for level in AutonomyLevel]
    assert ranks == [0, 1, 2, 3]


def test_every_sme_position_is_a_job_function():
    assert [job.value for job in JobFunction] == [
        "owner",
        "operations",
        "finance",
        "sales",
        "customer_service",
        "marketing",
        "procurement",
        "logistics",
        "production",
        "hr",
        "compliance",
    ]


def test_owasp_agentic_risks_cover_all_ten():
    assert [risk.value for risk in OwaspAgenticRisk] == [f"ASI{n:02d}" for n in range(1, 11)]


def test_clients_apply_roles_and_reject_anonymous_requests():
    router = APIRouter()

    @router.get("/owner-only")
    def owner_only(_=Depends(require_roles(UserRole.OWNER_DIRECTOR))) -> dict[str, str]:
        return {"ok": "yes"}

    assert client_for(router).get("/owner-only").status_code == 200
    assert client_for(router, role=UserRole.FINANCE_OPS).get("/owner-only").status_code == 403
    assert client_for(router, role=None).get("/owner-only").status_code == 401
    marketing = client_as(router, MARKETING_EXEC, UserRole.GENERAL_EMPLOYEE)
    assert marketing.get("/owner-only").status_code == 403
