import datetime as dt
import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.common import EMAIL_PATTERN, DataMode, EvidenceRef

PASSPORT_DIGEST_FIELDS = {"id", "version", "company_label", "issued_at", "metrics"}
AUDIT_PACK_DIGEST_FIELDS = {"id", "period", "company_label", "created_at", "items"}


def _digest(content: dict) -> str:
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class PassportMetric(BaseModel):
    """Strict: a document submitted for verification may carry nothing that was not issued."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(max_length=64)
    label: str = Field(max_length=200)
    value: str = Field(max_length=500)
    evidence: list[EvidenceRef] = Field(max_length=20)


class AnchorRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository_path: str = Field(max_length=200)
    anchored_at: dt.datetime | None
    commit: str | None = Field(max_length=64)


class Passport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(max_length=64)
    version: int
    company_label: str = Field(max_length=200)
    issued_at: dt.datetime
    metrics: list[PassportMetric] = Field(max_length=50)
    sha256: str = Field(max_length=64)
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


class ExternalGrantsResponse(BaseModel):
    data_mode: DataMode
    grants: list[ExternalGrant]


class PassportListResponse(BaseModel):
    data_mode: DataMode
    passports: list[Passport]


class AuditPackListResponse(BaseModel):
    data_mode: DataMode
    packs: list[AuditPack]
