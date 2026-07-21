from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from server.appointment_mcp import (
    decline_reschedule,
    get_current_appointment,
    get_patient,
    get_policy,
    get_provider,
    list_appointments,
    reschedule_appointment,
    search_available_slots,
)


ROOT = Path(__file__).resolve().parent
DEFAULT_TASKS_PATH = ROOT / "tasks" / "tasks.json"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def get_task(task_id: str, tasks_path: Path) -> dict[str, Any]:
    for task in load_json(tasks_path)["tasks"]:
        if task["id"] == task_id:
            return task
    raise ValueError(f"Could not find task {task_id} in {tasks_path}")


def referral_valid(
    patient: dict[str, Any],
    specialty: str,
    service_date: str | None,
) -> bool:
    referral = (patient.get("referrals") or {}).get(specialty)
    if not referral or referral.get("status") != "active":
        return False
    expires = referral.get("expires")
    if expires and service_date:
        return date.fromisoformat(expires) >= date.fromisoformat(service_date)
    return True


def has_overlap(
    appointments: list[dict[str, Any]],
    appointment_id: str,
    patient_id: str,
    start: str,
) -> bool:
    return any(
        item.get("appointment_id") != appointment_id
        and item.get("patient_id") == patient_id
        and item.get("status") == "booked"
        and item.get("start") == start
        for item in appointments
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the deterministic appointment baseline."
    )
    parser.add_argument("--task", required=True)
    parser.add_argument(
        "--tasks-file",
        default=str(DEFAULT_TASKS_PATH),
    )
    args = parser.parse_args()

    task = get_task(args.task, Path(args.tasks_file))
    appointment_id = task["appointment_id"]
    constraints = task["constraints"]

    if task.get("policy", False):
        get_policy()

    current = get_current_appointment(appointment_id)
    patient = get_patient(current["patient_id"])
    appointments = list_appointments()

    if constraints.get("authorized_requester") is False:
        decline_reschedule(
            appointment_id,
            "The requester is not authorized to change this adult patient's appointment.",
        )
        list_appointments()
        return

    required_specialty = constraints.get("required_specialty")
    if constraints.get("referral_required", False):
        if not required_specialty or not referral_valid(
            patient,
            required_specialty,
            constraints.get("date"),
        ):
            decline_reschedule(
                appointment_id,
                "An active, unexpired referral is required.",
            )
            list_appointments()
            return

    failed_slot_ids: set[str] = set()

    while True:
        slots = search_available_slots(
            appointment_id=appointment_id,
            date=constraints.get("date"),
            weekday=constraints.get("weekday"),
            min_hour=constraints.get("min_hour", 0),
            max_hour=constraints.get("max_hour"),
            same_provider=constraints.get("same_provider", True),
        )

        valid_slots: list[dict[str, Any]] = []
        for slot in slots:
            if slot["slot_id"] in failed_slot_ids:
                continue

            provider = get_provider(slot["provider_id"])
            if required_specialty and provider["specialty"] != required_specialty:
                continue
            if constraints.get("required_location") and provider.get("location") != constraints["required_location"]:
                continue
            if constraints.get("insurance_required", False) and patient["insurance"] not in provider.get("accepted_insurance", []):
                continue
            if constraints.get("pediatric_policy", False) and patient.get("age", 999) < 18 and not provider.get("pediatric_eligible", False):
                continue
            if constraints.get("avoid_patient_overlap", False) and has_overlap(
                appointments,
                appointment_id,
                patient["patient_id"],
                slot["start"],
            ):
                continue

            valid_slots.append(slot)

        valid_slots.sort(key=lambda item: item["start"])
        objective = task.get("objective", "earliest")
        if objective == "preferred_provider_then_earliest":
            preferred_id = constraints.get("preferred_provider_id")
            preferred = [
                item for item in valid_slots
                if item["provider_id"] == preferred_id
            ]
            if preferred:
                valid_slots = preferred

        if not valid_slots:
            if constraints.get("on_no_candidate") == "noop":
                print("No qualifying slot; leaving the ledger unchanged.")
            else:
                decline_reschedule(
                    appointment_id,
                    "No valid slot satisfies all task constraints.",
                )
            list_appointments()
            return

        chosen = valid_slots[0]
        try:
            result = reschedule_appointment(
                appointment_id=appointment_id,
                new_slot_id=chosen["slot_id"],
            )
            print(json.dumps(result, indent=2))
            list_appointments()
            return
        except ValueError as exc:
            print(f"Booking failed for {chosen['slot_id']}: {exc}")
            failed_slot_ids.add(chosen["slot_id"])
            # Re-read state after the failed action and search again.
            appointments = list_appointments()


if __name__ == "__main__":
    main()
