from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from grading.grader import grade


ROOT = Path(__file__).resolve().parent
DEFAULT_TASKS_PATH = ROOT / "tasks" / "tasks.json"
SNAPSHOT_PATH = ROOT / "data" / "snapshot.json"
SERVER_PATH = ROOT / "server" / "appointment_server.py"
BASELINE_AGENT_PATH = ROOT / "baseline_agent.py"
AGENTS_PATH = ROOT / "agents.json"
RUNS_DIR = ROOT / "runs"

CLAUDE_ALLOWED_TOOLS = ",".join(
    [
        "mcp__appointment__get_policy",
        "mcp__appointment__get_current_appointment",
        "mcp__appointment__get_patient",
        "mcp__appointment__get_provider",
        "mcp__appointment__search_available_slots",
        "mcp__appointment__reschedule_appointment",
        "mcp__appointment__decline_reschedule",
        "mcp__appointment__list_appointments",
    ]
)

CLAUDE_DISALLOWED_TOOLS = (
    "Bash,Read,Write,Edit,Glob,Grep,WebSearch,WebFetch"
)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)


def select_named(
    available: dict[str, Any],
    argument: str,
    label: str,
) -> list[str]:
    if argument == "all":
        return [
            name for name in available if not name.startswith("_")
        ]

    requested = [
        item.strip()
        for item in argument.split(",")
        if item.strip()
    ]
    missing = [
        item for item in requested if item not in available
    ]
    if missing:
        raise ValueError(
            f"Unknown {label}: {missing}. "
            f"Available: {sorted(available)}"
        )
    return requested


def select_tasks(
    tasks: list[dict[str, Any]],
    argument: str,
) -> list[dict[str, Any]]:
    if argument == "all":
        return tasks

    requested = {
        item.strip()
        for item in argument.split(",")
        if item.strip()
    }
    selected = [task for task in tasks if task["id"] in requested]
    missing = requested - {task["id"] for task in selected}
    if missing:
        raise ValueError(f"Unknown task IDs: {sorted(missing)}")
    return selected


def build_prompt(task: dict[str, Any]) -> str:
    policy_clause = ""
    if task.get("policy", False):
        policy_clause = (
            "- Clinic policy is in force. Call get_policy before acting "
            "and follow it even when the scheduling system is more permissive.\n"
        )

    common = f"""
You are an appointment-rescheduling agent operating in a synthetic
clinic environment.

Complete the user request by using only the appointment MCP tools.

Important rules:
- Inspect the current appointment before acting.
- Inspect patient, provider, and existing appointment records whenever
  they may affect insurance, specialty, location, eligibility, referral,
  authorization, or scheduling conflicts.
{policy_clause}- search_available_slots filters schedule constraints only; it does not
  enforce insurance, specialty, location, policy, or patient conflicts.
- A slot may become unavailable after search. Recover from tool errors
  by re-reading state and trying the next valid option.
- A conditional instruction to leave the appointment unchanged requires
  a true no-op when its condition is not met.
- Do not modify unrelated appointments.
- Confirm the final state with list_appointments.
- Do not use shell commands, edit files, or inspect the project.
- Perform the action; do not merely describe what should happen.
""".strip()

    if task.get("suite") == "hard":
        # Hard-suite constraints are hidden from the agent. The natural
        # user request and policy are the specification it must interpret.
        return f"{common}\n\nUSER REQUEST:\n{task['prompt']}"

    constraints = json.dumps(task["constraints"], indent=2)
    return (
        f"{common}\n\nMachine-readable task constraints:\n"
        f"{constraints}\n\nUSER REQUEST:\n{task['prompt']}"
    )


def create_mcp_config(
    snapshot_path: Path,
    ledger_path: Path,
    calls_path: Path,
    mcp_config_path: Path,
) -> None:
    config = {
        "mcpServers": {
            "appointment": {
                "command": sys.executable,
                "args": [str(SERVER_PATH.resolve())],
                "env": {
                    "APPOINTMENT_SNAPSHOT": str(
                        snapshot_path.resolve()
                    ),
                    "APPOINTMENT_LEDGER": str(
                        ledger_path.resolve()
                    ),
                    "APPOINTMENT_CALLS_LOG": str(
                        calls_path.resolve()
                    ),
                },
            }
        }
    }
    save_json(mcp_config_path, config)


def parse_claude_metrics(trace_path: Path) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "cost_usd": None,
        "output_tokens": None,
    }

    try:
        for line in trace_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines():
            if not line.startswith("{"):
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if event.get("type") == "result":
                metrics["cost_usd"] = event.get("total_cost_usd")
                metrics["output_tokens"] = (
                    event.get("usage") or {}
                ).get("output_tokens")
    except OSError:
        pass

    return metrics


def parse_codex_metrics(trace_path: Path) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "cost_usd": None,
        "output_tokens": None,
    }

    try:
        for line in trace_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines():
            if not line.startswith("{"):
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            usage = event.get("usage") or {}
            output_tokens = (
                usage.get("output_tokens")
                or usage.get("output_tokens_count")
            )
            if output_tokens is not None:
                metrics["output_tokens"] = output_tokens
    except OSError:
        pass

    return metrics


def run_baseline(
    task: dict[str, Any],
    tasks_path: Path,
    run_dir: Path,
    environment: dict[str, str],
    timeout: int,
) -> tuple[int, bool]:
    command = [
        sys.executable,
        str(BASELINE_AGENT_PATH),
        "--task",
        task["id"],
        "--tasks-file",
        str(tasks_path.resolve()),
    ]

    with (run_dir / "trace.jsonl").open(
        "w",
        encoding="utf-8",
    ) as stdout_file, (run_dir / "stderr.log").open(
        "w",
        encoding="utf-8",
    ) as stderr_file:
        try:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                stdout=stdout_file,
                stderr=stderr_file,
                check=False,
                timeout=timeout,
            )
            return completed.returncode, False
        except subprocess.TimeoutExpired:
            return -1, True


def run_claude(
    task: dict[str, Any],
    model: str,
    run_dir: Path,
    mcp_config_path: Path,
    environment: dict[str, str],
    timeout: int,
) -> tuple[int, bool]:
    claude_executable = shutil.which("claude")
    if claude_executable is None:
        raise RuntimeError(
            "Claude Code was not found. Run 'claude --version'."
        )

    prompt = build_prompt(task)
    prompt_path = run_dir / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    if os.name == "nt":
        powershell = (
            shutil.which("pwsh")
            or shutil.which("powershell")
        )
        if powershell is None:
            raise RuntimeError("PowerShell was not found.")

        ps_script = (
            "$promptText = Get-Content -Raw "
            "-LiteralPath $env:CLAUDE_PROMPT_PATH; "
            "$promptText | & $env:CLAUDE_EXE "
            '-p "Complete the appointment benchmark task '
            'provided through standard input. Use the appointment '
            'MCP tools and perform the requested action." '
            "--mcp-config $env:CLAUDE_MCP_CONFIG "
            "--strict-mcp-config "
            "--allowedTools $env:CLAUDE_ALLOWED_TOOLS "
            "--disallowedTools $env:CLAUDE_DISALLOWED_TOOLS "
            "--model $env:CLAUDE_MODEL "
            "--max-turns 30 "
            "--output-format stream-json "
            "--verbose; "
            "exit $LASTEXITCODE"
        )

        command = [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            ps_script,
        ]

        environment["CLAUDE_EXE"] = claude_executable
        environment["CLAUDE_PROMPT_PATH"] = str(
            prompt_path.resolve()
        )
        environment["CLAUDE_MCP_CONFIG"] = str(
            mcp_config_path.resolve()
        )
        environment["CLAUDE_ALLOWED_TOOLS"] = (
            CLAUDE_ALLOWED_TOOLS
        )
        environment["CLAUDE_DISALLOWED_TOOLS"] = (
            CLAUDE_DISALLOWED_TOOLS
        )
        environment["CLAUDE_MODEL"] = model
    else:
        command = [
            claude_executable,
            "-p",
            prompt,
            "--mcp-config",
            str(mcp_config_path.resolve()),
            "--strict-mcp-config",
            "--allowedTools",
            CLAUDE_ALLOWED_TOOLS,
            "--disallowedTools",
            CLAUDE_DISALLOWED_TOOLS,
            "--model",
            model,
            "--max-turns",
            "30",
            "--output-format",
            "stream-json",
            "--verbose",
        ]

    with (run_dir / "trace.jsonl").open(
        "w",
        encoding="utf-8",
    ) as stdout_file, (run_dir / "stderr.log").open(
        "w",
        encoding="utf-8",
    ) as stderr_file:
        try:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                stdout=stdout_file,
                stderr=stderr_file,
                check=False,
                timeout=timeout,
            )
            return completed.returncode, False
        except subprocess.TimeoutExpired:
            return -1, True


def toml_literal_string(value: str) -> str:
    """Quote a value as a TOML literal string.

    Single-quoted TOML strings keep Windows backslashes literal, which
    prevents Codex CLI from treating an MCP args array as one string.
    """
    if "'" in value:
        # This fallback is unlikely for Windows paths, but it keeps the
        # function valid for values containing an apostrophe.
        return json.dumps(value)
    return "'" + value + "'"


def codex_config_overrides(
    snapshot_path: Path,
    ledger_path: Path,
    calls_path: Path,
) -> list[str]:
    """Build per-run Codex TOML overrides for the stdio MCP server."""
    python_value = toml_literal_string(sys.executable)
    server_value = toml_literal_string(str(SERVER_PATH.resolve()))
    snapshot_value = toml_literal_string(str(snapshot_path.resolve()))
    ledger_value = toml_literal_string(str(ledger_path.resolve()))
    calls_value = toml_literal_string(str(calls_path.resolve()))

    return [
        f"mcp_servers.appointment.command={python_value}",
        # Codex requires args to be a TOML sequence, not a quoted JSON
        # string. Literal quoting is reliable with Windows paths.
        f"mcp_servers.appointment.args=[{server_value}]",
        (
            "mcp_servers.appointment.env.APPOINTMENT_SNAPSHOT="
            + snapshot_value
        ),
        (
            "mcp_servers.appointment.env.APPOINTMENT_LEDGER="
            + ledger_value
        ),
        (
            "mcp_servers.appointment.env.APPOINTMENT_CALLS_LOG="
            + calls_value
        ),
    ]


def run_codex(
    task: dict[str, Any],
    model: str | None,
    run_dir: Path,
    snapshot_path: Path,
    ledger_path: Path,
    calls_path: Path,
    environment: dict[str, str],
    timeout: int,
) -> tuple[int, bool]:
    codex_executable = shutil.which("codex")
    if codex_executable is None:
        raise RuntimeError(
            "Codex CLI was not found. Install @openai/codex and "
            "run 'codex --version'."
        )

    prompt = build_prompt(task)
    prompt_path = run_dir / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    overrides = codex_config_overrides(
        snapshot_path,
        ledger_path,
        calls_path,
    )

    base_arguments = [
        "exec",
        "--json",
        "--skip-git-repo-check",
        "--dangerously-bypass-approvals-and-sandbox",
    ]
    if model:
        base_arguments.extend(["--model", model])
    for override in overrides:
        base_arguments.extend(["-c", override])
    base_arguments.append("-")

    if os.name == "nt":
        powershell = (
            shutil.which("pwsh")
            or shutil.which("powershell")
        )
        if powershell is None:
            raise RuntimeError("PowerShell was not found.")

        # PowerShell's argument array preserves the prompt and all config
        # overrides as single arguments, including Windows paths.
        environment["CODEX_EXE"] = codex_executable
        for index, argument in enumerate(base_arguments):
            environment[f"CODEX_ARG_{index}"] = argument
        environment["CODEX_ARG_COUNT"] = str(len(base_arguments))

        ps_script = (
            "$argsList = @(); "
            "$count = [int]$env:CODEX_ARG_COUNT; "
            "for ($i = 0; $i -lt $count; $i++) { "
            "$argsList += [Environment]::GetEnvironmentVariable("
            "('CODEX_ARG_' + $i)); }; "
            "& $env:CODEX_EXE @argsList; "
            "exit $LASTEXITCODE"
        )
        command = [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            ps_script,
        ]
    else:
        command = [codex_executable, *base_arguments]

    with (run_dir / "trace.jsonl").open(
        "w",
        encoding="utf-8",
    ) as stdout_file, (run_dir / "stderr.log").open(
        "w",
        encoding="utf-8",
    ) as stderr_file:
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                text=True,
                # Run from the isolated per-run folder rather than the
                # project root. The MCP paths are absolute.
                cwd=run_dir,
                env=environment,
                stdout=stdout_file,
                stderr=stderr_file,
                check=False,
                timeout=timeout,
            )
            return completed.returncode, False
        except subprocess.TimeoutExpired:
            return -1, True


def run_one(
    agent_name: str,
    agent_config: dict[str, Any],
    task: dict[str, Any],
    tasks_path: Path,
    run_dir: Path,
    timeout: int,
) -> dict[str, Any]:
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    snapshot_path = run_dir / "snapshot.json"
    ledger_path = run_dir / "ledger.json"
    calls_path = run_dir / "tool_calls.json"
    mcp_config_path = run_dir / "mcp_config.json"

    shutil.copy2(SNAPSHOT_PATH, snapshot_path)

    save_json(
        ledger_path,
        copy.deepcopy(task["initial_ledger"]),
    )
    save_json(calls_path, [])
    create_mcp_config(
        snapshot_path,
        ledger_path,
        calls_path,
        mcp_config_path,
    )

    environment = os.environ.copy()
    environment["APPOINTMENT_SNAPSHOT"] = str(
        snapshot_path.resolve()
    )
    environment["APPOINTMENT_LEDGER"] = str(
        ledger_path.resolve()
    )
    environment["APPOINTMENT_CALLS_LOG"] = str(
        calls_path.resolve()
    )

    started = time.perf_counter()
    timed_out = False
    error_message: str | None = None

    try:
        if agent_config["kind"] == "baseline":
            exit_code, timed_out = run_baseline(
                task,
                tasks_path,
                run_dir,
                environment,
                timeout,
            )
        elif agent_config["kind"] == "claude":
            exit_code, timed_out = run_claude(
                task,
                agent_config["model"],
                run_dir,
                mcp_config_path,
                environment,
                timeout,
            )
        elif agent_config["kind"] == "codex":
            exit_code, timed_out = run_codex(
                task,
                agent_config.get("model"),
                run_dir,
                snapshot_path,
                ledger_path,
                calls_path,
                environment,
                timeout,
            )
        else:
            raise ValueError(
                f"Unsupported agent kind: {agent_config['kind']}"
            )
    except Exception as exc:
        exit_code = -1
        error_message = str(exc)

    wall_seconds = round(
        time.perf_counter() - started,
        2,
    )

    result = grade(task, run_dir)
    result.update(
        {
            "agent": agent_name,
            "agent_kind": agent_config["kind"],
            "foundation_model": agent_config.get("model"),
            "exit_code": exit_code,
            "timed_out": timed_out,
            "wall_seconds": wall_seconds,
        }
    )

    if timed_out:
        result["passed"] = False
        result["reasons"].append(
            f"Agent timed out after {timeout} seconds."
        )
    elif error_message is not None:
        result["passed"] = False
        result["reasons"].append(error_message)
    elif exit_code != 0:
        result["passed"] = False
        result["reasons"].append(
            f"Agent exited with code {exit_code}."
        )

    if agent_config["kind"] == "claude":
        result.update(
            parse_claude_metrics(run_dir / "trace.jsonl")
        )
    elif agent_config["kind"] == "codex":
        result.update(
            parse_codex_metrics(run_dir / "trace.jsonl")
        )

    save_json(run_dir / "result.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the appointment-agent benchmark."
    )
    parser.add_argument(
        "--agents",
        default="baseline",
        help=(
            "Comma-separated agents from agents.json, "
            "or all."
        ),
    )
    parser.add_argument(
        "--tasks-file",
        default=str(DEFAULT_TASKS_PATH),
        help="Path to an easy- or hard-suite task JSON file.",
    )
    parser.add_argument(
        "--tasks",
        default="all",
        help="Comma-separated task IDs, or all.",
    )
    parser.add_argument(
        "--reps",
        type=int,
        default=1,
        help="Repeat each agent-task pair k times.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=420,
        help="Maximum seconds per agent-task run.",
    )
    parser.add_argument(
        "--runs-dir",
        default=str(RUNS_DIR),
    )
    parser.add_argument(
        "--allow-unsafe-codex",
        action="store_true",
        help=(
            "Acknowledge that headless Codex MCP execution uses "
            "--dangerously-bypass-approvals-and-sandbox."
        ),
    )
    args = parser.parse_args()

    agent_configs = load_json(AGENTS_PATH)
    selected_agents = select_named(
        agent_configs,
        args.agents,
        "agents",
    )

    if "codex" in selected_agents and not args.allow_unsafe_codex:
        raise SystemExit(
            "Codex was selected, but the headless MCP adapter needs "
            "--dangerously-bypass-approvals-and-sandbox. Read "
            "CODEX_SECURITY.md, then rerun with "
            "--allow-unsafe-codex if you accept this for the isolated "
            "synthetic benchmark."
        )

    tasks_path = Path(args.tasks_file).resolve()
    all_tasks = load_json(tasks_path)["tasks"]
    selected_tasks = select_tasks(
        all_tasks,
        args.tasks,
    )

    results: list[dict[str, Any]] = []
    runs_dir = Path(args.runs_dir)

    for agent_name in selected_agents:
        config = agent_configs[agent_name]

        for task in selected_tasks:
            for rep in range(1, args.reps + 1):
                task_folder = (
                    task["id"]
                    if args.reps == 1
                    else f"{task['id']}_r{rep}"
                )
                run_dir = (
                    runs_dir
                    / agent_name
                    / task_folder
                )

                result = run_one(
                    agent_name,
                    config,
                    task,
                    tasks_path,
                    run_dir,
                    args.timeout,
                )
                results.append(result)

                mark = (
                    "PASS"
                    if result["passed"]
                    else "FAIL"
                )
                print(
                    f"[{mark}] {agent_name} "
                    f"{task['id']} "
                    f"calls={result['n_tool_calls']} "
                    f"wall={result['wall_seconds']}s"
                )
                for reason in result["reasons"]:
                    print(f"  - {reason}")

    print("\n=== SUMMARY ===")
    for agent_name in selected_agents:
        rows = [
            result
            for result in results
            if result["agent"] == agent_name
        ]
        passed = sum(
            1 for result in rows if result["passed"]
        )
        print(
            f"{agent_name}: "
            f"{passed}/{len(rows)} passed"
        )

    save_json(runs_dir / "summary.json", results)


if __name__ == "__main__":
    main()
