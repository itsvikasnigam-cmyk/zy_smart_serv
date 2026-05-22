#!/usr/bin/env python3
"""Run pytest and write results to scripts/pytest_ci_result.txt (for CI debugging)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "scripts" / "pytest_ci_result.txt"


def main() -> int:
    env = {**dict(__import__("os").environ), "PYTHONPATH": str(ROOT)}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    body = (proc.stdout or "") + (proc.stderr or "")
    OUT.write_text(
        f"exit_code={proc.returncode}\n\n{body}",
        encoding="utf-8",
    )
    print(body, end="")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
