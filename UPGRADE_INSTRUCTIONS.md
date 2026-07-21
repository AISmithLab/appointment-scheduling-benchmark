# Setup and Run Instructions

This folder is a standalone report-ready version configured for Claude Haiku, Claude Sonnet, and Codex.

## 1. Open the correct folder

Open the folder that directly contains:

```text
agents.json
runner.py
report.py
data/
tasks/
server/
grading/
```

## 2. Install the Python dependency

```powershell
py -m pip install -r .\requirements.txt
```

## 3. Validate the environment

```powershell
py .\scripts\build_snapshot.py
py .\scripts\validate_tasks.py
py .\test_mcp.py
py .\runner.py --agents baseline --tasks all
```

Expected baseline result:

```text
baseline: 6/6 passed
```

## 4. Check the agent CLIs

```powershell
py .\scripts\check_agents.py
```

Then run the explicit authentication/model checks:

```powershell
claude --version
claude doctor
claude -p "Reply with exactly: haiku works" --model haiku
claude -p "Reply with exactly: sonnet works" --model sonnet

npm install -g @openai/codex
codex --version
codex login
codex exec --json --skip-git-repo-check "Reply with exactly: codex works"
```

## 5. Run a one-task smoke test

```powershell
py .\runner.py --agents claude-haiku,claude-sonnet --tasks T01
py .\runner.py --agents codex --tasks T01 --allow-unsafe-codex
```

## 6. Run all tasks

```powershell
py .\runner.py --agents claude-haiku,claude-sonnet --tasks all
py .\runner.py --agents codex --tasks all --allow-unsafe-codex
```

Or all three in one command:

```powershell
py .\runner.py --agents claude-haiku,claude-sonnet,codex --tasks all --allow-unsafe-codex
```

## 7. Generate the report

```powershell
py .\report.py
```

Teacher-facing outputs:

```text
TEACHER_REPORT.md
BENCHMARK_REPORT.md
benchmark_results.csv
```

## 8. Reliability run

```powershell
py .\runner.py --agents claude-haiku,claude-sonnet,codex --tasks all --reps 3 --allow-unsafe-codex
py .\report.py
```

Read `CODEX_SECURITY.md` before running the Codex adapter.
