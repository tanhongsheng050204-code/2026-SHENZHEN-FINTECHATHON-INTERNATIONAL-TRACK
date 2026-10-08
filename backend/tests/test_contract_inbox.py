from app.contracts.common import JobFunction
from app.routes.inbox import router
from app.schemas import UserRole
from tests.contract_support import (
    MARKETING_EXEC,
    OPERATIONS_MANAGER,
    PURCHASING_STORES,
    client_as,
    client_for,
)


def _ids(response) -> list[str]:
    return [action["id"] for action in response.json()["actions"]]


def test_owner_oversees_every_position():
    body = client_for(router).get("/review-inbox").json()

    assert body["job_functions"] == [job.value for job in JobFunction]
    assert len(body["actions"]) == 13


def test_one_person_holding_two_positions_gets_one_combined_inbox():
    response = client_for(router, role=UserRole.FINANCE_OPS).get("/review-inbox")

    assert response.json()["job_functions"] == ["finance", "hr"]
    assert _ids(response) == ["act_reminders", "act_bank_change", "act_payroll_run"]


def test_each_position_sees_its_own_items():
    sales = client_for(router, role=UserRole.GENERAL_EMPLOYEE).get("/review-inbox")
    stores = client_as(router, PURCHASING_STORES, UserRole.GENERAL_EMPLOYEE).get("/review-inbox")
    marketing = client_as(router, MARKETING_EXEC, UserRole.GENERAL_EMPLOYEE).get("/review-inbox")
    operations = client_as(router, OPERATIONS_MANAGER, UserRole.FINANCE_OPS).get("/review-inbox")
    compliance = client_for(router, role=UserRole.COMPLIANCE).get("/review-inbox")

    assert _ids(sales) == ["act_sales_followup", "act_cs_reply"]
    assert _ids(stores) == ["act_po_approval", "act_reorder"]
    assert _ids(marketing) == ["act_campaign"]
    assert _ids(operations) == ["act_stale_approvals"]
    assert _ids(compliance) == ["act_access_review"]


def test_inbox_filters_to_one_of_your_positions():
    client = client_for(router, role=UserRole.FINANCE_OPS)

    hr_only = client.get("/review-inbox", params={"job_function": "hr"})
    not_mine = client.get("/review-inbox", params={"job_function": "sales"})

    assert _ids(hr_only) == ["act_payroll_run"]
    assert (not_mine.status_code, not_mine.json()["detail"]) == (403, "not_your_job_function")


def test_finance_edits_a_draft():
    response = client_for(router, role=UserRole.FINANCE_OPS).post(
        "/review-inbox/act_reminders/decision",
        json={"decision": "edit", "edited_draft": "Dear Customer A, a gentle reminder."},
    )

    assert response.status_code == 200
    action = response.json()["action"]
    assert action["status"] == "edited"
    assert action["draft"] == "Dear Customer A, a gentle reminder."


def test_staff_decide_only_their_own_positions():
    sales = client_for(router, role=UserRole.GENERAL_EMPLOYEE)

    own = sales.post("/review-inbox/act_sales_followup/decision", json={"decision": "approve"})
    other = sales.post("/review-inbox/act_reorder/decision", json={"decision": "approve"})

    assert own.json()["action"]["status"] == "approved"
    assert (other.status_code, other.json()["detail"]) == (403, "not_your_job_function")


def test_external_actions_need_the_owner():
    finance = client_for(router, role=UserRole.FINANCE_OPS).post(
        "/review-inbox/act_send_reminders/decision", json={"decision": "approve"}
    )
    owner = client_for(router).post(
        "/review-inbox/act_send_reminders/decision", json={"decision": "approve"}
    )

    assert (finance.status_code, finance.json()["detail"]) == (403, "owner_approval_required")
    assert owner.json()["action"]["status"] == "approved"


def test_money_movement_needs_two_approvers():
    client = client_for(router)

    bank = client.post("/review-inbox/act_bank_change/decision", json={"decision": "approve"})
    payroll = client.post("/review-inbox/act_payroll_run/decision", json={"decision": "approve"})

    assert (bank.status_code, bank.json()["detail"]) == (409, "maker_checker_required")
    assert (payroll.status_code, payroll.json()["detail"]) == (409, "maker_checker_required")


def test_edit_without_a_draft_and_unknown_actions_are_rejected():
    client = client_for(router)

    missing_draft = client.post("/review-inbox/act_reminders/decision", json={"decision": "edit"})
    unknown = client.post("/review-inbox/act_nothing/decision", json={"decision": "approve"})

    assert missing_draft.status_code == 422
    assert "edited_draft_required" in missing_draft.text
    assert (unknown.status_code, unknown.json()["detail"]) == (404, "action_not_found")
