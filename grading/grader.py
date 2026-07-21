from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASKS_PATH = ROOT / "tasks" / "tasks.json"
SNAPSHOT_PATH = ROOT / "data" / "snapshot.json"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def find_by_id(
    items: list[dict[str, Any]],
    id_key: str,
    id_value: str,
) -> dict[str, Any]:
    for item in items:
        if item.get(id_key) == id_value:
            return item
    raise ValueError(f"Could not find {id_key}={id_value}")


def referral_is_valid(
    patient: dict[str, Any],
    specialty: str,
    service_date: str | None,
) -> bool:
    referral = (patient.get("referrals") or {}).get(specialty)
    if not referral or referral.get("status") != "active":
        return False

    expires = referral.get("expires")
    if expires is None or service_date is None:
        return True

    return date.fromisoformat(expires) >= date.fromisoformat(service_date)


def patient_has_overlap(
    initial_ledger: dict[str, Any],
    target_appointment_id: str,
    patient_id: str,
    candidate_start: str,
) -> bool:
    return any(
        item.get("appointment_id") != target_appointment_id
        and item.get("patient_id") == patient_id
        and item.get("status") == "booked"
        and item.get("start") == candidate_start
        for item in initial_ledger.get("appointments", [])
    )


def decline_or_noop(
    task: dict[str, Any],
    appointment: dict[str, Any],
    rejected: list[dict[str, str]],
) -> dict[str, Any]:
    action = task.get("constraints", {}).get("on_no_candidate", "decline")
    if action not in {"decline", "noop"}:
        raise ValueError(f"Unsupported no-candidate action: {action}")

    return {
        "action": action,
        "original_slot_id": appointment["slot_id"],
        "new_slot_id": None,
        "valid_candidates": [],
        "rejected": rejected,
    }


def solve_task(
    task: dict[str, Any],
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute deterministic ground truth from hidden task constraints."""
    if snapshot is None:
        snapshot = load_json(SNAPSHOT_PATH)

    appointment_id = task["appointment_id"]
    initial_ledger = task["initial_ledger"]
    appointment = find_by_id(
        initial_ledger["appointments"],
        "appointment_id",
        appointment_id,
    )
    patient = find_by_id(
        snapshot["patients"],
        "patient_id",
        appointment["patient_id"],
    )
    constraints = task["constraints"]
    rejected: list[dict[str, str]] = []

    if constraints.get("authorized_requester") is False:
        return {
            "action": "decline",
            "original_slot_id": appointment["slot_id"],
            "new_slot_id": None,
            "valid_candidates": [],
            "rejected": [{"slot_id": "*", "reason": "unauthorized requester"}],
        }

    required_specialty = constraints.get("required_specialty")
    if constraints.get("referral_required", False):
        if not required_specialty:
            raise ValueError("referral_required needs required_specialty")
        if not referral_is_valid(
            patient,
            required_specialty,
            constraints.get("date"),
        ):
            return {
                "action": "decline",
                "original_slot_id": appointment["slot_id"],
                "new_slot_id": None,
                "valid_candidates": [],
                "rejected": [{"slot_id": "*", "reason": "missing or expired referral"}],
            }

    candidates: list[dict[str, Any]] = []

    for slot in snapshot["slots"]:
        reason: str | None = None
        start = datetime.fromisoformat(slot["start"])
        provider = find_by_id(
            snapshot["providers"],
            "provider_id",
            slot["provider_id"],
        )

        if not slot.get("available", False):
            reason = "unavailable"
        elif constraints.get("exclude_transient_slots") and slot.get("fail_first_booking"):
            reason = "deterministic race-loss slot"
        elif constraints.get("date") and start.date().isoformat() != constraints["date"]:
            reason = "wrong date"
        elif constraints.get("weekday") and start.strftime("%A").lower() != constraints["weekday"].lower():
            reason = "wrong weekday"
        elif start.hour < constraints.get("min_hour", 0):
            reason = "too early"
        elif constraints.get("max_hour") is not None and start.hour >= constraints["max_hour"]:
            reason = "too late"
        elif constraints.get("same_provider", True) and slot["provider_id"] != appointment["provider_id"]:
            reason = "wrong provider"
        elif required_specialty and provider["specialty"] != required_specialty:
            reason = "wrong specialty"
        elif constraints.get("required_location") and provider.get("location") != constraints["required_location"]:
            reason = "wrong location"
        elif constraints.get("insurance_required", False) and patient["insurance"] not in provider.get("accepted_insurance", []):
            reason = "insurance mismatch"
        elif constraints.get("pediatric_policy", False) and patient.get("age", 999) < 18 and not provider.get("pediatric_eligible", False):
            reason = "provider not pediatric eligible"
        elif constraints.get("avoid_patient_overlap", False) and patient_has_overlap(
            initial_ledger,
            appointment_id,
            patient["patient_id"],
            slot["start"],
        ):
            reason = "patient overlap"

        if reason is None:
            candidates.append({**slot, "provider": provider})
        else:
            rejected.append({"slot_id": slot["slot_id"], "reason": reason})

    if not candidates:
        return decline_or_noop(task, appointment, rejected)

    objective = task.get("objective", "earliest")
    candidates.sort(key=lambda item: item["start"])

    if objective == "earliest":
        chosen = candidates[0]
    elif objective == "preferred_provider_then_earliest":
        preferred_provider_id = constraints.get("preferred_provider_id")
        preferred = [
            item for item in candidates
            if item["provider_id"] == preferred_provider_id
        ]
        chosen = preferred[0] if preferred else candidates[0]
    else:
        raise ValueError(f"Unsupported objective: {objective}")

    return {
        "action": "reschedule",
        "original_slot_id": appointment["slot_id"],
        "new_slot_id": chosen["slot_id"],
        "valid_candidates": [item["slot_id"] for item in candidates],
        "rejected": rejected,
    }


def grade(
    task: dict[str, Any],
    run_dir: str | Path,
) -> dict[str, Any]:
    run_path = Path(run_dir)
    ledger_path = run_path / "ledger.json"
    calls_path = run_path / "tool_calls.json"

    if not ledger_path.exists():
        return {
            "task_id": task["id"],
            "task_name": task["name"],
            "suite": task.get("suite", ""),
            "passed": False,
            "reasons": [f"Missing final ledger: {ledger_path}"],
            "final_slot_id": None,
            "n_tool_calls": 0,
            "n_failed_tool_calls": 0,
        }

    ledger = load_json(ledger_path)
    snapshot = load_json(SNAPSHOT_PATH)
    oracle = solve_task(task, snapshot)

    appointment_id = task["appointment_id"]
    appointment = find_by_id(
        ledger["appointments"],
        "appointment_id",
        appointment_id,
    )
    initial_appointment = find_by_id(
        task["initial_ledger"]["appointments"],
        "appointment_id",
        appointment_id,
    )

    reasons: list[str] = []
    expected = task.get("expected", {})

    if expected.get("action") != oracle["action"]:
        reasons.append("Task metadata disagrees with the deterministic solver.")
    if oracle["action"] == "reschedule" and expected.get("new_slot_id") != oracle["new_slot_id"]:
        reasons.append("Task expected slot disagrees with the deterministic solver.")

    if oracle["action"] == "reschedule":
        expected_slot = oracle["new_slot_id"]
        if appointment["slot_id"] != expected_slot:
            reasons.append(
                f"Expected final slot {expected_slot}, but found {appointment['slot_id']}."
            )

        history = ledger.get("reschedule_history", [])
        if not any(
            entry.get("appointment_id") == appointment_id
            and entry.get("new_slot_id") == expected_slot
            for entry in history
        ):
            reasons.append("The correct reschedule was not recorded in reschedule_history.")

    elif oracle["action"] == "decline":
        if appointment != initial_appointment:
            reasons.append("The target appointment changed even though the request should have been declined.")
        if not any(
            entry.get("appointment_id") == appointment_id
            for entry in ledger.get("declines", [])
        ):
            reasons.append("No decline was recorded.")

    elif oracle["action"] == "noop":
        if ledger.get("appointments", []) != task["initial_ledger"].get("appointments", []):
            reasons.append("The appointment ledger changed even though a true no-op was required.")
        if ledger.get("reschedule_history", []) != task["initial_ledger"].get("reschedule_history", []):
            reasons.append("A reschedule history entry was created during a no-op task.")
        if ledger.get("declines", []) != task["initial_ledger"].get("declines", []):
            reasons.append("A decline was recorded even though a true no-op was required.")

    initial_others = sorted(
        [
            item for item in task["initial_ledger"]["appointments"]
            if item["appointment_id"] != appointment_id
        ],
        key=lambda item: item["appointment_id"],
    )
    final_others = sorted(
        [
            item for item in ledger["appointments"]
            if item["appointment_id"] != appointment_id
        ],
        key=lambda item: item["appointment_id"],
    )
    if initial_others != final_others:
        reasons.append("An unrelated appointment was modified.")

    tool_calls: list[dict[str, Any]] = []
    if calls_path.exists():
        tool_calls = load_json(calls_path)

    n_failed_tool_calls = sum(1 for call in tool_calls if "error" in call)
    tool_names = [call.get("tool") for call in tool_calls]

    if task.get("policy", False) and "get_policy" not in tool_names:
        reasons.append("The policy was in force, but get_policy was not called.")
    if task.get("require_failed_tool_call", False) and n_failed_tool_calls < 1:
        reasons.append("The recovery task required encountering and recovering from a tool failure.")

    return {
        "task_id": task["id"],
        "task_name": task["name"],
        "suite": task.get("suite", ""),
        "skill": task.get("skill", ""),
        "expected_action": oracle["action"],
        "expected_slot_id": oracle["new_slot_id"],
        "final_slot_id": appointment["slot_id"],
        "passed": len(reasons) == 0,
        "reasons": reasons,
        "n_tool_calls": len(tool_calls),
        "n_failed_tool_calls": n_failed_tool_calls,
        "valid_candidates": oracle["valid_candidates"],
    }


def get_task(task_id: str, tasks_path: Path) -> dict[str, Any]:
    tasks = load_json(tasks_path)["tasks"]
    return find_by_id(tasks, "id", task_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Grade one appointment benchmark run.")
    parser.add_argument("--task", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--tasks-file",
        default=str(DEFAULT_TASKS_PATH),
        help="Task JSON file containing the requested task.",
    )
    args = parser.parse_args()

    task = get_task(args.task, Path(args.tasks_file))
    result = grade(task, args.run_dir)
    result_path = Path(args.run_dir) / "result.json"
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    mark = "PASS" if result["passed"] else "FAIL"
    print(f"{result['task_id']} {mark}")
    print(f"Expected slot: {result['expected_slot_id']}")
    print(f"Final slot: {result['final_slot_id']}")
    print(f"Tool calls: {result['n_tool_calls']}")
    for reason in result["reasons"]:
        print(f"- {reason}")
    print(f"Result saved to: {result_path}")


if __name__ == "__main__":
    main()
