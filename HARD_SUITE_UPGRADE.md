# Hard-Suite Upgrade Guide

## Files added

```text
tasks/tasks_hard.json
tasks/policy.md
tasks/GROUND_TRUTH_HARD.md
HARD_SUITE_UPGRADE.md
```

## Files replaced

```text
runner.py
baseline_agent.py
report.py
grading/grader.py
server/appointment_mcp.py
server/appointment_server.py
scripts/build_snapshot.py
scripts/validate_tasks.py
scripts/ground_truth.py
README.md
TEACHER_REPORT.md
```

## What each change does

- `tasks_hard.json`: defines H01–H08.
- `policy.md`: rules for vague time, referrals, pediatric eligibility, authorization, no-op, recovery, and overlap.
- `appointment_mcp.py`: adds `get_policy` and deterministic race-condition behavior.
- `grader.py`: adds no-op grading, policy-call checks, referral, location, pediatric, authorization, overlap, and recovery checks.
- `runner.py`: adds `--tasks-file`, hides hard constraints from agents, permits `get_policy`, and includes both Windows Codex fixes.
- `baseline_agent.py`: validates hard-suite infrastructure and recovers from deterministic tool failure.
- `report.py`: reports suite labels and separate easy/hard summaries.
- `build_snapshot.py`: adds hard-task fixtures and patient referral metadata.

## Upgrade an existing project without deleting results

Back up the folder, then copy the files from the upgrade ZIP into the project root and allow replacement. Do **not** delete or replace the existing `runs/` folder. Rebuild the snapshot afterward:

```powershell
py .\scripts\build_snapshot.py
py .\scripts\validate_tasks.py
py .\scripts\validate_tasks.py --tasks-file .\tasks\tasks_hard.json
py .\runner.py --agents baseline --tasks-file .\tasks\tasks_hard.json --tasks all
```

Then run the AI agents on the hard suite and regenerate the report.
