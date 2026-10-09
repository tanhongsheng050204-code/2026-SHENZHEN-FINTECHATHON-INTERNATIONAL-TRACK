from eval.run import TASKS, run_all


def test_every_evaluation_task_passes_or_names_what_it_needs():
    results = run_all()

    failed = [(r["id"], r["detail"]) for r in results if r["status"] == "fail"]
    assert failed == []
    assert all(r["detail"].startswith("needs ") for r in results if r["status"] == "skip")
    assert {r["id"] for r in results if r["kind"] == "adversarial"} == {
        f"ADV-0{n}" for n in range(1, 9)
    }


def test_tasks_are_data_with_unique_ids():
    import json

    tasks = json.loads(TASKS.read_text(encoding="utf-8"))["tasks"]
    ids = [task["id"] for task in tasks]
    assert len(ids) == len(set(ids)) >= 28
