from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_RUNS_DIR = ROOT / "runs"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def base_task_id(folder_name: str) -> str:
    return folder_name.split("_r", maxsplit=1)[0]


def collect_results(runs_dir: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for path in sorted(runs_dir.glob("*/*/result.json")):
        result = load_json(path)
        result["_task_folder"] = path.parent.name
        result["_base_task"] = base_task_id(path.parent.name)
        results.append(result)
    return results


def write_csv(results: list[dict[str, Any]], path: Path) -> None:
    fields = [
        "agent", "agent_kind", "foundation_model", "suite",
        "task_id", "task_name", "skill", "passed",
        "expected_action", "expected_slot_id", "final_slot_id",
        "n_tool_calls", "n_failed_tool_calls", "wall_seconds",
        "exit_code", "timed_out", "cost_usd", "output_tokens",
        "reasons",
    ]

    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for result in results:
            row = {field: result.get(field, "") for field in fields}
            row["reasons"] = "; ".join(result.get("reasons", []))
            writer.writerow(row)


def matrix_mark(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "—"
    passed = sum(1 for row in rows if row["passed"])
    if len(rows) == 1:
        return "PASS" if passed == 1 else "FAIL"
    return f"{passed}/{len(rows)}"


def summary_row(agent: str, rows: list[dict[str, Any]]) -> str:
    passed = sum(1 for result in rows if result["passed"])
    total = len(rows)
    pass_rate = passed / total if total else 0
    avg_calls = sum(result.get("n_tool_calls", 0) for result in rows) / total if total else 0
    failed_calls = sum(result.get("n_failed_tool_calls", 0) for result in rows)
    avg_wall = sum(result.get("wall_seconds", 0) for result in rows) / total if total else 0
    return (
        f"| {agent} | {passed}/{total} | {pass_rate:.1%} | "
        f"{avg_calls:.1f} | {failed_calls} | {avg_wall:.2f}s |"
    )


def build_markdown(results: list[dict[str, Any]]) -> str:
    agents = sorted({result["agent"] for result in results})
    tasks = sorted(
        {result["task_id"] for result in results},
        key=lambda item: (item[0], int(item[1:])),
    )

    lines = [
        "# Appointment-Agent Benchmark Results",
        "",
        "Generated from deterministic grader outputs in `runs/`.",
        "",
        "## Task × Agent Matrix",
        "",
        "| Task | Suite | " + " | ".join(agents) + " |",
        "|---|---|" + "|".join(["---"] * len(agents)) + "|",
    ]

    for task_id in tasks:
        task_rows = [result for result in results if result["task_id"] == task_id]
        suite = task_rows[0].get("suite", "") if task_rows else ""
        marks = []
        for agent in agents:
            rows = [
                result for result in task_rows
                if result["agent"] == agent
            ]
            marks.append(matrix_mark(rows))
        lines.append(f"| {task_id} | {suite} | " + " | ".join(marks) + " |")

    lines.extend(
        [
            "",
            "## Per-Agent Summary",
            "",
            "| Agent | Passed | Pass rate | Avg. tool calls | Failed tool calls | Avg. wall time |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for agent in agents:
        lines.append(summary_row(agent, [r for r in results if r["agent"] == agent]))

    suites = sorted({result.get("suite", "") for result in results if result.get("suite")})
    for suite in suites:
        lines.extend(
            [
                "",
                f"## {suite.title()} Suite Summary",
                "",
                "| Agent | Passed | Pass rate | Avg. tool calls | Failed tool calls | Avg. wall time |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for agent in agents:
            rows = [
                r for r in results
                if r["agent"] == agent and r.get("suite") == suite
            ]
            if rows:
                lines.append(summary_row(agent, rows))

    failures = [result for result in results if not result["passed"]]
    lines.extend(["", "## Failures", ""])
    if not failures:
        lines.append("No failures were recorded.")
    else:
        for result in failures:
            reason = "; ".join(result.get("reasons", []))
            lines.append(f"- **{result['agent']} {result['task_id']}**: {reason}")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The easy suite is an execution and basic-safety smoke test. "
            "The hard suite hides machine-readable constraints from the agent "
            "and tests policy retrieval, conditional no-op behavior, referral "
            "and authorization safety, race-condition recovery, double-booking "
            "avoidance, pediatric eligibility, and multi-constraint filtering. "
            "Accuracy differences should be interpreted together with failed "
            "tool calls, tool-call count, wall time, and repeated-run reliability.",
            "",
        ]
    )
    return "\n".join(lines)


def print_console(results: list[dict[str, Any]]) -> None:
    print(
        f"{'Agent':<18}{'Task':<7}{'Suite':<7}{'Result':<9}"
        f"{'Expected':<11}{'Final':<9}{'Calls':<7}{'Wall':<8}"
    )
    print("-" * 76)
    for result in results:
        mark = "PASS" if result["passed"] else "FAIL"
        print(
            f"{result['agent']:<18}{result['task_id']:<7}"
            f"{result.get('suite', ''):<7}{mark:<9}"
            f"{str(result.get('expected_slot_id')):<11}"
            f"{str(result.get('final_slot_id')):<9}"
            f"{result.get('n_tool_calls', 0):<7}"
            f"{result.get('wall_seconds', 0):<8}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs-dir", default=str(DEFAULT_RUNS_DIR))
    args = parser.parse_args()

    runs_dir = Path(args.runs_dir)
    results = collect_results(runs_dir)
    if not results:
        print("No result.json files were found.")
        return

    print_console(results)
    csv_path = ROOT / "benchmark_results.csv"
    markdown_path = ROOT / "BENCHMARK_REPORT.md"
    write_csv(results, csv_path)
    markdown_path.write_text(build_markdown(results), encoding="utf-8")

    print()
    print(f"CSV: {csv_path}")
    print(f"Markdown report: {markdown_path}")


if __name__ == "__main__":
    main()
