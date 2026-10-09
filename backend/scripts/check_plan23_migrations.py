"""Apply actual SQL to a disposable local Docker PostgreSQL database.

Only use the explicitly named review container. The minimal auth bootstrap is
not hosted Supabase Auth; this checks PostgreSQL migration syntax and RLS.
"""

import os
import subprocess
from pathlib import Path

CONTAINER = os.environ.get("FINBRAIN_REVIEW_POSTGRES_CONTAINER", "duitduit-plan23-review-db")


def sql(document: str):
    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            CONTAINER,
            "psql",
            "-U",
            "postgres",
            "-d",
            "finbrain_review",
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
        ],
        input=document,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)


def main():
    sql("""
        create schema extensions;
        create schema auth;
        create role anon nologin;
        create role authenticated nologin;
        create role supabase_auth_admin nologin;
        create table auth.users(id uuid primary key);
        create function auth.jwt() returns jsonb language sql stable as $$ select '{}'::jsonb $$;
        create function auth.uid() returns uuid language sql stable as $$ select null::uuid $$;
    """)
    folder = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
    for path in sorted(folder.glob("*.sql")):
        try:
            sql("begin;\n" + path.read_text(encoding="utf-8") + "\ncommit;")
        except RuntimeError as error:
            raise RuntimeError(f"Migration failed: {path.name}\n{error}") from error
        print(f"PASS {path.name}")


if __name__ == "__main__":
    main()
