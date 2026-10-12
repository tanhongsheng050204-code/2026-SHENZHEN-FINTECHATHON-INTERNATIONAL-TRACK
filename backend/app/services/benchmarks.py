"""Benchmarks across companies, with differential privacy.

"How does my collection speed compare with other companies?" answered without any
company's own figure being revealed or worked out:

- Each company contributes one value per metric (its median days late on paid
  e-invoices), clipped to [0, CLIP_DAYS], so one company can move the average by
  at most CLIP_DAYS / n (the sensitivity).
- The released average gets Laplace noise with scale sensitivity / EPSILON: the
  Laplace mechanism, epsilon-differentially private for that release.
- One release per day. The first request of the day computes it and keeps it on
  the workflow chain of the platform's default company ("benchmark_released",
  figures only); every later request that day gets exactly that release, whatever
  changes in the data. So two answers can never be compared to cancel the noise,
  and asking again cannot average it away. The privacy cost is epsilon per metric
  per day, adding up over days (sequential composition). The first release of a
  day is taken under a database lock, so simultaneous first requests cannot each
  store one.
- Nothing is released below MIN_COMPANIES contributing companies.

The company's own value is shown exactly, to itself only. Reading other companies'
rows uses a worker session, and only the noisy average leaves this module.
"""

import datetime as dt
import hashlib
import hmac
import math
import statistics

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.contracts.insights import BenchmarkMetric, BenchmarksResponse
from app.models import DEFAULT_TENANT_ID, EInvoiceRecord, WorkflowAuditEntry
from app.services.workflow_audit import write_workflow_event

RELEASED = "benchmark_released"

EPSILON = 1.0
CLIP_DAYS = 90
MIN_COMPANIES = 5


def laplace(scale: float, seed: str) -> float:
    """A Laplace(0, scale) draw from a keyed hash of the seed (inverse CDF)."""
    secret = get_settings().token_root_secret.encode()
    digest = hmac.new(secret, f"benchmark:{seed}".encode(), hashlib.sha256).digest()
    u = (int.from_bytes(digest[:8], "big") + 0.5) / 2**64 - 0.5  # in (-0.5, 0.5)
    return -scale * math.copysign(1.0, u) * math.log(1 - 2 * abs(u))


def _rows(db: Session):
    query = select(EInvoiceRecord.tenant_id, EInvoiceRecord.due_date, EInvoiceRecord.paid_at).where(
        EInvoiceRecord.status == "validated",
        EInvoiceRecord.due_date.is_not(None),
        EInvoiceRecord.paid_at.is_not(None),
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        from app.db import set_worker_context

        with Session(bind=db.get_bind()) as worker:
            set_worker_context(worker, actor_ref="benchmarks")
            return list(worker.execute(query).all())
    return list(db.execute(query).all())


def _per_company(db: Session) -> dict[str, float]:
    lates: dict[str, list[int]] = {}
    for tenant_id, due, paid in _rows(db):
        lates.setdefault(str(tenant_id), []).append((paid - due).days)
    return {
        tenant: min(CLIP_DAYS, max(0, statistics.median(values)))
        for tenant, values in lates.items()
    }


def _worker(db: Session):
    """A worker session on PostgreSQL (the release lives with the default company)."""
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        from app.db import set_worker_context

        worker = Session(bind=db.get_bind())
        set_worker_context(worker, actor_ref="benchmarks")
        return worker
    return None


def _release(db: Session, today: dt.date, values: dict[str, float]) -> dict:
    """Today's one release: the stored one, or computed and stored now."""
    worker = _worker(db)
    session = worker or db
    try:
        if worker is not None:
            # Concurrent first requests wait here, so the day gets exactly one release.
            worker.execute(
                text("select pg_advisory_xact_lock(hashtext(:key))"),
                {"key": f"finbrain:benchmark:{today.isoformat()}"},
            )
        stored = session.scalar(
            select(WorkflowAuditEntry)
            .where(
                WorkflowAuditEntry.tenant_id == DEFAULT_TENANT_ID,
                WorkflowAuditEntry.event_type == RELEASED,
                WorkflowAuditEntry.resource_id == today.isoformat(),
            )
            .order_by(WorkflowAuditEntry.id)
            .limit(1)
        )
        if stored is not None:
            return dict(stored.event_payload)
        n = len(values)
        release = {
            "metric": "median_days_late",
            "peer_value": None,
            "noise_scale": None,
            "epsilon": EPSILON,
        }
        if n >= MIN_COMPANIES:
            scale = (CLIP_DAYS / n) / EPSILON
            noisy = statistics.fmean(values.values()) + laplace(scale, f"days_late:{today}")
            release["peer_value"] = round(min(CLIP_DAYS, max(0.0, noisy)), 1)
            release["noise_scale"] = round(scale, 2)
        write_workflow_event(
            session,
            event_type=RELEASED,
            actor_role="system",
            actor_ref="system:benchmarks",
            resource_type="benchmark",
            resource_id=today.isoformat(),
            event_payload=release,
            tenant_id=DEFAULT_TENANT_ID,
        )
        session.commit()
        return release
    finally:
        if worker is not None:
            worker.close()


def report(db: Session, tenant_id: str, today: dt.date | None = None) -> BenchmarksResponse:
    today = today or dt.date.today()
    values = _per_company(db)
    mine = values.get(tenant_id)
    release = _release(db, today, values)
    measured = release["peer_value"] is not None
    return BenchmarksResponse(
        status="measured" if measured else "not_enough_companies",
        epsilon=EPSILON,
        min_companies=MIN_COMPANIES,
        metrics=[
            BenchmarkMetric(
                name="median_days_late",
                your_value=None if mine is None else round(mine, 1),
                peer_value=release["peer_value"],
                noise_scale=release["noise_scale"],
            )
        ],
    )
