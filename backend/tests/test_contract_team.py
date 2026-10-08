from app.contracts.common import JobFunction
from app.routes.team import router
from app.schemas import UserRole
from tests.auth_support import USER_IDS
from tests.contract_support import client_for

OWNER_ID = str(USER_IDS[UserRole.OWNER_DIRECTOR])
FINANCE_ID = str(USER_IDS[UserRole.FINANCE_OPS])
SALES_ID = str(USER_IDS[UserRole.GENERAL_EMPLOYEE])


def test_team_covers_every_built_position_with_masked_emails():
    members = client_for(router).get("/team/members").json()["members"]

    assert len(members) == 7
    assert all("***@" in member["email_masked"] for member in members)
    held = {job for member in members for job in member["job_functions"]}
    assert held == {job.value for job in JobFunction} - {"production"}


def test_one_person_can_hold_several_positions():
    members = client_for(router).get("/team/members").json()["members"]

    clerk = next(member for member in members if member["user_id"] == FINANCE_ID)
    assert clerk["job_functions"] == ["finance", "hr"]


def test_invitation_masks_the_email_and_removes_duplicate_positions():
    response = client_for(router).post(
        "/team/invitations",
        json={
            "email": "new.clerk@example.com",
            "role": "finance_ops",
            "job_functions": ["finance", "finance", "hr"],
        },
    )

    assert response.status_code == 200
    member = response.json()["member"]
    assert member["email_masked"] == "n***@example.com"
    assert member["job_functions"] == ["finance", "hr"]
    assert member["active"] is False
    assert "new.clerk@example.com" not in response.text


def test_invitation_validation():
    client = client_for(router)

    bad_email = client.post(
        "/team/invitations",
        json={"email": "nope", "role": "finance_ops", "job_functions": ["finance"]},
    )
    no_position = client.post(
        "/team/invitations",
        json={"email": "a@example.com", "role": "finance_ops", "job_functions": []},
    )
    staff_owner = client.post(
        "/team/invitations",
        json={"email": "a@example.com", "role": "finance_ops", "job_functions": ["owner"]},
    )

    assert bad_email.status_code == 422
    assert no_position.status_code == 422
    assert staff_owner.status_code == 422
    assert "owner_function_requires_owner_role" in staff_owner.text


def test_owner_adds_a_position_to_a_member():
    response = client_for(router).patch(
        f"/team/members/{SALES_ID}",
        json={"job_functions": ["sales", "customer_service", "marketing"]},
    )

    assert response.status_code == 200
    assert response.json()["member"]["job_functions"] == ["sales", "customer_service", "marketing"]


def test_owner_cannot_lock_themselves_out():
    client = client_for(router)

    deactivate = client.patch(f"/team/members/{OWNER_ID}", json={"active": False})
    demote = client.patch(f"/team/members/{OWNER_ID}", json={"role": "finance_ops"})

    assert (deactivate.status_code, deactivate.json()["detail"]) == (409, "cannot_deactivate_self")
    assert (demote.status_code, demote.json()["detail"]) == (409, "last_owner_required")


def test_staff_cannot_take_the_owner_position():
    response = client_for(router).patch(
        f"/team/members/{FINANCE_ID}", json={"job_functions": ["owner"]}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "owner_function_requires_owner_role"


def test_empty_and_unknown_member_updates_are_rejected():
    client = client_for(router)

    empty = client.patch(f"/team/members/{SALES_ID}", json={})
    unknown = client.patch("/team/members/nobody", json={"active": False})

    assert empty.status_code == 422
    assert "no_changes" in empty.text
    assert (unknown.status_code, unknown.json()["detail"]) == (404, "member_not_found")


def test_sign_out_everywhere():
    response = client_for(router).post(f"/team/members/{SALES_ID}/sign-out")

    assert response.json()["sessions_revoked"] == 2


def test_compliance_reads_the_team_but_cannot_invite():
    client = client_for(router, role=UserRole.COMPLIANCE)

    assert client.get("/team/members").status_code == 200
    invited = client.post(
        "/team/invitations",
        json={"email": "x@example.com", "role": "finance_ops", "job_functions": ["finance"]},
    )
    assert invited.status_code == 403
