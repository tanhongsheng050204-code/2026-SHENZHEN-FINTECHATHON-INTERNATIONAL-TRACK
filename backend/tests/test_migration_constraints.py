"""The database accepts every value the code writes."""

import re
from pathlib import Path

from app.schemas import ProcessingStatus

MIGRATIONS = Path(__file__).parents[2] / "supabase" / "migrations"


def _latest_check(constraint: str) -> set[str]:
    allowed: set[str] = set()
    for path in sorted(MIGRATIONS.glob("*.sql")):
        sql = path.read_text(encoding="utf-8")
        for match in re.finditer(
            rf"add constraint {constraint}\s+check \(\w+ in \(([^)]*)\)\)", sql
        ):
            allowed = set(re.findall(r"'([^']+)'", match.group(1)))
    return allowed


def test_every_processing_status_is_allowed_by_postgres():
    allowed = _latest_check("tokenized_content_processing_status_valid")
    assert {s.value for s in ProcessingStatus} <= allowed
