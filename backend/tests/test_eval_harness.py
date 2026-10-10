from eval.run import TASKS, run_all


def test_every_evaluation_task_passes_or_names_what_it_needs():
    results = run_all()

    failed = [(r["id"], r["detail"]) for r in results if r["status"] == "fail"]
    assert failed == []
    assert all(r["detail"].startswith("needs ") for r in results if r["status"] == "skip")
    assert {r["id"] for r in results if r["kind"] == "adversarial"} == {
        f"ADV-{n:02}" for n in (*range(1, 9), *range(10, 16))
    } | {
        "A-trick-typed", "A-trick-spoken", "A-role-limits", "A-no-confirm",
        "A-provider-outage", "A-no-words-in-audit",
    }
    assert all(r["status"] == "pass" for r in results if r["id"].startswith("A-"))
    # The Oct 10 attack tests have no prerequisites, so they must all pass.
    assert all(
        r["status"] == "pass" for r in results if r["id"] in {f"ADV-{n}" for n in range(10, 16)}
    )


def test_tasks_are_data_with_unique_ids():
    import json

    tasks = json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]
    ids = [task["id"] for task in tasks]
    assert len(ids) == len(set(ids)) == 42
    assert {f"F{n:02}" for n in range(1, 23)} | {f"ADV-{n:02}" for n in range(1, 9)} <= set(ids)
