"""Financing Readiness Passport and audit packs, issued onto the tenant's audit chain.

Issuing computes the Passport from the same cash basis and financing profile the
Cash and Financing pages use (Plan 4), hashes its canonical JSON (the contract's
passport_digest) and appends a "passport_issued" event holding the hash and the
document to the tenant's workflow hash chain. Nothing else stores it, so the chain
is the record.

Verification is public: it finds the issued event by Passport id, compares the
submitted document's hash with the recorded one and names every changed field,
re-verifies the tenant's whole chain, and reports the first anchor file whose
workflow tail covers the entry (written by .github/workflows/anchor-audit-chain.yml).

Passport amounts are bands, never exact figures. Audit packs follow the same
pattern with "audit_pack_prepared" events; payroll appears as run totals only.
"""

import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select

from app import models
from app.auth.principal import AuthPrincipal
from app.contracts.common import DataMode, EvidenceRef
from app.contracts.passports import (
    AUDIT_PACK_DIGEST_FIELDS,
    PASSPORT_DIGEST_FIELDS,
    AnchorRef,
    AuditPack,
    AuditPackItem,
    Passport,
    PassportMetric,
    VerificationResult,
    audit_pack_digest,
    passport_digest,
)
from app.models import EInvoiceRecord, Tenant, WorkflowAuditEntry
from app.services import cashflow_engine, financing_profile
from app.services.cashflow import basis_for
from app.services.workflow_audit import verify_workflow_chain, write_workflow_event
from app.stubs.financing import _METRICS as FINANCING_FACTS
from app.stubs.passports import _differences

_BANDS = (
    (Decimal("50000"), "under RM50k"),
    (Decimal("100000"), "RM50k–100k"),
    (Decimal("250000"), "RM100k–250k"),
    (Decimal("500000"), "RM250k–500k"),
    (Decimal("1000000"), "RM500k–1M"),
    (Decimal("2500000"), "RM1M–2.5M"),
    (Decimal("5000000"), "RM2.5M–5M"),
)


def anchor_dir() -> Path:
    configured = os.environ.get("AUDIT_ANCHOR_DIR")
    return Path(configured) if configured else Path(__file__).resolve().parents[3] / "audit-anchors"


def _band(amount: Decimal) -> str:
    return next((label for limit, label in _BANDS if amount < limit), "over RM5M")


def _percent(value: Decimal | None) -> str:
    return "Not on record" if value is None else f"{value * 100:.0f}%"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(microsecond=0)


def _company(db, tenant_id: str, data_mode: DataMode) -> str:
    tenant = db.get(Tenant, tenant_id)
    name = tenant.name if tenant is not None else "Company"
    return name + (" (synthetic demo data)" if data_mode == DataMode.STUB else "")


def _metrics(db, principal: AuthPrincipal) -> tuple[DataMode, list[PassportMetric]]:
    tenant_id = str(principal.tenant_id)
    today = dt.date.today()
    basis = basis_for(db, principal, today)
    forecast = cashflow_engine.build_forecast(basis, horizon_days=90, as_of=today)
    facts = financing_profile.compute(db, tenant_id, forecast).values
    shortfall = forecast.shortfall
    invoices = db.scalar(select(func.count()).where(EInvoiceRecord.tenant_id == tenant_id)) or 0
    validated = (
        db.scalar(
            select(func.count()).where(
                EInvoiceRecord.tenant_id == tenant_id, EInvoiceRecord.status == "validated"
            )
        )
        or 0
    )
    revenue = facts.get("annual_revenue")

    def metric(key: str, label: str, value: str, source: str, evidence: str) -> PassportMetric:
        return PassportMetric(
            key=key, label=label, value=value, evidence=[EvidenceRef(label=evidence, source=source)]
        )

    return basis.data_mode, [
        metric(
            "cash_flow_health",
            "Cash-flow health",
            f"Shortfall risk in {shortfall.day} days; gap {_band(shortfall.gap)}"
            if shortfall
            else "No shortfall in the next 90 days",
            "cashflow:forecast",
            "90-day forecast",
        ),
        metric(
            "annual_revenue",
            "Annual revenue",
            "Not on record" if revenue is None else _band(revenue),
            "profile:revenue",
            "Declared or validated revenue",
        ),
        metric(
            "receivables_quality",
            "Receivables over 90 days",
            _percent(facts.get("receivables_over_90_share")),
            "finance:ar-aging",
            "Receivables aging",
        ),
        metric(
            "validated_einvoice_share",
            "Validated e-invoice share",
            _percent(facts.get("validated_einvoice_share")),
            "einvoice:validation-status",
            "Validation status",
        ),
        metric(
            "customer_concentration",
            "Largest customer's share of revenue",
            _percent(facts.get("top_customer_share")),
            "finance:top-customers",
            "Revenue by customer",
        ),
        metric(
            "data_completeness",
            "Financing facts on record",
            f"{len(facts)} of {len(FINANCING_FACTS)}",
            "financing:profile",
            "Financing profile",
        ),
        metric(
            "compliance_status",
            "E-invoices validated by MyInvois",
            f"{validated} of {invoices}" if invoices else "No e-invoices on record",
            "einvoice:readiness",
            "E-invoice readiness",
        ),
    ]


def _anchor(db, entry: WorkflowAuditEntry) -> AnchorRef | None:
    directory = anchor_dir()
    if not directory.is_dir():
        return None
    for path in sorted(directory.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for anchor in record.get("anchors", []):
            if anchor.get("chain") != "workflow" or anchor.get("tenant_id") != entry.tenant_id:
                continue
            tail_id = db.scalar(
                select(WorkflowAuditEntry.id).where(
                    WorkflowAuditEntry.tenant_id == entry.tenant_id,
                    WorkflowAuditEntry.event_hash == anchor.get("tail_hash"),
                )
            )
            if tail_id is not None and tail_id >= entry.id:
                return AnchorRef(
                    repository_path=f"audit-anchors/{path.name}",
                    anchored_at=dt.datetime.fromisoformat(record["anchored_at"]),
                    commit=None,
                )
    return None


def _issued(db, *, tenant_id: str | None = None, passport_id: str | None = None):
    query = select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "passport_issued")
    if tenant_id is not None:
        query = query.where(WorkflowAuditEntry.tenant_id == tenant_id)
    if passport_id is not None:
        query = query.where(WorkflowAuditEntry.resource_id == passport_id)
    return db.scalars(query.order_by(WorkflowAuditEntry.id)).all()


def _passport(db, entry: WorkflowAuditEntry) -> Passport:
    return Passport(
        **entry.event_payload["document"],
        sha256=entry.event_payload["sha256"],
        audit_entry_id=entry.id,
        anchor=_anchor(db, entry),
    )


def data_mode_of(db, principal: AuthPrincipal) -> DataMode:
    return basis_for(db, principal, dt.date.today()).data_mode


def issue(db, principal: AuthPrincipal) -> Passport:
    tenant_id = str(principal.tenant_id)
    data_mode, metrics = _metrics(db, principal)
    unsigned = Passport(
        id="pp_" + secrets.token_hex(6),
        version=len(_issued(db, tenant_id=tenant_id)) + 1,
        company_label=_company(db, tenant_id, data_mode),
        issued_at=_now(),
        metrics=metrics,
        sha256="",
        audit_entry_id=None,
        anchor=None,
    )
    digest = passport_digest(unsigned)
    entry = write_workflow_event(
        db,
        event_type="passport_issued",
        actor_role=principal.role.value,
        actor_ref=str(principal.user_id),
        resource_type="passport",
        resource_id=unsigned.id,
        event_payload={
            "sha256": digest,
            "document": unsigned.model_dump(mode="json", include=PASSPORT_DIGEST_FIELDS),
        },
        tenant_id=tenant_id,
    )
    db.commit()
    return _passport(db, entry)


def list_for(db, tenant_id: str) -> list[Passport]:
    return [_passport(db, entry) for entry in _issued(db, tenant_id=tenant_id)]


def get(db, tenant_id: str, passport_id: str) -> Passport:
    entries = _issued(db, tenant_id=tenant_id, passport_id=passport_id)
    if not entries:
        raise LookupError(passport_id)
    return _passport(db, entries[0])


def verify(db, document: Passport) -> VerificationResult:
    computed = passport_digest(document)
    entries = _issued(db, passport_id=document.id)
    if not entries:
        return VerificationResult(
            data_mode=DataMode.LIVE,
            passport_id=document.id,
            status="unknown_passport",
            expected_sha256=None,
            computed_sha256=computed,
            chain_intact=False,
            anchor=None,
            mismatched_fields=[],
        )
    entry = entries[0]
    recorded = Passport(
        **entry.event_payload["document"], sha256="", audit_entry_id=None, anchor=None
    )
    expected = entry.event_payload["sha256"]
    if not hmac.compare_digest(document.sha256, expected):
        # The submitter does not hold the issued document. Naming fields or returning
        # the recorded hash would let anyone with a Passport id guess its contents
        # one metric at a time.
        return VerificationResult(
            data_mode=DataMode.LIVE,
            passport_id=document.id,
            status="mismatch",
            expected_sha256=None,
            computed_sha256=computed,
            chain_intact=False,
            anchor=None,
            mismatched_fields=["sha256"],
        )
    matches = computed == expected
    return VerificationResult(
        data_mode=DataMode.LIVE,
        passport_id=document.id,
        status="verified" if matches else "mismatch",
        expected_sha256=expected,
        computed_sha256=computed,
        chain_intact=verify_workflow_chain(db, entry.tenant_id)
        and passport_digest(recorded) == expected,
        anchor=_anchor(db, entry),
        mismatched_fields=[] if matches else _differences(document, recorded),
    )


# --- Audit packs ---


def _period(period: str) -> tuple[dt.date, dt.date]:
    year = int(period[:4])
    if "-Q" not in period:
        return dt.date(year, 1, 1), dt.date(year, 12, 31)
    quarter = int(period[-1])
    start = dt.date(year, 3 * quarter - 2, 1)
    if quarter == 4:
        return start, dt.date(year, 12, 31)
    return start, dt.date(year, 3 * quarter + 1, 1) - dt.timedelta(days=1)


def _item(key: str, label: str, description: str, data: dict) -> AuditPackItem:
    canonical = json.dumps({"key": key, "data": data}, sort_keys=True, default=str)
    return AuditPackItem(
        key=key,
        label=label,
        description=description,
        sha256=hashlib.sha256(canonical.encode()).hexdigest(),
    )


def _pack_items(db, tenant_id: str, start: dt.date, end: dt.date) -> list[AuditPackItem]:
    bank = getattr(models, "BankTransaction", None)
    lines = []
    if bank is not None:
        lines = db.scalars(
            select(bank.source_record_id).where(
                bank.tenant_id == tenant_id, bank.posted_on >= start, bank.posted_on <= end
            )
        ).all()
    invoices = db.scalars(
        select(EInvoiceRecord).where(
            EInvoiceRecord.tenant_id == tenant_id,
            EInvoiceRecord.issue_date >= start,
            EInvoiceRecord.issue_date <= end,
        )
    ).all()
    with_uin = [i for i in invoices if i.uin]
    chain = db.scalars(
        select(WorkflowAuditEntry.event_hash)
        .where(WorkflowAuditEntry.tenant_id == tenant_id)
        .order_by(WorkflowAuditEntry.id)
    ).all()
    intact = verify_workflow_chain(db, tenant_id)
    runs = []
    payroll = getattr(models, "PayrollRun", None)
    if payroll is not None:
        runs = db.scalars(
            select(payroll).where(
                payroll.tenant_id == tenant_id, payroll.pay_date >= start, payroll.pay_date <= end
            )
        ).all()
    return [
        _item(
            "ledger_export",
            "Bank statement lines",
            f"{len(lines)} imported bank lines in the period",
            {"lines": sorted(lines)},
        ),
        _item(
            "einvoice_register",
            "E-invoice register",
            f"{len(invoices)} e-invoices issued in the period; "
            f"{len(with_uin)} carry a MyInvois UIN",
            {
                "invoices": sorted(
                    (i.invoice_no or "", i.uin or "", str(i.total_amount)) for i in invoices
                )
            },
        ),
        _item(
            "reconciliation_status",
            "Reconciliation status",
            "Not measured: bank-to-record matching is not built yet",
            {},
        ),
        _item(
            "audit_chain_proof",
            "Audit-chain proof",
            f"Workflow chain {'intact' if intact else 'BROKEN'}: {len(chain)} events, tail "
            + (chain[-1][:12] if chain else "genesis"),
            {"tail": chain[-1] if chain else "genesis", "events": len(chain), "intact": intact},
        ),
        _item(
            "payroll_summary",
            "Payroll summary",
            f"{len(runs)} payroll runs in the period, totals only; per-employee lines withheld",
            {
                "runs": sorted(
                    (r.period, str(r.total_gross), str(r.employer_contributions)) for r in runs
                )
            },
        ),
    ]


def _packs(db, *, tenant_id: str | None = None, pack_id: str | None = None):
    query = select(WorkflowAuditEntry).where(WorkflowAuditEntry.event_type == "audit_pack_prepared")
    if tenant_id is not None:
        query = query.where(WorkflowAuditEntry.tenant_id == tenant_id)
    if pack_id is not None:
        query = query.where(WorkflowAuditEntry.resource_id == pack_id)
    return db.scalars(query.order_by(WorkflowAuditEntry.id)).all()


def _pack(entry: WorkflowAuditEntry) -> AuditPack:
    return AuditPack(**entry.event_payload["document"], sha256=entry.event_payload["sha256"])


def prepare_pack(db, principal: AuthPrincipal, period: str) -> AuditPack:
    tenant_id = str(principal.tenant_id)
    start, end = _period(period)
    unsigned = AuditPack(
        id="ap_" + secrets.token_hex(6),
        period=period,
        company_label=_company(db, tenant_id, data_mode_of(db, principal)),
        created_at=_now(),
        items=_pack_items(db, tenant_id, start, end),
        sha256="",
    )
    digest = audit_pack_digest(unsigned)
    entry = write_workflow_event(
        db,
        event_type="audit_pack_prepared",
        actor_role=principal.role.value,
        actor_ref=str(principal.user_id),
        resource_type="audit_pack",
        resource_id=unsigned.id,
        event_payload={
            "sha256": digest,
            "document": unsigned.model_dump(mode="json", include=AUDIT_PACK_DIGEST_FIELDS),
        },
        tenant_id=tenant_id,
    )
    db.commit()
    return _pack(entry)


def list_packs(db, tenant_id: str) -> list[AuditPack]:
    return [_pack(entry) for entry in _packs(db, tenant_id=tenant_id)]


def get_pack(db, tenant_id: str, pack_id: str) -> AuditPack:
    entries = _packs(db, tenant_id=tenant_id, pack_id=pack_id)
    if not entries:
        raise LookupError(pack_id)
    return _pack(entries[0])
