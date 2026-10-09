"""One-command local demo: a seeded SQLite database and the evaluation report.

Usage, from backend/:  uv run python -m scripts.demo_kit [database_path]

Seeds the original demo dataset (e-invoices and protected email and Telegram
records) into a fresh local SQLite file. Where Plan 3 is deployed, it also seeds
the synthetic Topic E company and copies the original fixtures into it, so every
page tells one company's story. Then it runs the evaluation harness and prints
the command that serves the API against that database.

Everything here is synthetic. Nothing calls an external service.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    database = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "output" / "demo.db"
    database.parent.mkdir(parents=True, exist_ok=True)
    if database.exists():
        print(f"{database} already exists; pass another path or delete it first.")
        return 1
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{database.as_posix()}",
        "ENABLE_GLINER": "false",
        "ALLOW_OFFLINE_DEMO": "true",
        "TOKEN_ROOT_SECRET": os.environ.get(
            "TOKEN_ROOT_SECRET", "development-only-local-demo-kit-secret"
        ),
    }

    def run(*args: str) -> int:
        print("$", " ".join(args))
        return subprocess.call([sys.executable, *args], env=env, cwd=ROOT / "backend")

    if run("-m", "seed.seed_data"):
        return 1
    if (ROOT / "backend" / "seed" / "topic_e.py").exists():
        if run("-m", "seed.topic_e"):
            return 1
        print("Copy the original fixtures into the synthetic tenant printed above with:")
        print("  python -m seed.topic_e_original_fixtures --tenant-id <tenant_id>")
    else:
        print("Plan 3 importer not present: the Topic E pages use the synthetic demo company.")
    run("-m", "eval.run", str(ROOT / "output"))
    print()
    print("Serve the API against this database:")
    print(f"  DATABASE_URL=sqlite:///{database.as_posix()} uv run uvicorn app.main:app --reload")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
