# Codex Headless MCP Safety Note

The Codex adapter uses:

```text
--dangerously-bypass-approvals-and-sandbox
```

This is currently needed by the Flight-Bench-style headless MCP adapter because non-interactive Codex MCP calls may otherwise be denied while waiting for an approval that cannot be answered.

This flag disables Codex's normal approval prompts and sandbox protections. For that reason:

- The runner requires the explicit `--allow-unsafe-codex` flag.
- Codex starts from a separate per-run directory rather than the project root.
- The prompt instructs Codex to use only appointment MCP tools and not shell commands or files.
- The benchmark contains only synthetic data.
- Close unrelated sensitive projects and terminals before running.
- Do not use this adapter on a machine or directory containing sensitive credentials unless you understand the risk.

Run Codex separately from Claude when first testing it:

```powershell
py .\runner.py --agents codex --tasks T01 --allow-unsafe-codex
```

Inspect these files after the run:

```text
runs/codex/T01/trace.jsonl
runs/codex/T01/stderr.log
runs/codex/T01/tool_calls.json
runs/codex/T01/result.json
```
