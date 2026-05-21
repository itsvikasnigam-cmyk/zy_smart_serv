"""Diagnose why META_ACCESS_TOKEN may not match backend/.env (no full secret printed).

Usage:
  cd ...\\empty-window; . .\\dev-env.ps1
  python backend/tools/diagnose_meta_token_env.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from backend.shared.config import settings

ENV_PATH = _root / "backend" / ".env"


def _fingerprint(token: str) -> str:
    t = (token or "").strip()
    if len(t) < 12:
        return f"len={len(t)} (too short)"
    return f"len={len(t)} start={t[:8]}...end={t[-4:]}"


def _read_env_token() -> tuple[str, int]:
    if not ENV_PATH.exists():
        return "", 0
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    matches = 0
    last = ""
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("META_ACCESS_TOKEN="):
            matches += 1
            last = s.split("=", 1)[1].strip().strip('"').strip("'")
    return last, matches


def main() -> int:
    file_token, count = _read_env_token()
    proc_env = (os.environ.get("META_ACCESS_TOKEN") or "").strip()
    settings_token = (settings.meta_access_token or "").strip()

    print("=== META_ACCESS_TOKEN diagnose ===")
    print(f"backend/.env path: {ENV_PATH}")
    print(f"META_ACCESS_TOKEN lines in file: {count}")
    print(f"file token:      {_fingerprint(file_token)}")
    print(f"process env:     {_fingerprint(proc_env) if proc_env else '(not set)'}")
    print(f"settings token:  {_fingerprint(settings_token)}")

    if count == 0:
        print("\nERROR: no META_ACCESS_TOKEN= line in backend/.env")
        return 1
    if count > 1:
        print("\nWARN: multiple META_ACCESS_TOKEN lines in backend/.env — keep only ONE.")

    if proc_env and proc_env != file_token:
        print("\nPROBLEM: Windows/process META_ACCESS_TOKEN overrides backend/.env")
        print("Fix: remove user env var, or open a NEW PowerShell window after editing .env")
        print("  [Environment]::SetEnvironmentVariable('META_ACCESS_TOKEN',$null,'User')")
        return 1

    if settings_token != file_token:
        print("\nPROBLEM: Settings loaded token != backend/.env file token")
        print("Fix: save backend/.env, close PowerShell, open new window, run dev-env.ps1 again")
        return 1

    if file_token == settings_token == proc_env or (file_token == settings_token and not proc_env):
        print("\nOK: same token is loaded from backend/.env")
        print("If check_meta_token still says expired, the NEW token from Meta is also expired.")
        print("Generate a fresh token in Meta Console (not the old copied one).")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
