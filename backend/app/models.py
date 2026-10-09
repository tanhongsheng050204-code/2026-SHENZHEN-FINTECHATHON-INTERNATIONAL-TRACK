import json
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(UTC)


class EmbeddingType(TypeDecorator[list[float]]):
    """JSON text on SQLite and a native vector(768) on Postgres."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(768))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: list[float] | str | None, dialect: Dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return json.loads(value) if isinstance(value, str) else value
        return value if isinstance(value, str) else json.dumps(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> list[float] | None:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return [float(item) for item in value]
        return [float(item) for item in json.loads(value)]


class RoleListType(TypeDecorator[list[str]]):
    """SQLite JSON locally and indexable JSONB on Postgres."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class ObjectType(TypeDecorator[dict[str, Any]]):
    """SQLite JSON locally and JSONB for queryable protected metadata on Postgres."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB(none_as_null=True))
        return dialect.type_descriptor(JSON(none_as_null=True))


class Base(DeclarativeBase):
    pass


class BackendAuthSession(Base):
    """Opaque browser handle; provider credentials exist only as encrypted server data."""

    __tablename__ = "backend_auth_sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    csrf_hash: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), index=True)
    tenant_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("tenants.id"))
    purpose: Mapped[str] = mapped_column(String, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    password_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    credential_ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    credential_nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    generation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    aal: Mapped[str] = mapped_column(String, default="aal1", nullable=False)
    mfa_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TenantSettingsRecord(Base):
    __tablename__ = "tenant_settings"
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    document: Mapped[dict] = mapped_column(ObjectType(), nullable=False)


class TenantSettingsVersion(Base):
    __tablename__ = "tenant_settings_versions"
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    document: Mapped[dict] = mapped_column(ObjectType(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TenantSettingsChange(Base):
    __tablename__ = "tenant_setting_changes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), index=True
    )
    area: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False)
    base_version: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_document: Mapped[dict] = mapped_column(ObjectType(), nullable=False)
    preview: Mapped[list[str]] = mapped_column(RoleListType(), nullable=False)
    proposer_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False)
    reviewer_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TenantCustomization(Base):
    __tablename__ = "tenant_customizations"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), index=True
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    document: Mapped[dict] = mapped_column(ObjectType(), nullable=False)
    created_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SecurityGuardrailEvent(Base):
    __tablename__ = "security_guardrail_events"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), index=True
    )
    agent_id: Mapped[str | None] = mapped_column(String)
    owasp_code: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[str] = mapped_column(String, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentSecurityControl(Base):
    __tablename__ = "agent_security_controls"
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), primary_key=True
    )
    agent_id: Mapped[str] = mapped_column(String, primary_key=True)
    engaged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_by: Mapped[str] = mapped_column(Uuid(as_uuid=False), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentBudgetWindow(Base):
    __tablename__ = "agent_budget_windows"
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), primary_key=True
    )
    agent_id: Mapped[str] = mapped_column(String, primary_key=True)
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    tool_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    spent: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)


# Well-known id for the single tenant that exists while multi-tenancy is being
# rolled out. Every pre-existing row (and every SQLite/local-dev row, since there
# is no migration-driven backfill there) belongs to this tenant.
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), primary_key=True, default=DEFAULT_TENANT_ID
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthUserRole(Base):
    """Backend-authoritative DuitDuit role assigned to a Supabase Auth user within one tenant."""

    __tablename__ = "user_roles"

    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), primary_key=True, default=DEFAULT_TENANT_ID
    )
    user_role: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    job_functions: Mapped[list[str]] = mapped_column(RoleListType(), default=list, nullable=False)
    display_name: Mapped[str] = mapped_column(String, default="Team member", nullable=False)
    email_masked: Mapped[str] = mapped_column(String, default="[restricted]", nullable=False)
    mfa_enrolled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_generation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class TokenizedContent(Base):
    """Sanitized content only; raw inbound text is never persisted."""

    __tablename__ = "tokenized_content"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    source_record_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingType())
    record_type: Mapped[str | None] = mapped_column(String)
    summary: Mapped[str | None] = mapped_column(Text)
    source_system: Mapped[str] = mapped_column(String, default="legacy", nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_fingerprint: Mapped[str | None] = mapped_column(String)
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(
        ObjectType(), default=dict, nullable=False
    )
    structured_summary: Mapped[dict[str, Any] | None] = mapped_column(ObjectType())
    processing_status: Mapped[str] = mapped_column(String, default="protected", nullable=False)
    processing_error: Mapped[str | None] = mapped_column(String)
    enrichment_mode: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class TokenVaultEntry(Base):
    """Encrypted sensitive values keyed by deterministic tenant-scoped tokens."""

    __tablename__ = "token_vault"

    token: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    data_class: Mapped[str] = mapped_column(String, default="customer_personal", nullable=False)
    encrypted_value: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    masked_value: Mapped[str] = mapped_column(String, default="[restricted]", nullable=False)
    encryption_algorithm: Mapped[str] = mapped_column(String, default="AES-256-GCM", nullable=False)
    allowed_roles: Mapped[list[str]] = mapped_column(RoleListType(), nullable=False)
    sensitivity: Mapped[str] = mapped_column(String, default="high")
    source_record_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProtectedTokenRegistry(Base):
    """Non-secret token metadata available without exposing encrypted values."""

    __tablename__ = "protected_token_registry"

    token: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    data_class: Mapped[str] = mapped_column(String, default="customer_personal", nullable=False)
    masked_value: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VaultKeyVersion(Base):
    """A random vault-generation key wrapped by the environment-held master key."""

    __tablename__ = "vault_key_versions"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    wrapped_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    wrap_nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VaultRotationJob(Base):
    """Resumable progress for re-encrypting vault rows under a new generation."""

    __tablename__ = "vault_rotation_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_version: Mapped[int] = mapped_column(Integer, nullable=False)
    to_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    rows_total: Mapped[int] = mapped_column(Integer, nullable=False)
    rows_rotated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_token: Mapped[str | None] = mapped_column(String)
    failure_code: Mapped[str | None] = mapped_column(String)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLogEntry(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("tenants.id"))
    prev_hash: Mapped[str] = mapped_column(String, nullable=False)
    event_hash: Mapped[str] = mapped_column(String, nullable=False)
    user_role: Mapped[str] = mapped_column(String, nullable=False)
    token: Mapped[str] = mapped_column(String, nullable=False)
    authorized: Mapped[bool] = mapped_column(Boolean, nullable=False)
    query_hash: Mapped[str] = mapped_column(String, nullable=False)
    actor_ref: Mapped[str] = mapped_column(String, default="legacy", nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class TelegramUpdateReceipt(Base):
    """Privacy-safe idempotency receipt; raw Telegram payloads are never stored."""

    __tablename__ = "telegram_update_receipts"

    update_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    message_ref_hash: Mapped[str | None] = mapped_column(String, unique=True)
    actor_ref: Mapped[str] = mapped_column(String, nullable=False)
    source_record_id: Mapped[str | None] = mapped_column(String)
    update_kind: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="received")
    failure_code: Mapped[str | None] = mapped_column(String)
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="RESTRICT")
    )
    onboarding_session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("telegram_onboarding_sessions.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class IntegrationStatus(Base):
    """Operational heartbeat containing no credentials or external identities."""

    __tablename__ = "integration_status"

    integration_key: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    detector_ready: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_update_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String)


class EmailSyncState(Base):
    """Incremental IMAP cursor containing no mailbox address or credentials."""

    __tablename__ = "email_sync_state"

    connector_key: Mapped[str] = mapped_column(String, primary_key=True)
    mailbox_ref: Mapped[str] = mapped_column(String, nullable=False)
    folder_name: Mapped[str] = mapped_column(String, nullable=False)
    last_uid: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String, default="idle", nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class EmailIngestionReceipt(Base):
    """HMAC-addressed email delivery receipt; raw headers are never persisted."""

    __tablename__ = "email_ingestion_receipts"

    message_ref_hash: Mapped[str] = mapped_column(String, primary_key=True)
    source_record_id: Mapped[str | None] = mapped_column(String, unique=True)
    status: Mapped[str] = mapped_column(String, default="received", nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    customer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("customers.id"))
    outreach_action_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("outreach_actions.id")
    )
    in_reply_to_ref_hash: Mapped[str | None] = mapped_column(String)
    correlation_status: Mapped[str | None] = mapped_column(String)
    correlated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailReplyCorrelation(Base):
    __tablename__ = "email_reply_correlations"
    __table_args__ = (
        UniqueConstraint(
            "email_receipt_ref_hash",
            "outreach_action_id",
            name="email_reply_action_unique",
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), nullable=False
    )
    email_receipt_ref_hash: Mapped[str] = mapped_column(
        String, ForeignKey("email_ingestion_receipts.message_ref_hash"), nullable=False
    )
    outreach_action_id: Mapped[str] = mapped_column(
        String, ForeignKey("outreach_actions.id"), nullable=False
    )
    matched_reference_hash: Mapped[str] = mapped_column(String, nullable=False)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    tokenized_content_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tokenized_content.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, default="correlated", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StructuredIngestionBatch(Base):
    """Opaque structured-file status; source bytes and filenames are never stored."""

    __tablename__ = "structured_ingestion_batches"

    batch_ref: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    schema_name: Mapped[str] = mapped_column(String, nullable=False)
    origin_channel: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    protected_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    ready_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    created_by_user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    context_customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="SET NULL")
    )
    context_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "sequence_number", name="conversation_turn_sequence_unique"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    conversation_id: Mapped[str] = mapped_column(
        String, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    user_role: Mapped[str] = mapped_column(String, nullable=False)
    protected_question: Mapped[str] = mapped_column(Text, nullable=False)
    protected_answer: Mapped[str] = mapped_column(Text, nullable=False)
    protected_brief: Mapped[dict[str, Any] | None] = mapped_column(ObjectType())
    query_intent: Mapped[str] = mapped_column(String, nullable=False)
    source_systems: Mapped[list[str]] = mapped_column(RoleListType(), nullable=False)
    reasoning_mode: Mapped[str] = mapped_column(String, nullable=False)
    insufficient_evidence: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConversationTurnCitation(Base):
    __tablename__ = "conversation_turn_citations"
    __table_args__ = (
        UniqueConstraint("turn_id", "ordinal", name="conversation_citation_ordinal_unique"),
        UniqueConstraint(
            "turn_id",
            "tokenized_content_id",
            name="conversation_citation_record_unique",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    turn_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversation_turns.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    tokenized_content_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tokenized_content.id", ondelete="RESTRICT"), nullable=False
    )


class ProcessRecommendation(Base):
    __tablename__ = "process_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    fingerprint: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    expected_benefit: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_owner: Mapped[str] = mapped_column(String, nullable=False)
    success_metric: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, default="proposed", nullable=False)
    analysis_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    analysis_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source_systems: Mapped[list[str]] = mapped_column(RoleListType(), nullable=False)
    enrichment_mode: Mapped[str] = mapped_column(String, nullable=False)
    origin_type: Mapped[str] = mapped_column(String, default="process_analysis", nullable=False)
    origin_turn_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("conversation_turns.id", ondelete="SET NULL"),
    )
    origin_query_hash: Mapped[str | None] = mapped_column(String)
    created_by_user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class RecommendationEvidence(Base):
    __tablename__ = "recommendation_evidence"
    __table_args__ = (
        UniqueConstraint(
            "recommendation_id",
            "tokenized_content_id",
            name="recommendation_evidence_record_unique",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    recommendation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("process_recommendations.id", ondelete="CASCADE"), nullable=False
    )
    tokenized_content_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tokenized_content.id", ondelete="RESTRICT"), nullable=False
    )
    evidence_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RecommendationDecision(Base):
    __tablename__ = "recommendation_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    recommendation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("process_recommendations.id", ondelete="CASCADE"), nullable=False
    )
    decision: Mapped[str] = mapped_column(String, nullable=False)
    actor_role: Mapped[str] = mapped_column(String, nullable=False)
    actor_ref: Mapped[str] = mapped_column(String, nullable=False)
    protected_comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkflowAuditEntry(Base):
    __tablename__ = "workflow_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), ForeignKey("tenants.id"))
    prev_hash: Mapped[str] = mapped_column(String, nullable=False)
    event_hash: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    actor_role: Mapped[str] = mapped_column(String, nullable=False)
    actor_ref: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[str] = mapped_column(String, nullable=False)
    resource_id: Mapped[str] = mapped_column(String, nullable=False)
    event_payload: Mapped[dict[str, Any]] = mapped_column(ObjectType(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Customer(Base):
    """Canonical business identity resolved across sources by normalized name.

    First cut of entity resolution: deterministic name normalization (corporate
    suffix stripped, casing/punctuation collapsed) only. Embedding-similarity-based
    fuzzy matching is a documented future step, not built here.
    """

    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "normalized_name", name="customers_tenant_normalized_unique"),
        UniqueConstraint("tenant_id", "id", name="customers_tenant_id_unique"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    canonical_name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False)
    profile_status: Mapped[str] = mapped_column(String, default="confirmed", nullable=False)
    identity_review_status: Mapped[str] = mapped_column(String, default="clear", nullable=False)
    profile_origin: Mapped[str] = mapped_column(String, default="manual", nullable=False)
    primary_name_token: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CustomerAlias(Base):
    __tablename__ = "customer_aliases"
    __table_args__ = (
        UniqueConstraint("tenant_id", "customer_id", "alias_token", name="customer_alias_unique"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    alias_token: Mapped[str] = mapped_column(String, nullable=False)
    alias_type: Mapped[str] = mapped_column(String, nullable=False)
    match_status: Mapped[str] = mapped_column(String, default="probable", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    source_system: Mapped[str] = mapped_column(String, nullable=False)
    source_record_id: Mapped[str | None] = mapped_column(String)
    created_by_user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    reviewed_by_user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CustomerRecordLink(Base):
    __tablename__ = "customer_record_links"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "customer_id",
            "tokenized_content_id",
            "match_basis",
            name="customer_record_link_unique",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    tokenized_content_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tokenized_content.id", ondelete="RESTRICT"), nullable=False
    )
    alias_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customer_aliases.id", ondelete="RESTRICT")
    )
    match_status: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    match_basis: Mapped[str] = mapped_column(String, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    reviewed_by_user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CustomerAttentionSnapshot(Base):
    __tablename__ = "customer_attention_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "customer_id",
            "input_fingerprint",
            name="customer_attention_input_unique",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[str] = mapped_column(String, nullable=False)
    calculation_version: Mapped[str] = mapped_column(String, nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CustomerAttentionSignal(Base):
    __tablename__ = "customer_attention_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customer_attention_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    signal_type: Mapped[str] = mapped_column(String, nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    freshness: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    tokenized_content_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tokenized_content.id", ondelete="RESTRICT")
    )
    einvoice_record_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("einvoice_records.id", ondelete="RESTRICT")
    )
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    details: Mapped[dict[str, Any]] = mapped_column(ObjectType(), default=dict, nullable=False)


class CustomerEndpoint(Base):
    __tablename__ = "customer_endpoints"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "channel",
            "endpoint_token",
            name="customer_endpoint_tenant_channel_token_unique",
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String, nullable=False)
    endpoint_token: Mapped[str] = mapped_column(String, nullable=False)
    delivery_token: Mapped[str | None] = mapped_column(String)
    verification_status: Mapped[str] = mapped_column(String, default="observed", nullable=False)
    origin: Mapped[str] = mapped_column(String, default="manual", nullable=False)
    verified_by_user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TelegramOnboardingSession(Base):
    """Durable protected onboarding state; contains tokens, never raw contact values."""

    __tablename__ = "telegram_onboarding_sessions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "telegram_endpoint_token",
            name="telegram_onboarding_tenant_endpoint_unique",
        ),
        Index("telegram_onboarding_tenant_status_idx", "tenant_id", "status", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), nullable=False
    )
    telegram_endpoint_token: Mapped[str] = mapped_column(String, nullable=False)
    telegram_delivery_token: Mapped[str] = mapped_column(String, nullable=False)
    name_token: Mapped[str | None] = mapped_column(String)
    email_token: Mapped[str | None] = mapped_column(String)
    phone_token: Mapped[str | None] = mapped_column(String)
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="RESTRICT")
    )
    profile_content_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("tokenized_content.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String, default="awaiting_consent", nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class TenantOutreachPolicy(Base):
    __tablename__ = "tenant_outreach_policies"

    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), primary_key=True
    )
    telegram_reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    grace_days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    repeat_interval_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    max_reminders: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    require_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    policy_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_by_user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class CustomerIdentityClaim(Base):
    """Protected, reviewable identity evidence observed for an inbound endpoint."""

    __tablename__ = "customer_identity_claims"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "customer_id",
            "endpoint_id",
            "identity_token",
            "claim_basis",
            name="customer_identity_claim_unique",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    endpoint_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customer_endpoints.id", ondelete="RESTRICT"), nullable=False
    )
    identity_token: Mapped[str] = mapped_column(String, nullable=False)
    claim_basis: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_content_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tokenized_content.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String, default="observed", nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_by_user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutreachAction(Base):
    __tablename__ = "outreach_actions"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="outreach_idempotency_unique"),
        UniqueConstraint(
            "tenant_id", "provider_message_ref_hash", name="outreach_provider_ref_unique"
        ),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), nullable=False
    )
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("customers.id"), nullable=False)
    customer_endpoint_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customer_endpoints.id"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String, nullable=False)
    protected_subject: Mapped[str] = mapped_column(Text, nullable=False)
    protected_body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, default="draft", nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    created_by_actor_ref: Mapped[str | None] = mapped_column(String)
    origin_type: Mapped[str] = mapped_column(String, default="manual", nullable=False)
    origin_invoice_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("einvoice_records.id", ondelete="RESTRICT")
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by_user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    send_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_message_ref_hash: Mapped[str | None] = mapped_column(String)
    failure_code: Mapped[str | None] = mapped_column(String)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class OutreachEvidence(Base):
    __tablename__ = "outreach_evidence"
    __table_args__ = (
        UniqueConstraint(
            "outreach_action_id", "tokenized_content_id", name="outreach_evidence_unique"
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), nullable=False
    )
    outreach_action_id: Mapped[str] = mapped_column(
        String, ForeignKey("outreach_actions.id"), nullable=False
    )
    tokenized_content_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tokenized_content.id"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String, default="supporting", nullable=False)


class EInvoiceRecord(Base):
    __tablename__ = "einvoice_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    supplier_name: Mapped[str] = mapped_column(String, nullable=False)
    supplier_tin: Mapped[str | None] = mapped_column(String)
    buyer_name: Mapped[str | None] = mapped_column(String)
    buyer_customer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("customers.id"))
    buyer_email_token: Mapped[str | None] = mapped_column(String)
    buyer_phone_token: Mapped[str | None] = mapped_column(String)
    invoice_no: Mapped[str | None] = mapped_column(String)
    issue_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str | None] = mapped_column(String)
    tax_type: Mapped[str | None] = mapped_column(String)
    tax_rate: Mapped[str | None] = mapped_column(String)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)
    # Orthogonal to `status`: document status (pending/validated) vs. payment status.
    # Set only via mark_invoice_paid(); an invoice is outstanding AR when
    # status == "validated" and paid_at is None.
    paid_at: Mapped[date | None] = mapped_column(Date)
    source_record_id: Mapped[str | None] = mapped_column(String)
    document_storage_path: Mapped[str | None] = mapped_column(String)
    uin: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class EinvoiceOutreachDraft(Base):
    __tablename__ = "einvoice_outreach_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), default=DEFAULT_TENANT_ID, nullable=False
    )
    einvoice_record_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("einvoice_records.id", ondelete="CASCADE"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String, nullable=False)
    draft_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, default="draft", nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    decided_by_user_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# Plan 3: immutable import facts. Composite foreign keys prevent cross-tenant joins.
class BusinessTenantMixin:
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), nullable=False
    )


class ImportMappingRecord(Base):
    __tablename__ = "import_mappings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "schema_name", "header_fingerprint"),
        UniqueConstraint("tenant_id", "id"),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), nullable=False
    )
    schema_name: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    column_map: Mapped[dict] = mapped_column(ObjectType, nullable=False)
    header_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BusinessImportBatch(Base):
    __tablename__ = "business_import_batches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "mapping_id"], ["import_mappings.tenant_id", "import_mappings.id"]
        ),
    )
    id: Mapped[str] = mapped_column(String, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), nullable=False
    )
    schema_name: Mapped[str] = mapped_column(String, nullable=False)
    mapping_id: Mapped[str | None] = mapped_column(String)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    imported_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    duplicate_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BusinessImportMixin(BusinessTenantMixin):
    source_record_id: Mapped[str] = mapped_column(String, nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    batch_id: Mapped[str] = mapped_column(String, nullable=False)


def _import_constraints(*extra):
    return (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "source_record_id"),
        ForeignKeyConstraint(
            ["tenant_id", "batch_id"],
            ["business_import_batches.tenant_id", "business_import_batches.id"],
        ),
        *extra,
    )


class Supplier(BusinessTenantMixin, Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "normalized_name"),
    )
    # HMAC identity, never a plaintext normalized supplier name.
    normalized_name: Mapped[str] = mapped_column(String(64), nullable=False)
    name_token: Mapped[str] = mapped_column(String, nullable=False)
    country: Mapped[str | None] = mapped_column(String(2))
    currency: Mapped[str] = mapped_column(String(3), default="MYR", nullable=False)
    verified_bank_account_token: Mapped[str | None] = mapped_column(String)


class SupplierBankChange(BusinessTenantMixin, Base):
    __tablename__ = "supplier_bank_changes"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "supplier_id"], ["suppliers.tenant_id", "suppliers.id"]),
        UniqueConstraint("tenant_id", "source_record_id"),
    )
    supplier_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    proposed_account_token: Mapped[str] = mapped_column(String, nullable=False)
    source_record_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="quarantined", nullable=False)
    callback_verified_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    maker_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    checker_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))


class BankTransaction(BusinessImportMixin, Base):
    __tablename__ = "bank_transactions"
    __table_args__ = _import_constraints(
        Index("bank_transactions_tenant_date", "tenant_id", "posted_on")
    )
    posted_on: Mapped[date] = mapped_column(Date, nullable=False)
    description_token: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    balance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    counterparty_token: Mapped[str | None] = mapped_column(String)


class Payable(BusinessImportMixin, Base):
    __tablename__ = "payables"
    __table_args__ = _import_constraints(
        ForeignKeyConstraint(["tenant_id", "supplier_id"], ["suppliers.tenant_id", "suppliers.id"]),
        Index("payables_tenant_due", "tenant_id", "due_date"),
    )
    supplier_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bill_no: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    amount_myr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String, default="open", nullable=False)


class PurchaseOrder(BusinessImportMixin, Base):
    __tablename__ = "purchase_orders"
    __table_args__ = _import_constraints(
        ForeignKeyConstraint(["tenant_id", "supplier_id"], ["suppliers.tenant_id", "suppliers.id"]),
        Index("purchase_orders_tenant_payment", "tenant_id", "expected_payment"),
    )
    supplier_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    po_no: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    amount_myr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    expected_delivery: Mapped[date] = mapped_column(Date, nullable=False)
    expected_payment: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String, default="open", nullable=False)


class InventoryItem(BusinessTenantMixin, Base):
    __tablename__ = "inventory_items"
    __table_args__ = (UniqueConstraint("tenant_id", "id"), UniqueConstraint("tenant_id", "sku"))
    sku: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    reorder_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)


class StockSnapshot(BusinessImportMixin, Base):
    __tablename__ = "stock_snapshots"
    __table_args__ = _import_constraints(
        ForeignKeyConstraint(
            ["tenant_id", "item_id"], ["inventory_items.tenant_id", "inventory_items.id"]
        ),
        UniqueConstraint("tenant_id", "item_id", "snapshot_date"),
    )
    item_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    on_hand: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)


class PayrollRun(BusinessTenantMixin, Base):
    __tablename__ = "payroll_runs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "period"),
        ForeignKeyConstraint(
            ["tenant_id", "batch_id"],
            ["business_import_batches.tenant_id", "business_import_batches.id"],
        ),
    )
    batch_id: Mapped[str] = mapped_column(String, nullable=False)
    period: Mapped[str] = mapped_column(String(7), nullable=False)
    pay_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    employer_contributions: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, default="draft", nullable=False)


class PayrollLine(BusinessImportMixin, Base):
    __tablename__ = "payroll_lines"
    __table_args__ = _import_constraints(
        ForeignKeyConstraint(
            ["tenant_id", "run_id"], ["payroll_runs.tenant_id", "payroll_runs.id"]
        ),
    )
    run_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    employee_token: Mapped[str] = mapped_column(String, nullable=False)
    gross_amount_token: Mapped[str] = mapped_column(String, nullable=False)
    gross_band: Mapped[str] = mapped_column(String, nullable=False)


class MarketingSpend(BusinessImportMixin, Base):
    __tablename__ = "marketing_spend"
    __table_args__ = _import_constraints(
        Index("marketing_spend_tenant_period", "tenant_id", "period_start")
    )
    channel: Mapped[str] = mapped_column(String, nullable=False)
    campaign_label: Mapped[str] = mapped_column(String, nullable=False)
    spend: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    attributed_revenue: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))


class MarketplacePayout(BusinessImportMixin, Base):
    __tablename__ = "marketplace_payouts"
    __table_args__ = _import_constraints(
        Index("marketplace_payouts_tenant_date", "tenant_id", "payout_date")
    )
    platform: Mapped[str] = mapped_column(String, nullable=False)
    payout_date: Mapped[date] = mapped_column(Date, nullable=False)
    gross: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    fees: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    net: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, default="expected", nullable=False)


class SalesPipeline(BusinessImportMixin, Base):
    __tablename__ = "sales_pipeline"
    __table_args__ = _import_constraints(
        Index("sales_pipeline_tenant_stage", "tenant_id", "stage"),
        ForeignKeyConstraint(["tenant_id", "customer_id"], ["customers.tenant_id", "customers.id"]),
    )
    customer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Legacy customer display/identity columns receive tokens/HMACs, never raw CSV names.
    customer_token: Mapped[str] = mapped_column(String, nullable=False)
    stage: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    expected_payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    probability: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)


class SyntheticTenantSeed(Base):
    __tablename__ = "synthetic_tenant_seeds"
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), primary_key=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    annual_revenue_myr: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    manifest: Mapped[dict] = mapped_column(ObjectType, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
