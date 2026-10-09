"""One-command local demo: a seeded SQLite database and the evaluation report.

Usage, from backend/:  uv run python -m scripts.demo_kit [database_path]

Seeds the original demo dataset (e-invoices and protected email and Telegram
records) into a fresh local SQLite file. Where Plan 3 is deployed, it also seeds
the synthetic Topic E company and copies the original fixtures into it, so every
page tells one company's story. Then it runs the evaluation harness and prints
the command that serves the API against that database.

Everything here is synthetic. Nothing calls an external service.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("database", nargs="?", type=Path, default=ROOT / "output" / "demo.db")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 10, 9))
    parser.add_argument("--report-dir", type=Path)
    args = parser.parse_args()
    database = args.database.resolve()
    report_dir = (args.report_dir or database.parent / f"{database.stem}-evidence").resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    if database.exists():
        print(f"{database} already exists; pass another path or delete it first.")
        return 1
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{database.as_posix()}",
        "ENABLE_GLINER": "false",
        "ALLOW_OFFLINE_DEMO": "true",
        "TOKEN_ROOT_SECRET": "development-only-local-demo-kit-secret",
        "TOKEN_HASH_SECRET": "development-only-demo-kit-identity-secret",
        "VAULT_MASTER_KEY": "development-only-demo-kit-wrapping-secret",
        "GEMINI_API_KEY": "",
        "MORPHEUS_API_KEY": "",
        "SENTRY_DSN": "",
        "PYTHONIOENCODING": "utf-8",
    }

    def run(*command: str):
        print("$", " ".join(command))
        result = subprocess.run(
            [sys.executable, *command],
            env=env,
            cwd=ROOT / "backend",
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        return result

    if run("-m", "seed.seed_data").returncode:
        return 1
    if (ROOT / "backend" / "seed" / "topic_e.py").exists():
        seeded = run(
            "-m",
            "seed.topic_e",
            "--as-of",
            args.as_of.isoformat(),
            "--export-dir",
            str(report_dir / "synthetic-csv"),
        )
        if seeded.returncode:
            return 1
        tenant_id = json.loads(seeded.stdout)["tenant_id"]
        if run("-m", "seed.topic_e_original_fixtures", "--tenant-id", tenant_id).returncode:
            return 1
    else:
        print("Plan 3 importer not present: the Topic E pages use the synthetic demo company.")
    if run("-m", "eval.run", str(report_dir)).returncode:
        return 1
    print()
    print("Serve the API against this database:")
    print("Use these LOCAL SYNTHETIC settings together (PowerShell):")
    for key in (
        "DATABASE_URL",
        "TOKEN_ROOT_SECRET",
        "TOKEN_HASH_SECRET",
        "VAULT_MASTER_KEY",
        "ENABLE_GLINER",
        "GEMINI_API_KEY",
        "MORPHEUS_API_KEY",
    ):
        print(f"  $env:{key}='{env[key].replace(chr(39), chr(39) * 2)}'")
    print("  uv run uvicorn app.main:app --reload")
    print("No login or membership was created; use controlled demo provisioning.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
