# Project Update: Appointment-Rescheduling Agent Benchmark

## Research question

How reliably can AI agents reschedule healthcare appointments while respecting availability, insurance, specialty, location, referral, age-eligibility, authorization, conditional-action, and calendar-conflict constraints?

## Evaluation workflow

```text
Natural-language task → CLI agent → Appointment MCP tools
→ Frozen synthetic clinic / per-run ledger
→ Server-side tool-call log → Deterministic grader → Result report
```

The benchmark compares Claude Code with Haiku, Claude Code with Sonnet, and Codex CLI. Haiku versus Sonnet holds the harness constant while changing the foundation model; Codex adds a different agent harness. A rule-based baseline validates the environment and is not treated as an AI result.

## Synthetic environment

The environment contains six synthetic patients, eight providers, multiple specialties and insurance plans, referral metadata, pediatric eligibility, locations, controlled task fixtures, and deterministic background availability. No real patient data is used.

## Easy suite

T01–T06 verify basic execution and safety: normal rescheduling, safe decline, insurance, specialty, availability, and earliest-valid-slot selection.

## Hard suite

H01–H08 add independent failure mechanisms:

| Task | Capability tested |
|---|---|
| H01 | Policy retrieval, vague-time interpretation, soft provider preference |
| H02 | Conditional no-op rather than unnecessary decline or modification |
| H03 | Referral-policy enforcement |
| H04 | Recovery after a slot becomes unavailable between search and booking |
| H05 | Double-booking avoidance using existing calendar state |
| H06 | Joint filtering by location, insurance, specialty, and time |
| H07 | Authorization policy and safe refusal |
| H08 | Pediatric-provider eligibility |

Hard-suite prompts do not expose the hidden machine-readable constraints. Policy tasks require the agent to call `get_policy`; the grader verifies that the call occurred. The recovery task requires a failed tool call followed by successful re-planning.

## Deterministic grading

The grader computes the valid candidate set from the frozen snapshot and hidden constraints. It checks:

- correct final slot or safe decline
- true no-op behavior when required
- preservation of unrelated appointments
- reschedule and decline histories
- policy retrieval
- failed-tool recovery
- insurance, specialty, location, referral, pediatric, authorization, and overlap rules

No LLM judge is used.

## Metrics

- task success rate
- easy-suite and hard-suite pass rates
- failed tool calls
- tool-call count
- wall-clock time
- repeated-run reliability with `--reps k`
- token and cost metadata when exposed by the CLI

## Reproducibility

Each task-agent run starts from its own copy of the frozen snapshot and initial ledger. The system stores the exact prompt, final ledger, MCP call log, trace, stderr, and deterministic grader output under `runs/<agent>/<task>/`.

## Results

The empirical results are generated from local authenticated Claude Code and Codex sessions. They are reported in:

- `BENCHMARK_REPORT.md`
- `benchmark_results.csv`

The report is regenerated from per-run `result.json` files with:

```powershell
py .\report.py
```

## Evaluation commands

```powershell
# Easy suite
py .\runner.py --agents claude-haiku,claude-sonnet --tasks all
py .\runner.py --agents codex --tasks all --allow-unsafe-codex

# Hard suite
py .\runner.py --agents claude-haiku,claude-sonnet --tasks-file .\tasks\tasks_hard.json --tasks all
py .\runner.py --agents codex --tasks-file .\tasks\tasks_hard.json --tasks all --allow-unsafe-codex

# Aggregate both suites
py .\report.py
```

## Interpretation plan

The easy suite primarily checks whether the harness and tools work. The hard suite is intended to separate agents by specification understanding, safety, policy use, calendar-state reasoning, and error recovery. Results should be interpreted using both accuracy and behavior-level metrics rather than pass rate alone.
