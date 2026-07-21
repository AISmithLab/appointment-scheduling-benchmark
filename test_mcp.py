from __future__ import annotations

import asyncio
import copy
import json
import os
import shutil
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parent
TASKS_PATH = ROOT / "tasks" / "tasks.json"
SNAPSHOT_PATH = ROOT / "data" / "snapshot.json"
SERVER_PATH = ROOT / "server" / "appointment_server.py"
RUN_DIR = ROOT / "runs" / "mcp_smoke_test"


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


async def main() -> None:
    tasks = json.loads(
        TASKS_PATH.read_text(encoding="utf-8")
    )["tasks"]
    task = next(task for task in tasks if task["id"] == "T01")

    snapshot_path = RUN_DIR / "snapshot.json"
    ledger_path = RUN_DIR / "ledger.json"
    calls_path = RUN_DIR / "tool_calls.json"

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SNAPSHOT_PATH, snapshot_path)

    save_json(ledger_path, copy.deepcopy(task["initial_ledger"]))
    save_json(calls_path, [])

    env = os.environ.copy()
    env["APPOINTMENT_SNAPSHOT"] = str(snapshot_path.resolve())
    env["APPOINTMENT_LEDGER"] = str(ledger_path.resolve())
    env["APPOINTMENT_CALLS_LOG"] = str(calls_path.resolve())

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH.resolve())],
        env=env,
    )

    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            tools = await session.list_tools()
            print("Available tools:")
            for tool in tools.tools:
                print(f"- {tool.name}")

            await session.call_tool("get_policy", {})
            await session.call_tool(
                "get_current_appointment",
                {"appointment_id": "A001"},
            )
            await session.call_tool(
                "search_available_slots",
                {
                    "appointment_id": "A001",
                    "date": "2026-09-14",
                    "min_hour": 14,
                    "same_provider": True,
                },
            )
            await session.call_tool(
                "reschedule_appointment",
                {
                    "appointment_id": "A001",
                    "new_slot_id": "S102",
                },
            )
            await session.call_tool(
                "list_appointments",
                {},
            )

    ledger = json.loads(
        ledger_path.read_text(encoding="utf-8")
    )
    final_slot = ledger["appointments"][0]["slot_id"]

    if final_slot != "S102":
        raise SystemExit(
            f"MCP smoke test failed: final slot={final_slot}"
        )

    print("MCP smoke test: PASS")


if __name__ == "__main__":
    asyncio.run(main())
