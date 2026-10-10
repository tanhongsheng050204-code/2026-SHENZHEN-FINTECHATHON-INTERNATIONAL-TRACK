import hashlib
import hmac
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ProtectedTokenRegistry, TokenizedContent, TokenVaultEntry
from app.security.disclosure import new_disclosure_session
from app.security.keyring import decrypt_vault_entry
from app.security.tokenize import ACL_POLICY
from app.services.audit import write_audit_entry

TOKEN_PATTERN = re.compile(r"(?:AMOUNT_BAND_\d+_[0-9a-f]{10}|[A-Z]+_[0-9a-f]{10})")
BAND_LABELS = [
    "<RM500",
    "RM500–1K",
    "RM1K–2.5K",
    "RM2.5K–5K",
    "RM5K–10K",
    "RM10K–25K",
    "RM25K–50K",
    "RM50K–100K",
    "RM100K+",
]


@dataclass(frozen=True, slots=True)
class DetokenizationTrace:
    text: str
    restored_tokens: int
    withheld_tokens: int
    decisions: tuple["DisclosureDecision", ...] = ()
    disclosure_session_ref: str = ""
    single_use_grants: int = 0


@dataclass(frozen=True, slots=True)
class DisclosureDecision:
    token: str
    entity_type: str
    authorized: bool


def hash_query(question: str) -> str:
    return hmac.new(
        get_settings().token_identity_secret.encode(),
        question.encode(),
        hashlib.sha256,
    ).hexdigest()[:16]


def _band_label(token: str) -> str:
    match = re.fullmatch(r"AMOUNT_BAND_(\d+)_[0-9a-f]{10}", token)
    if match is None:
        raise ValueError("Invalid protected amount token")
    index = int(match.group(1))
    return BAND_LABELS[index] if index < len(BAND_LABELS) else BAND_LABELS[-1]


def detokenize_response_with_trace(
    db: Session,
    text: str,
    role: str,
    query_hash: str,
    actor_ref: str = "legacy",
    turn_ref: str = "unbound",
    allow_exact: bool | None = None,
    tenant_id: str | None = None,
) -> DetokenizationTrace:
    from app.security.guardrails import record_event

    if allow_exact is None:
        allow_exact = db.info.get("finbrain_disclosure_allowed", True)
    tenant_id = tenant_id or db.info.get("finbrain_request_tenant")
    result = text
    restored = 0
    withheld = 0
    decisions: list[DisclosureDecision] = []
    session = new_disclosure_session(
        query_hash=query_hash,
        actor_ref=actor_ref,
        role=role,
        turn_ref=turn_ref,
    )
    try:
        for _depth in range(5):
            tokens = sorted(set(TOKEN_PATTERN.findall(result)), key=len, reverse=True)
            if not tokens:
                break
            before_pass = result
            for token in tokens:
                registry = db.get(ProtectedTokenRegistry, token)
                entry = db.scalar(select(TokenVaultEntry).where(TokenVaultEntry.token == token))
                if tenant_id and registry and registry.tenant_id != tenant_id:
                    registry, entry = None, None
                if registry is None:
                    if token.startswith("AMOUNT_BAND_"):
                        result = result.replace(token, _band_label(token))
                    continue
                # PostgreSQL RLS hides ciphertext rows from roles outside allowed_roles.
                # The explicit check preserves identical behavior in SQLite tests.
                source = (
                    db.scalar(
                        select(TokenizedContent).where(
                            TokenizedContent.tenant_id == registry.tenant_id,
                            TokenizedContent.source_record_id == entry.source_record_id,
                        )
                    )
                    if entry
                    else None
                )
                employee_data = registry.data_class == "employee_personal" or (
                    source is not None
                    and source.record_type
                    in {
                        "payroll_line",
                        "employee_record",
                        "leave_record",
                    }
                )
                employee_access = role == "owner_director" or "hr" in db.info.get(
                    "finbrain_request_jobs", ()
                )
                # The current policy also applies to rows written under an older,
                # wider one: a role must be allowed both then and now.
                current_policy = role in ACL_POLICY.get(registry.entity_type, (role,))
                policy_access = entry is not None and (
                    (role in entry.allowed_roles and current_policy)
                    or (
                        employee_data
                        and employee_access
                        and registry.entity_type
                        in {"PERSON", "AMOUNT", "NRIC", "BANKACC", "EMAIL", "PHONE", "ADDR"}
                    )
                )
                authorized = (
                    allow_exact and policy_access and (not employee_data or employee_access)
                )
                if authorized:
                    assert entry is not None
                    plaintext = decrypt_vault_entry(db, entry)
                    grant = session.issue(token, plaintext)
                    replacement = session.consume(grant)
                    restored += 1
                else:
                    replacement = (
                        _band_label(token)
                        if registry.entity_type == "AMOUNT"
                        else registry.masked_value
                    )
                    withheld += 1
                    if registry.entity_type in {"BANKACC", "CARD", "NRIC"}:
                        record_event(
                            db,
                            registry.tenant_id,
                            "ASI03",
                            "Exact-value disclosure denied",
                            "Role policy or recent MFA requirement withheld a protected value.",
                            "blocked",
                        )
                result = result.replace(token, replacement)
                decisions.append(
                    DisclosureDecision(
                        token=token,
                        entity_type=registry.entity_type,
                        authorized=authorized,
                    )
                )
                write_audit_entry(
                    db,
                    role,
                    token,
                    authorized,
                    query_hash,
                    tenant_id=registry.tenant_id,
                    actor_ref=actor_ref,
                )
            if result == before_pass:
                break
        db.commit()
        return DetokenizationTrace(
            text=result,
            restored_tokens=restored,
            withheld_tokens=withheld,
            decisions=tuple(decisions),
            disclosure_session_ref=session.public_ref,
            single_use_grants=session.consumed_count,
        )
    finally:
        session.close()


def detokenize_response(
    db: Session,
    text: str,
    role: str,
    query_hash: str,
    actor_ref: str = "legacy",
    turn_ref: str = "unbound",
) -> str:
    return detokenize_response_with_trace(
        db, text, role, query_hash, actor_ref=actor_ref, turn_ref=turn_ref
    ).text
