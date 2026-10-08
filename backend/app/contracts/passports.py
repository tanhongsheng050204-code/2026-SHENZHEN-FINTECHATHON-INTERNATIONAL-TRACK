import datetime as dt
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.common import EMAIL_PATTERN, DataMode, EvidenceRef

PASSPORT_DIGEST_FIELDS = {"id", "version", "company_label", "issued_at", "metrics"}
AUDIT_PACK_DIGEST_FIELDS = {"id", "period", "company_label", "created_at", "items"}


def _digest(content: dict) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class PassportMetric(BaseModel):
    key: str
    label: str
    value: str
    evidence: list[EvidenceRef]


class AnchorRef(BaseModel):
    repository_path: str
    anchored_at: dt.datetime | None
    commit: str | None


class Passport(BaseModel):
    id: str
    version: int
    company_label: str
    issued_at: dt.datetime
    metrics: list[PassportMetric]
    sha256: str
    audit_entry_id: int | None
    anchor: AnchorRef | None


def passport_digest(passport: Passport) -> str:
    """SHA-256 over the canonical JSON of the content fields. Lenders can recompute it."""
    return _digest(passport.model_dump(mode="json", include=PASSPORT_DIGEST_FIELDS))


class PassportResponse(BaseModel):
    data_mode: DataMode
    passport: Passport


class VerificationResult(BaseModel):
    data_mode: DataMode
    passport_id: str
    status: Literal["verified", "mismatch", "unknown_passport"]
    expected_sha256: str | None
    computed_sha256: str
    chain_intact: bool
    anchor: AnchorRef | None
    mismatched_fields: list[str]


class AuditPackItem(BaseModel):
    key: str
    label: str
    description: str
    sha256: str


class AuditPack(BaseModel):
    id: str
    period: str
    company_label: str
    created_at: dt.datetime
    items: list[AuditPackItem]
    sha256: str


def audit_pack_digest(pack: AuditPack) -> str:
    """SHA-256 over the canonical JSON of the pack's content fields."""
    return _digest(pack.model_dump(mode="json", include=AUDIT_PACK_DIGEST_FIELDS))


class AuditPackRequest(BaseModel):
    period: str = Field(pattern=r"^\d{4}(-Q[1-4])?$", description="e.g. 2026 or 2026-Q3")


class AuditPackResponse(BaseModel):
    data_mode: DataMode
    pack: AuditPack


class GrantRequest(BaseModel):
    grantee_email: str = Field(max_length=254, pattern=EMAIL_PATTERN)
    expires_in_days: int = Field(ge=1, le=30)
    allow_exact_values: bool = False


class ExternalGrant(BaseModel):
    id: str
    kind: Literal["lender", "auditor"]
    scope: str
    grantee_email_token: str
    expires_at: dt.datetime
    allow_exact_values: bool
    status: Literal["active", "revoked", "expired"]
    share_path: str


class ExternalGrantResponse(BaseModel):
    data_mode: DataMode
    grant: ExternalGrant
