"""Show promoted release + canary policy (Chat Z).

Usage:
  python backend/tools/show_release_status.py
"""

from __future__ import annotations

import json

from sqlalchemy import text

from backend.shared.db import engine
from backend.shared.release_manager import get_promoted_build_id, load_canary_policy_conn


def main() -> int:
    with engine.connect() as conn:
        promoted = get_promoted_build_id(conn)
        canary = load_canary_policy_conn(conn)
        rows = conn.execute(
            text(
                """
                SELECT id::text, build_id, status, registered_at, promoted_at, rolled_back_at
                FROM ops_releases
                ORDER BY registered_at DESC
                LIMIT 10
                """
            )
        ).all()
    print("promoted_build_id:", promoted)
    print("canary:", json.dumps({
        "enabled": canary.enabled,
        "percent": canary.percent,
        "active_build_id": canary.active_build_id,
        "canary_primary_model": canary.canary_primary_model,
    }, indent=2))
    print("\nrecent releases:")
    for r in rows or []:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
