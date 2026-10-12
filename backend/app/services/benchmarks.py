"""Benchmarks across companies, with differential privacy.

"How does my collection speed compare with other companies?" answered without any
company's own figure being revealed or worked out:

- Each company contributes one value per metric (its median days late on paid
  e-invoices), clipped to [0, CLIP_DAYS], so one company can move the average by
  at most CLIP_DAYS / n (the sensitivity).
- The released average gets Laplace noise with scale sensitivity / EPSILON: the
  Laplace mechanism, epsilon-differentially private for that release.
- The noise is seeded from the server secret, the date and a digest of the exact
  values released. Asking again with the same data gives the same answer, so it
  cannot be averaged away; any change (a company joins, a figure moves) gets fresh
  noise, so the difference between two answers does not cancel the noise and
  reveal one company's figure. Each distinct release costs epsilon, and the cost
  adds up across releases (sequential composition).
- Nothing is released below MIN_COMPANIES contributing companies.

The company's own value is shown exactly, to itself only. Reading other companies'
rows uses a worker session, and only the noisy average leaves this module.
"""

import datetime as dt
import hashlib
import hmac
import math
import statistics

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.contracts.insights import BenchmarkMetric, BenchmarksResponse
from app.models import EInvoiceRecord

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


def report(db: Session, tenant_id: str, today: dt.date | None = None) -> BenchmarksResponse:
    today = today or dt.date.today()
    values = _per_company(db)
    mine = values.get(tenant_id)
    n = len(values)
    enough = n >= MIN_COMPANIES
    scale = (CLIP_DAYS / n) / EPSILON if n else None
    peer = None
    if enough:
        released = ",".join(f"{t}={v}" for t, v in sorted(values.items()))
        data = hashlib.sha256(released.encode()).hexdigest()
        noisy = statistics.fmean(values.values()) + laplace(scale, f"days_late:{today}:{data}")
        peer = round(min(CLIP_DAYS, max(0.0, noisy)), 1)
    return BenchmarksResponse(
        status="measured" if enough else "not_enough_companies",
        epsilon=EPSILON,
        min_companies=MIN_COMPANIES,
        metrics=[
            BenchmarkMetric(
                name="median_days_late",
                your_value=None if mine is None else round(mine, 1),
                peer_value=peer,
                noise_scale=round(scale, 2) if enough and scale else None,
            )
        ],
    )
