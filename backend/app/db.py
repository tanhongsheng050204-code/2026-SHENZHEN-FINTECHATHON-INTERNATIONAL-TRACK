from collections.abc import Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()


def _sqlalchemy_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


database_url = _sqlalchemy_url(settings.database_url)
if settings.database_backend == "sqlite":
    connect_args = {"check_same_thread": False}
elif ":6543/" in database_url:
    # Supavisor transaction mode does not support prepared statements.
    connect_args = {"prepare_threshold": None}
else:
    connect_args = {}

engine = create_engine(
    database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@event.listens_for(Session, "after_begin")
def _restore_rls_context(session: Session, _transaction, connection) -> None:
    context = session.info.get("finbrain_rls_context")
    if context is None or connection.dialect.name != "postgresql":
        return
    connection.execute(
        text(
            "select set_config('app.user_id', :user_id, true), "
            "set_config('app.user_role', :user_role, true), "
            "set_config('app.actor_ref', :actor_ref, true), "
            "set_config('app.tenant_id', :tenant_id, true)"
        ),
        context,
    )
    connection.exec_driver_sql(f"set local role {context['database_role']}")


def initialize_local_schema() -> None:
    """Create zero-config SQLite tables; PostgreSQL schemas are migration-controlled."""
    if settings.database_backend != "sqlite":
        return
    from app.models import Base

    Base.metadata.create_all(engine)
    # create_all does not evolve pre-Plan-2 SQLite databases. PostgreSQL uses SQL migrations.
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS customers_tenant_id_unique "
            "ON customers(tenant_id, id)"
        )
        existing = {row[1] for row in connection.exec_driver_sql("pragma table_info(user_roles)")}
        batch_columns = {
            row[1]
            for row in connection.exec_driver_sql("pragma table_info(structured_ingestion_batches)")
        }
        if "tenant_id" not in batch_columns:
            connection.exec_driver_sql(
                "ALTER TABLE structured_ingestion_batches ADD COLUMN tenant_id TEXT NOT NULL "
                "DEFAULT '00000000-0000-0000-0000-000000000001'"
            )
        additions = {
            "job_functions": "JSON NOT NULL DEFAULT '[]'",
            "display_name": "TEXT NOT NULL DEFAULT 'Team member'",
            "email_masked": "TEXT NOT NULL DEFAULT '[restricted]'",
            "mfa_enrolled": "BOOLEAN NOT NULL DEFAULT 0",
            "last_active_at": "DATETIME",
            "session_generation": "INTEGER NOT NULL DEFAULT 0",
        }
        for column, declaration in additions.items():
            if column not in existing:
                connection.exec_driver_sql(
                    f"ALTER TABLE user_roles ADD COLUMN {column} {declaration}"
                )
        if "job_functions" not in existing:
            connection.exec_driver_sql("""
                UPDATE user_roles SET job_functions = CASE user_role
                WHEN 'owner_director' THEN '["owner"]'
                WHEN 'finance_ops' THEN '["finance"]'
                WHEN 'compliance' THEN '["compliance"]'
                ELSE '[]' END
            """)
        for table in ("token_vault", "protected_token_registry"):
            columns = {row[1] for row in connection.exec_driver_sql(f"pragma table_info({table})")}
            if "data_class" not in columns:
                connection.exec_driver_sql(
                    f"ALTER TABLE {table} ADD COLUMN data_class TEXT NOT NULL "
                    "DEFAULT 'customer_personal'"
                )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def set_rls_context(
    db: Session,
    *,
    user_id: str,
    user_role: str,
    actor_ref: str,
    tenant_id: str,
) -> None:
    """Apply verified request identity and enter the non-bypass application role."""
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    db.info["finbrain_rls_context"] = {
        "user_id": user_id,
        "user_role": user_role,
        "actor_ref": actor_ref,
        "tenant_id": tenant_id,
        "database_role": "finbrain_app",
    }
    db.execute(
        text(
            "select set_config('app.user_id', :user_id, true), "
            "set_config('app.user_role', :user_role, true), "
            "set_config('app.actor_ref', :actor_ref, true), "
            "set_config('app.tenant_id', :tenant_id, true)"
        ),
        {
            "user_id": user_id,
            "user_role": user_role,
            "actor_ref": actor_ref,
            "tenant_id": tenant_id,
        },
    )
    db.execute(text("set local role finbrain_app"))


def set_worker_context(
    db: Session,
    *,
    actor_ref: str = "vault-rotation-worker",
    tenant_id: str | None = None,
) -> None:
    """Enter the RLS-bypass-free worker role, optionally scoped to one tenant.

    tenant_id is None for genuinely global work (vault rotation); a real tenant_id
    for a worker iterating tenants one at a time (e.g. the recommendations
    scheduler). Either way the context dict must carry all four keys the
    after_begin listener's query references -- omitting tenant_id here previously
    left it out of session.info, which raised a missing-bind-parameter error the
    moment a worker's session opened a second transaction (any db.commit()
    followed by another write) against real Postgres.
    """
    if db.bind is None or db.bind.dialect.name != "postgresql":
        return
    context = {
        "user_id": "",
        "user_role": "system_worker",
        "actor_ref": actor_ref,
        "tenant_id": tenant_id or "",
    }
    db.info["finbrain_rls_context"] = {**context, "database_role": "finbrain_worker"}
    db.execute(
        text(
            "select set_config('app.user_id', :user_id, true), "
            "set_config('app.user_role', :user_role, true), "
            "set_config('app.actor_ref', :actor_ref, true), "
            "set_config('app.tenant_id', :tenant_id, true)"
        ),
        context,
    )
    db.execute(text("set local role finbrain_worker"))
