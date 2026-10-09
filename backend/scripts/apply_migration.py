"""Apply one SQL migration file to the configured database, all or nothing.

Usage, from backend/:
    python -m scripts.apply_migration ../supabase/migrations/<file>.sql --dry-run
    python -m scripts.apply_migration ../supabase/migrations/<file>.sql

The whole file runs inside one transaction. With --dry-run it is rolled back at the
end, so you see whether it would succeed without changing anything. Without it, it
is committed only if every statement succeeded; any error leaves the database as it
was. A file's own top-level BEGIN; and COMMIT; lines are removed so this script
controls the transaction.
"""

import argparse
import re
from pathlib import Path

import psycopg

from app.config import get_settings

_TRANSACTION_LINE = re.compile(r"^\s*(begin|commit)\s*;\s*$", re.IGNORECASE | re.MULTILINE)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    url = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    if not url.startswith(("postgresql://", "postgres://")):
        raise SystemExit("DATABASE_URL in backend/.env is not a PostgreSQL connection string.")
    script = _TRANSACTION_LINE.sub("", args.file.read_text(encoding="utf-8"))

    with psycopg.connect(url, autocommit=False) as connection:
        try:
            connection.execute(script)
        except psycopg.Error as error:
            connection.rollback()
            print(f"FAILED, nothing was changed: {error}")
            return 1
        if args.dry_run:
            connection.rollback()
            print(f"DRY RUN OK: {args.file.name} applies cleanly. Nothing was changed.")
        else:
            connection.commit()
            print(f"APPLIED: {args.file.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
