from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SNAPSHOT = ROOT / "data" / "snapshot.json"
DEFAULT_LEDGER = ROOT / "runs" / "local" / "ledger.json"
DEFAULT_CALLS_LOG = ROOT / "runs" / "local" / "tool_calls.json"
DEFAULT_POLICY = ROOT / "tasks" / "policy.md"


def _path_from_env(name: str, default: Path) -> Path:
    return Path(os.environ.get(name, str(default))).resolve()


def _snapshot_path() -> Path:
    return _path_from_env("APPOINTMENT_SNAPSHOT", DEFAULT_SNAPSHOT)


def _ledger_path() -> Path:
    return _path_from_env("APPOINTMENT_LEDGER", DEFAULT_LEDGER)


def _calls_path() -> Path:
    return _path_from_env("APPOINTMENT_CALLS_LOG", DEFAULT_CALLS_LOG)


def _policy_path() -> Path:
    return _path_from_env("APPOINTMENT_POLICY", DEFAULT_POLICY)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def _find(
    items: list[dict[str, Any]],
    key: str,
    value: str,
) -> dict[str, Any]:
    for item in items:
        if item.get(key) == value:
            return item
    raise ValueError(f"Could not find {key}={value}")


def _log_call(
    tool: str,
    arguments: dict[str, Any],
    result: Any = None,
    error: str | None = None,
) -> None:
    path = _calls_path()
    calls: list[dict[str, Any]]

    if path.exists():
        try:
            calls = _load_json(path)
        except (json.JSONDecodeError, OSError):
            calls = []
    else:
        calls = []

    entry: dict[str, Any] = {"tool": tool, "arguments": arguments}
    if error is None:
        entry["result"] = result
    else:
        entry["error"] = error

    calls.append(entry)
    _save_json(path, calls)


def _run_logged(
    tool: str,
    arguments: dict[str, Any],
    operation: Callable[[], Any],
) -> Any:
    try:
        result = operation()
    except Exception as exc:
        _log_call(tool, arguments, error=str(exc))
        raise

    _log_call(tool, arguments, result=result)
    return result


def get_policy() -> str:
    """Return the synthetic clinic policy that governs hard-suite tasks."""
    arguments: dict[str, Any] = {}

    def operation() -> str:
        return _policy_path().read_text(encoding="utf-8")

    return _run_logged("get_policy", arguments, operation)


def get_current_appointment(appointment_id: str) -> dict[str, Any]:
    """Return one currently booked appointment."""
    arguments = {"appointment_id": appointment_id}

    def operation() -> dict[str, Any]:
        ledger = _load_json(_ledger_path())
        return _find(ledger["appointments"], "appointment_id", appointment_id)

    return _run_logged("get_current_appointment", arguments, operation)


def get_patient(patient_id: str) -> dict[str, Any]:
    """Return insurance, age, referrals, and authorization metadata."""
    arguments = {"patient_id": patient_id}

    def operation() -> dict[str, Any]:
        snapshot = _load_json(_snapshot_path())
        return _find(snapshot["patients"], "patient_id", patient_id)

    return _run_logged("get_patient", arguments, operation)


def get_provider(provider_id: str) -> dict[str, Any]:
    """Return provider specialty, insurance, location, and eligibility."""
    arguments = {"provider_id": provider_id}

    def operation() -> dict[str, Any]:
        snapshot = _load_json(_snapshot_path())
        return _find(snapshot["providers"], "provider_id", provider_id)

    return _run_logged("get_provider", arguments, operation)


def _public_slot(slot: dict[str, Any]) -> dict[str, Any]:
    """Hide internal simulation flags from agent-visible search results."""
    return {
        key: value
        for key, value in slot.items()
        if key not in {"fail_first_booking", "failure_triggered"}
    }


def search_available_slots(
    appointment_id: str,
    date: str | None = None,
    weekday: str | None = None,
    min_hour: int = 0,
    max_hour: int | None = None,
    same_provider: bool = True,
) -> list[dict[str, Any]]:
    """
    Search by schedule constraints only.

    Specialty, insurance, location, referral, pediatric eligibility,
    authorization, and patient-overlap rules are intentionally not
    filtered here. Agents must inspect the relevant records and policy.
    """
    arguments = {
        "appointment_id": appointment_id,
        "date": date,
        "weekday": weekday,
        "min_hour": min_hour,
        "max_hour": max_hour,
        "same_provider": same_provider,
    }

    def operation() -> list[dict[str, Any]]:
        snapshot = _load_json(_snapshot_path())
        ledger = _load_json(_ledger_path())
        appointment = _find(
            ledger["appointments"],
            "appointment_id",
            appointment_id,
        )

        results: list[dict[str, Any]] = []
        for slot in snapshot["slots"]:
            if not slot.get("available", False):
                continue
            if same_provider and slot["provider_id"] != appointment["provider_id"]:
                continue

            start = datetime.fromisoformat(slot["start"])
            if date is not None and start.date().isoformat() != date:
                continue
            if weekday is not None and start.strftime("%A").lower() != weekday.lower():
                continue
            if start.hour < min_hour:
                continue
            if max_hour is not None and start.hour >= max_hour:
                continue

            results.append(_public_slot(slot))

        results.sort(key=lambda item: item["start"])
        return results

    return _run_logged("search_available_slots", arguments, operation)


def reschedule_appointment(
    appointment_id: str,
    new_slot_id: str,
) -> dict[str, Any]:
    """
    Move an appointment to an available slot.

    The system enforces availability and exact-start overlap. Domain
    constraints remain the responsibility of the agent and grader.
    """
    arguments = {"appointment_id": appointment_id, "new_slot_id": new_slot_id}

    def operation() -> dict[str, Any]:
        snapshot_path = _snapshot_path()
        ledger_path = _ledger_path()
        snapshot = _load_json(snapshot_path)
        ledger = _load_json(ledger_path)

        appointment = _find(
            ledger["appointments"],
            "appointment_id",
            appointment_id,
        )
        new_slot = _find(snapshot["slots"], "slot_id", new_slot_id)

        if not new_slot.get("available", False):
            raise ValueError(f"Slot {new_slot_id} is not available.")

        # Deterministic race-condition fixture: the first booking attempt
        # loses the slot and persists that state in the per-run snapshot.
        if (
            new_slot.get("fail_first_booking", False)
            and not new_slot.get("failure_triggered", False)
        ):
            new_slot["failure_triggered"] = True
            new_slot["available"] = False
            _save_json(snapshot_path, snapshot)
            raise ValueError(
                f"Slot {new_slot_id} became unavailable before booking. "
                "Search again for the next valid option."
            )

        for other in ledger["appointments"]:
            if other["appointment_id"] == appointment_id:
                continue
            if (
                other.get("patient_id") == appointment.get("patient_id")
                and other.get("start") == new_slot["start"]
                and other.get("status") == "booked"
            ):
                raise ValueError(
                    "The patient already has an overlapping appointment."
                )

        old_slot_id = appointment["slot_id"]
        old_start = appointment["start"]
        old_provider_id = appointment["provider_id"]

        appointment["slot_id"] = new_slot["slot_id"]
        appointment["provider_id"] = new_slot["provider_id"]
        appointment["start"] = new_slot["start"]
        appointment["status"] = "booked"

        ledger.setdefault("reschedule_history", []).append(
            {
                "appointment_id": appointment_id,
                "old_slot_id": old_slot_id,
                "new_slot_id": new_slot_id,
                "old_start": old_start,
                "new_start": new_slot["start"],
                "old_provider_id": old_provider_id,
                "new_provider_id": new_slot["provider_id"],
            }
        )

        new_slot["available"] = False
        for slot in snapshot["slots"]:
            if slot["slot_id"] == old_slot_id:
                slot["available"] = True
                break

        _save_json(ledger_path, ledger)
        _save_json(snapshot_path, snapshot)
        return {"status": "success", "appointment": dict(appointment)}

    return _run_logged("reschedule_appointment", arguments, operation)


def decline_reschedule(
    appointment_id: str,
    reason: str,
) -> dict[str, Any]:
    """Record that the request was safely declined."""
    arguments = {"appointment_id": appointment_id, "reason": reason}

    def operation() -> dict[str, Any]:
        ledger_path = _ledger_path()
        ledger = _load_json(ledger_path)
        _find(ledger["appointments"], "appointment_id", appointment_id)

        decline = {"appointment_id": appointment_id, "reason": reason}
        ledger.setdefault("declines", []).append(decline)
        _save_json(ledger_path, ledger)
        return {"status": "declined", "decline": decline}

    return _run_logged("decline_reschedule", arguments, operation)


def list_appointments() -> list[dict[str, Any]]:
    """Return all appointments in the current run ledger."""
    arguments: dict[str, Any] = {}

    def operation() -> list[dict[str, Any]]:
        ledger = _load_json(_ledger_path())
        return ledger["appointments"]

    return _run_logged("list_appointments", arguments, operation)
