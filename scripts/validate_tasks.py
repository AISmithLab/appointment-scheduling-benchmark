from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from grading.grader import solve_task


DEFAULT_TASKS_PATH = ROOT / "tasks" / "tasks.json"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--tasks-file",
        default=str(DEFAULT_TASKS_PATH),
    )
    args = parser.parse_args()

    tasks_path = Path(args.tasks_file)
    tasks = load_json(tasks_path)["tasks"]
    failed = False

    for task in tasks:
        oracle = solve_task(task)
        expected = task["expected"]
        reasons: list[str] = []

        if expected["action"] != oracle["action"]:
            reasons.append(
                f"action expected={expected['action']} solver={oracle['action']}"
            )
        if oracle["action"] == "reschedule" and expected.get("new_slot_id") != oracle["new_slot_id"]:
            reasons.append(
                f"slot expected={expected.get('new_slot_id')} solver={oracle['new_slot_id']}"
            )

        if reasons:
            failed = True
            print(f"[FAIL] {task['id']}: {'; '.join(reasons)}")
        else:
            print(
                f"[PASS] {task['id']}: {oracle['action']} "
                f"{oracle['new_slot_id'] or ''}"
            )

    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
