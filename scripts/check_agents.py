from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def check(command_name: str, version_args: list[str]) -> bool:
    executable = shutil.which(command_name)
    if executable is None:
        print(f"[MISSING] {command_name}")
        return False

    try:
        completed = subprocess.run(
            [executable, *version_args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except Exception as exc:
        print(f"[ERROR] {command_name}: {exc}")
        return False

    output = (completed.stdout or completed.stderr).strip()
    first_line = output.splitlines()[0] if output else "no version output"
    mark = "OK" if completed.returncode == 0 else "ERROR"
    print(f"[{mark}] {command_name}: {first_line}")
    return completed.returncode == 0


def main() -> None:
    claude_ok = check("claude", ["--version"])
    codex_ok = check("codex", ["--version"])

    print()
    if claude_ok:
        print("Claude model checks:")
        print('  claude -p "Reply with exactly: haiku works" --model haiku')
        print('  claude -p "Reply with exactly: sonnet works" --model sonnet')
    if codex_ok:
        print("Codex smoke check:")
        print(
            '  codex exec --json --skip-git-repo-check '
            '"Reply with exactly: codex works"'
        )


if __name__ == "__main__":
    main()
