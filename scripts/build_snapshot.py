from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "data" / "snapshot.json"


def stable_int(*parts: str) -> int:
    text = "|".join(parts).encode("utf-8")
    return int(hashlib.sha256(text).hexdigest()[:12], 16)


def controlled_records() -> dict[str, list[dict[str, Any]]]:
    """Hand-designed fixtures for easy and hard benchmark tasks."""
    patients = [
        {
            "patient_id": "P001",
            "name": "Alex Morgan",
            "insurance": "BlueShield",
            "age": 26,
            "preferred_location": "Downtown",
            "authorized_proxies": [],
            "referrals": {
                "cardiology": {
                    "status": "expired",
                    "expires": "2026-09-01",
                },
                "neurology": {
                    "status": "none",
                    "expires": None,
                },
            },
        },
        {
            "patient_id": "P002",
            "name": "Jamie Rivera",
            "insurance": "Aetna",
            "age": 34,
            "preferred_location": "Downtown",
            "authorized_proxies": [],
            "referrals": {},
        },
        {
            "patient_id": "P003",
            "name": "Taylor Kim",
            "insurance": "UnitedHealthcare",
            "age": 42,
            "preferred_location": "Uptown",
            "authorized_proxies": [],
            "referrals": {
                "neurology": {
                    "status": "active",
                    "expires": "2026-12-31",
                }
            },
        },
        {
            "patient_id": "P004",
            "name": "Jordan Patel",
            "insurance": "Medicare",
            "age": 68,
            "preferred_location": "North Clinic",
            "authorized_proxies": [],
            "referrals": {
                "cardiology": {
                    "status": "active",
                    "expires": "2026-12-31",
                }
            },
        },
        {
            "patient_id": "P005",
            "name": "Casey Nguyen",
            "insurance": "BlueShield",
            "age": 15,
            "preferred_location": "Downtown",
            "authorized_proxies": ["PARENT-001"],
            "referrals": {},
        },
        {
            "patient_id": "P006",
            "name": "Riley Chen",
            "insurance": "Aetna",
            "age": 29,
            "preferred_location": "Uptown",
            "authorized_proxies": [],
            "referrals": {},
        },
    ]

    providers = [
        {
            "provider_id": "D001",
            "name": "Dr. Lee",
            "specialty": "dermatology",
            "accepted_insurance": ["BlueShield", "Aetna"],
            "location": "Downtown",
            "pediatric_eligible": False,
        },
        {
            "provider_id": "D002",
            "name": "Dr. Patel",
            "specialty": "dermatology",
            "accepted_insurance": ["Aetna"],
            "location": "Downtown",
            "pediatric_eligible": True,
        },
        {
            "provider_id": "D003",
            "name": "Dr. Gomez",
            "specialty": "dermatology",
            "accepted_insurance": ["BlueShield", "UnitedHealthcare"],
            "location": "Uptown",
            "pediatric_eligible": True,
        },
        {
            "provider_id": "D004",
            "name": "Dr. Chen",
            "specialty": "cardiology",
            "accepted_insurance": ["BlueShield", "Medicare"],
            "location": "Downtown",
            "pediatric_eligible": False,
        },
        {
            "provider_id": "D005",
            "name": "Dr. Williams",
            "specialty": "orthopedics",
            "accepted_insurance": ["UnitedHealthcare", "Medicare"],
            "location": "North Clinic",
            "pediatric_eligible": False,
        },
        {
            "provider_id": "D006",
            "name": "Dr. Nguyen",
            "specialty": "primary_care",
            "accepted_insurance": ["BlueShield", "Aetna", "Medicare"],
            "location": "Downtown",
            "pediatric_eligible": True,
        },
        {
            "provider_id": "D007",
            "name": "Dr. Brown",
            "specialty": "neurology",
            "accepted_insurance": ["Aetna", "UnitedHealthcare"],
            "location": "Uptown",
            "pediatric_eligible": False,
        },
        {
            "provider_id": "D008",
            "name": "Dr. Garcia",
            "specialty": "ophthalmology",
            "accepted_insurance": ["BlueShield", "Medicare"],
            "location": "North Clinic",
            "pediatric_eligible": True,
        },
    ]

    slots: list[dict[str, Any]] = [
        # Easy-suite fixtures.
        {"slot_id": "S090", "provider_id": "D001", "start": "2026-09-10T09:00:00", "available": False},
        {"slot_id": "S101", "provider_id": "D001", "start": "2026-09-14T10:00:00", "available": True},
        {"slot_id": "S102", "provider_id": "D001", "start": "2026-09-14T15:00:00", "available": True},
        {"slot_id": "S103", "provider_id": "D001", "start": "2026-09-15T15:00:00", "available": True},
        {"slot_id": "S201", "provider_id": "D002", "start": "2026-09-21T14:30:00", "available": True},
        {"slot_id": "S202", "provider_id": "D003", "start": "2026-09-21T15:30:00", "available": True},
        {"slot_id": "S301", "provider_id": "D004", "start": "2026-09-22T14:15:00", "available": True},
        {"slot_id": "S302", "provider_id": "D003", "start": "2026-09-22T15:00:00", "available": True},
        {"slot_id": "S401", "provider_id": "D003", "start": "2026-09-23T14:00:00", "available": False},
        {"slot_id": "S402", "provider_id": "D003", "start": "2026-09-23T15:00:00", "available": True},
        {"slot_id": "S500", "provider_id": "D002", "start": "2026-09-24T13:30:00", "available": True},
        {"slot_id": "S501", "provider_id": "D003", "start": "2026-09-24T14:30:00", "available": True},
        {"slot_id": "S502", "provider_id": "D001", "start": "2026-09-24T15:00:00", "available": True},

        # Hard-suite original booked slots.
        {"slot_id": "SH100", "provider_id": "D001", "start": "2026-10-20T10:00:00", "available": False},
        {"slot_id": "SH200", "provider_id": "D001", "start": "2026-10-20T10:00:00", "available": False},
        {"slot_id": "SH300", "provider_id": "D004", "start": "2026-10-30T10:00:00", "available": False},
        {"slot_id": "SH400", "provider_id": "D001", "start": "2026-10-30T10:00:00", "available": False},
        {"slot_id": "SH500", "provider_id": "D001", "start": "2026-10-30T10:00:00", "available": False},
        {"slot_id": "SH599", "provider_id": "D006", "start": "2026-10-16T14:00:00", "available": False},
        {"slot_id": "SH600", "provider_id": "D001", "start": "2026-10-30T10:00:00", "available": False},
        {"slot_id": "SH700", "provider_id": "D001", "start": "2026-10-30T10:00:00", "available": False},
        {"slot_id": "SH800", "provider_id": "D003", "start": "2026-10-30T10:00:00", "available": False},

        # H01: policy-defined early afternoon. D001 is outside the window;
        # D002 is earlier but out of network; D003 is valid.
        {"slot_id": "SH101", "provider_id": "D001", "start": "2026-10-13T15:00:00", "available": True},
        {"slot_id": "SH102", "provider_id": "D002", "start": "2026-10-13T13:15:00", "available": True},
        {"slot_id": "SH103", "provider_id": "D003", "start": "2026-10-13T14:00:00", "available": True},

        # H02: only another provider is open, so the correct outcome is no-op.
        {"slot_id": "SH201", "provider_id": "D003", "start": "2026-10-17T10:00:00", "available": True},

        # H03: a valid cardiology slot exists, but the referral is expired.
        {"slot_id": "SH301", "provider_id": "D004", "start": "2026-10-14T10:00:00", "available": True},

        # H04: the first slot deterministically disappears on first booking.
        {"slot_id": "SH401", "provider_id": "D001", "start": "2026-10-15T14:00:00", "available": True, "fail_first_booking": True},
        {"slot_id": "SH402", "provider_id": "D001", "start": "2026-10-15T15:00:00", "available": True},

        # H05: SH501 overlaps A599; SH502 is the next safe option.
        {"slot_id": "SH501", "provider_id": "D001", "start": "2026-10-16T14:00:00", "available": True},
        {"slot_id": "SH502", "provider_id": "D001", "start": "2026-10-16T15:00:00", "available": True},

        # H06: one wrong location, one insurance mismatch, then valid.
        {"slot_id": "SH601", "provider_id": "D003", "start": "2026-10-19T13:30:00", "available": True},
        {"slot_id": "SH602", "provider_id": "D002", "start": "2026-10-19T14:00:00", "available": True},
        {"slot_id": "SH603", "provider_id": "D001", "start": "2026-10-19T15:00:00", "available": True},

        # H07: slots exist, but requester is not authorized.
        {"slot_id": "SH701", "provider_id": "D001", "start": "2026-10-20T14:00:00", "available": True},
        {"slot_id": "SH702", "provider_id": "D003", "start": "2026-10-20T15:00:00", "available": True},

        # H08: D001 is not pediatric-eligible; D003 is valid.
        {"slot_id": "SH801", "provider_id": "D001", "start": "2026-10-21T13:00:00", "available": True},
        {"slot_id": "SH802", "provider_id": "D003", "start": "2026-10-21T14:00:00", "available": True},
    ]

    return {"patients": patients, "providers": providers, "slots": slots}


def background_slots(providers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic background availability that does not alter fixtures."""
    slots: list[dict[str, Any]] = []
    start_date = date(2026, 9, 25)
    hours = [9, 10, 11, 14, 15, 16]
    slot_number = 1000

    for day_offset in range(14):
        day = start_date + timedelta(days=day_offset)
        for provider in providers:
            provider_id = provider["provider_id"]
            for hour in hours:
                token = stable_int(provider_id, day.isoformat(), str(hour))
                available = token % 10 < 7
                start = datetime.combine(day, time(hour=hour))
                slots.append(
                    {
                        "slot_id": f"S{slot_number}",
                        "provider_id": provider_id,
                        "start": start.isoformat(),
                        "available": available,
                    }
                )
                slot_number += 1

    return slots


def build_snapshot() -> dict[str, Any]:
    snapshot = controlled_records()
    snapshot["slots"].extend(background_slots(snapshot["providers"]))
    return snapshot


def main() -> None:
    snapshot = build_snapshot()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(snapshot, file, indent=2)

    print(f"Wrote {len(snapshot['patients'])} patients")
    print(f"Wrote {len(snapshot['providers'])} providers")
    print(f"Wrote {len(snapshot['slots'])} slots")
    print(f"Snapshot: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
