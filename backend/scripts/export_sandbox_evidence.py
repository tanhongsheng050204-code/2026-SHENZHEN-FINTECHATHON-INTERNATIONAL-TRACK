"""Run the simulated-bank scenario offline and write its operation logs as evidence.

    uv run python -m scripts.export_sandbox_evidence <output dir>

Uses an in-memory SQLite company and the real review-inbox routes and sandbox
ledger: two-person approval of an L3 payment, the refusals around it, and the
company's hash-chained workflow audit log. No network, no real bank.
"""

import datetime as dt
import json
import sys
from decimal import Decimal
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import get_current_user
from app.auth.principal import AuthPrincipal
from app.contracts.common import AutonomyLevel, JobFunction
from app.db import get_db
from app.models import Base, Tenant, WorkflowAuditEntry
from app.routes.agents_live import router
from app.schemas import UserRole
from app.services import review_inbox, sandbox_bank
from app.services.workflow_audit import verify_workflow_chain

TENANT = "00000000-0000-4000-8000-00000000e001"
USERS = {
    UserRole.OWNER_DIRECTOR: "00000000-0000-4000-8000-0000000000a1",
    UserRole.FINANCE_OPS: "00000000-0000-4000-8000-0000000000b2",
    UserRole.GENERAL_EMPLOYEE: "00000000-0000-4000-8000-0000000000c3",
}
JOBS = {
    UserRole.OWNER_DIRECTOR: ("owner",),
    UserRole.FINANCE_OPS: ("finance", "hr"),
    UserRole.GENERAL_EMPLOYEE: ("sales",),
}
NAMES = {
    UserRole.OWNER_DIRECTOR: "Owner",
    UserRole.FINANCE_OPS: "Finance",
    UserRole.GENERAL_EMPLOYEE: "Employee",
}


def _client(db, role: UserRole) -> TestClient:
    principal = AuthPrincipal(
        user_id=USERS[role],
        email=None,
        role=role,
        tenant_id=TENANT,
        job_functions=JOBS[role],
        aal="aal2",
        mfa_verified_at=dt.datetime.now(dt.UTC),
    )
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: principal
    return TestClient(app)


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    db.add(Tenant(id=TENANT, slug="evidence-co", name="Synthetic evidence company"))
    db.commit()
    lines: list[str] = []

    def log(step: str, detail: str) -> None:
        lines.append(
            f"{dt.datetime.now(dt.UTC).isoformat(timespec='milliseconds')}  {step:<28} {detail}"
        )

    def propose(title: str, amount: str, level: AutonomyLevel) -> str:
        action_id = review_inbox.propose(
            db,
            TENANT,
            agent_id="payables",
            reviewer=JobFunction.FINANCE,
            title=title,
            summary=title,
            amount=Decimal(amount),
            level=level,
        )
        log(
            "agent proposes",
            f"{action_id} {level.value} RM{amount} -> review inbox (agent cannot execute)",
        )
        return action_id

    def decide(role: UserRole, action_id: str, decision: str) -> dict:
        response = _client(db, role).post(
            f"/review-inbox/{action_id}/decision", json={"decision": decision}
        )
        body = response.json()
        action = body.get("action") or {}
        outcome = action.get("status") or body.get("detail") or body
        ref = action.get("payment_reference")
        log(
            f"{NAMES[role]} {decision}s",
            f"{action_id} HTTP {response.status_code} -> {outcome}"
            + (f" ref={ref}" if ref else ""),
        )
        return body

    def ledger() -> list:
        return sandbox_bank.payments(db, TENANT)

    # 1. The normal path: maker, then a different checker, then exactly one payment.
    payroll = propose("October payroll run", "38400.00", AutonomyLevel.L3)
    decide(UserRole.GENERAL_EMPLOYEE, payroll, "approve")
    decide(UserRole.FINANCE_OPS, payroll, "approve")
    log("ledger after maker", f"{len(ledger())} payments (nothing runs on one approval)")
    decide(UserRole.FINANCE_OPS, payroll, "approve")
    log("ledger after same person", f"{len(ledger())} payments (maker cannot also be checker)")
    decide(UserRole.OWNER_DIRECTOR, payroll, "approve")
    first = sandbox_bank.execute_if_due(db, TENANT, payroll)
    log("simulated bank executes", f"{payroll} -> {first}")
    again = sandbox_bank.execute_if_due(db, TENANT, payroll)
    log(
        "simulated bank re-run",
        f"{payroll} -> {again} (same reference; ledger still {len(ledger())} payment)",
    )

    # 2. Nothing else moves money.
    rejected = propose("Pay supplier bill (rejected)", "14800.00", AutonomyLevel.L3)
    decide(UserRole.FINANCE_OPS, rejected, "reject")
    half = propose("Pay supplier bill (half approved)", "9200.00", AutonomyLevel.L3)
    decide(UserRole.FINANCE_OPS, half, "approve")
    reminder = propose("Send payment reminder", "0.00", AutonomyLevel.L2)
    decide(UserRole.OWNER_DIRECTOR, reminder, "approve")
    for action_id in (rejected, half, reminder):
        log(
            "simulated bank attempt",
            f"{action_id} -> {sandbox_bank.execute_if_due(db, TENANT, action_id)}",
        )
    log("final ledger", f"{len(ledger())} payment(s)")

    paid = [
        {
            "action_id": p.action_id,
            "amount": str(p.amount),
            "reference": p.reference,
            "executed_at": p.executed_at.isoformat(),
            "ledger": sandbox_bank.LEDGER,
        }
        for p in ledger()
    ]
    chain = [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat(),
            "event_type": r.event_type,
            "actor_role": r.actor_role,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "payload": r.event_payload,
            "prev_hash": r.prev_hash,
            "event_hash": r.event_hash,
        }
        for r in db.scalars(
            select(WorkflowAuditEntry)
            .where(WorkflowAuditEntry.tenant_id == TENANT)
            .order_by(WorkflowAuditEntry.id)
        )
    ]
    intact = verify_workflow_chain(db, TENANT)
    log("audit chain verified", f"{len(chain)} entries, intact={intact}")

    (out / "operations.log").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "sandbox-ledger.json").write_text(json.dumps(paid, indent=2) + "\n", encoding="utf-8")
    (out / "audit-chain.jsonl").write_text(
        "".join(json.dumps(e, default=str) + "\n" for e in chain), encoding="utf-8"
    )
    print("\n".join(lines))


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "output/sandbox-evidence"))
