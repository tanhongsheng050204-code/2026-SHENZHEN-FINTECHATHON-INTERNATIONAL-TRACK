"""Stub Financing Readiness Passport, audit packs, verification and external grants.

Workstream B2 replaces issuance and verification (hashes recorded in the workflow
audit chain and anchored by anchor-audit-chain.yml); workstream B1 replaces grants
with persisted, expiring, revocable grants. The digest functions are the contract's
and are not stubs.
"""

import datetime as dt
import hashlib
from typing import Literal

from app.contracts.common import DataMode, EvidenceRef
from app.contracts.passports import (
    PASSPORT_DIGEST_FIELDS,
    AnchorRef,
    AuditPack,
    AuditPackItem,
    AuditPackResponse,
    ExternalGrant,
    GrantRequest,
    Passport,
    PassportMetric,
    PassportResponse,
    VerificationResult,
    audit_pack_digest,
    passport_digest,
)
from app.security.tokenize import derive_token

DEMO_PASSPORT_ID = "pp_demo_1"
DEMO_AUDIT_PACK_ID = "ap_demo_2026"
DEMO_LENDER_TOKEN = "demo-grant-token"
DEMO_AUDITOR_TOKEN = "demo-audit-token"
COMPANY_LABEL = "Synthetic demo company: Malaysian home-goods importer"

_METRICS = [
    PassportMetric(
        key="cash_flow_health",
        label="Cash-flow health",
        value="Shortfall risk in 23 days, covered by matched invoice financing",
        evidence=[EvidenceRef(label="90-day forecast", source="cashflow:forecast")],
    ),
    PassportMetric(
        key="annual_revenue",
        label="Annual revenue (validated e-invoices)",
        value="RM2.5M–3M",
        evidence=[EvidenceRef(label="Validated e-invoices", source="einvoice:last-12-months")],
    ),
    PassportMetric(
        key="receivables_quality",
        label="Receivables over 90 days",
        value="8%",
        evidence=[EvidenceRef(label="Receivables aging", source="finance:ar-aging")],
    ),
    PassportMetric(
        key="validated_einvoice_share",
        label="Validated e-invoice share",
        value="72%",
        evidence=[EvidenceRef(label="Validation status", source="einvoice:validation-status")],
    ),
    PassportMetric(
        key="customer_concentration",
        label="Largest customer's share of revenue",
        value="31%",
        evidence=[EvidenceRef(label="Revenue by customer", source="finance:top-customers")],
    ),
    PassportMetric(
        key="data_completeness",
        label="Bank lines matched to records",
        value="94%",
        evidence=[EvidenceRef(label="Reconciliation", source="bank_statement:reconciliation")],
    ),
    PassportMetric(
        key="compliance_status",
        label="Compliance status",
        value="MyInvois-ready; PDPA controls in place",
        evidence=[EvidenceRef(label="E-invoice readiness", source="einvoice:readiness")],
    ),
]

_UNSIGNED = Passport(
    id=DEMO_PASSPORT_ID,
    version=1,
    company_label=COMPANY_LABEL,
    issued_at=dt.datetime(2026, 10, 14, 9, 30, tzinfo=dt.UTC),
    metrics=_METRICS,
    sha256="",
    audit_entry_id=None,
    anchor=None,
)
_ANCHOR = AnchorRef(
    repository_path="audit-anchors/2026-10-14.json",
    anchored_at=dt.datetime(2026, 10, 14, 10, 0, tzinfo=dt.UTC),
    commit=None,
)
_PASSPORT = _UNSIGNED.model_copy(
    update={"sha256": passport_digest(_UNSIGNED), "audit_entry_id": 4182, "anchor": _ANCHOR}
)

_PACK_ITEMS = (
    ("ledger_export", "General ledger export", "Bank and journal lines for the period"),
    ("einvoice_register", "E-invoice register", "Every issued e-invoice with its UIN"),
    ("reconciliation_status", "Reconciliation status", "Bank lines matched to records: 94%"),
    ("audit_chain_proof", "Audit-chain proof", "Chain heads with their public GitHub anchors"),
    ("payroll_summary", "Payroll summary", "Monthly totals only; per-employee lines withheld"),
)


def issue() -> PassportResponse:
    return PassportResponse(data_mode=DataMode.STUB, passport=_PASSPORT)


def get(passport_id: str) -> PassportResponse:
    if passport_id != DEMO_PASSPORT_ID:
        raise LookupError(passport_id)
    return issue()


def _differences(document: Passport, recorded: Passport) -> list[str]:
    fields = [
        name
        for name in sorted(PASSPORT_DIGEST_FIELDS - {"metrics"})
        if getattr(document, name) != getattr(recorded, name)
    ]
    submitted = {metric.key: metric for metric in document.metrics}
    expected = {metric.key: metric for metric in recorded.metrics}
    metric_keys = sorted(
        key for key in submitted.keys() | expected.keys() if submitted.get(key) != expected.get(key)
    )
    return fields + metric_keys


def verify(document: Passport) -> VerificationResult:
    computed = passport_digest(document)
    if document.id != DEMO_PASSPORT_ID:
        return VerificationResult(
            data_mode=DataMode.STUB,
            passport_id=document.id,
            status="unknown_passport",
            expected_sha256=None,
            computed_sha256=computed,
            chain_intact=False,
            anchor=None,
            mismatched_fields=[],
        )
    matches = computed == _PASSPORT.sha256
    return VerificationResult(
        data_mode=DataMode.STUB,
        passport_id=document.id,
        status="verified" if matches else "mismatch",
        expected_sha256=_PASSPORT.sha256,
        computed_sha256=computed,
        chain_intact=True,
        anchor=_ANCHOR,
        mismatched_fields=[] if matches else _differences(document, _PASSPORT),
    )


def _pack(period: str) -> AuditPack:
    unsigned = AuditPack(
        id=f"ap_demo_{period}",
        period=period,
        company_label=COMPANY_LABEL,
        created_at=dt.datetime(2026, 10, 14, 10, 30, tzinfo=dt.UTC),
        items=[
            AuditPackItem(
                key=key,
                label=label,
                description=description,
                sha256=hashlib.sha256(f"{period}:{key}:{description}".encode()).hexdigest(),
            )
            for key, label, description in _PACK_ITEMS
        ],
        sha256="",
    )
    return unsigned.model_copy(update={"sha256": audit_pack_digest(unsigned)})


def prepare_audit_pack(period: str) -> AuditPackResponse:
    return AuditPackResponse(data_mode=DataMode.STUB, pack=_pack(period))


def get_audit_pack(pack_id: str) -> AuditPackResponse:
    if pack_id != DEMO_AUDIT_PACK_ID:
        raise LookupError(pack_id)
    return prepare_audit_pack("2026")


GrantKind = Literal["lender", "auditor"]

_VIEWS: dict[str, tuple[str, str, str]] = {
    "lender": ("passport", "lender/passports", DEMO_LENDER_TOKEN),
    "auditor": ("audit_pack", "auditor/packs", DEMO_AUDITOR_TOKEN),
}


def _check_scope(kind: GrantKind, scope_id: str) -> None:
    if kind == "lender":
        get(scope_id)
    else:
        get_audit_pack(scope_id)


def _grant(
    kind: GrantKind,
    scope_id: str,
    *,
    email_token: str,
    expires_at: dt.datetime,
    allow_exact_values: bool,
    status: Literal["active", "revoked"],
) -> ExternalGrant:
    scope_name, view, token = _VIEWS[kind]
    return ExternalGrant(
        id=f"grant_demo_{kind}",
        kind=kind,
        scope=f"{scope_name}:{scope_id}",
        grantee_email_token=email_token,
        expires_at=expires_at,
        allow_exact_values=allow_exact_values,
        status=status,
        share_path=f"/{view}/{token}",
    )


def create_grant(
    kind: GrantKind, scope_id: str, request: GrantRequest, tenant_id: str
) -> ExternalGrant:
    _check_scope(kind, scope_id)
    return _grant(
        kind,
        scope_id,
        email_token=derive_token("EMAIL", request.grantee_email, tenant_id),
        expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(days=request.expires_in_days),
        allow_exact_values=request.allow_exact_values,
        status="active",
    )


def revoke_grant(kind: GrantKind, scope_id: str, grant_id: str) -> ExternalGrant:
    _check_scope(kind, scope_id)
    if grant_id != f"grant_demo_{kind}":
        raise LookupError(grant_id)
    return _grant(
        kind,
        scope_id,
        email_token="EMAIL_demo",
        expires_at=dt.datetime.now(dt.UTC),
        allow_exact_values=False,
        status="revoked",
    )


def list_passports() -> list[Passport]:
    return [_PASSPORT]


def list_audit_packs() -> list[AuditPack]:
    return [get_audit_pack(DEMO_AUDIT_PACK_ID).pack]


def list_grants(kind: GrantKind, scope_id: str) -> list[ExternalGrant]:
    _check_scope(kind, scope_id)
    return [
        _grant(
            kind,
            scope_id,
            email_token="EMAIL_demo",
            expires_at=dt.datetime(2026, 10, 21, 9, 30, tzinfo=dt.UTC),
            allow_exact_values=False,
            status="active",
        )
    ]


def lender_view(grant_token: str) -> PassportResponse:
    if grant_token != DEMO_LENDER_TOKEN:
        raise LookupError(grant_token)
    return issue()


def auditor_view(grant_token: str) -> AuditPackResponse:
    if grant_token != DEMO_AUDITOR_TOKEN:
        raise LookupError(grant_token)
    return get_audit_pack(DEMO_AUDIT_PACK_ID)
