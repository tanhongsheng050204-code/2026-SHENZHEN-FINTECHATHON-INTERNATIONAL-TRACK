"""Run the evaluation tasks and write output/eval-report.md and .json.

Usage, from backend/:  python -m eval.run [output_dir]
Exit status is 1 if any task fails; skipped tasks name what they need and do not fail.
"""

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("ENABLE_GLINER", "false")
os.environ.setdefault("ALLOW_OFFLINE_DEMO", "true")
os.environ.setdefault("TOKEN_ROOT_SECRET", "eval-only-secret-that-is-longer-than-32-chars")
os.environ["GEMINI_API_KEY"] = ""
os.environ["MORPHEUS_API_KEY"] = ""

TASKS = Path(__file__).with_name("tasks.json")


def run_all() -> list[dict]:
    from eval.checks import CHECKS

    results = []
    for task in json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]:
        started = time.perf_counter()
        try:
            status, detail = CHECKS[task["check"]](**task.get("args", {}))
        except Exception as error:  # noqa: BLE001 - a crashing checker is a failed task
            status, detail = "fail", f"{type(error).__name__}: {error}"
        results.append(
            {
                "id": task["id"],
                "kind": task["kind"],
                "standard": task.get("standard"),
                "title": task["title"],
                "status": status,
                "detail": detail,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                "mode": "offline",
            }
        )
    return results


def _markdown(results: list[dict]) -> str:
    counts = {s: sum(r["status"] == s for r in results) for s in ("pass", "fail", "skip")}
    lines = [
        "# DuitDuit evaluation report",
        "",
        f"{counts['pass']} passed, {counts['fail']} failed, {counts['skip']} skipped "
        f"of {len(results)} tasks. Offline: no network and no model provider.",
        "",
        "| Task | Kind | Standard | Result | Detail |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in results:
        detail = r["detail"].replace("|", "\\|")
        lines.append(
            f"| {r['id']} {r['title']} | {r['kind']} | {r['standard'] or ''} "
            f"| {r['status']} | {detail} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "output"
    out.mkdir(parents=True, exist_ok=True)
    results = run_all()
    (out / "eval-report.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    report = _markdown(results)
    (out / "eval-report.md").write_text(report, encoding="utf-8")
    print(report)
    return 1 if any(r["status"] == "fail" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
