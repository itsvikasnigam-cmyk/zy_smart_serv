"""Disable canary traffic immediately (Chat Z).

Usage:
  python backend/tools/disable_canary.py
"""

from __future__ import annotations

import json

from backend.shared.db import engine
from backend.shared.release_manager import disable_canary_quick


def main() -> int:
    with engine.begin() as conn:
        p = disable_canary_quick(conn, note="disable_canary.py")
    print(json.dumps({
        "ok": True,
        "enabled": p.enabled,
        "percent": p.percent,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
