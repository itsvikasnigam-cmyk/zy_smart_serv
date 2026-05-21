"""Enable inbox typing lock (Chat Q) in ops_runtime_config.

Usage (repo root, after . .\\dev-env.ps1):
  python backend/tools/enable_typing_lock.py
  python backend/tools/enable_typing_lock.py --off
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import text

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from backend.shared.db import engine
from backend.shared.inbox_typing_lock import LEGACY_HARD_LOCK_KEY, POLICY_KEY, merge_typing_lock_policy


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--off", action="store_true", help="Disable typing lock")
    args = ap.parse_args()
    enabled = not args.off

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO ops_runtime_config (key, value_json)
                VALUES (:k, CAST(:v AS jsonb))
                ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json
                """
            ),
            {"k": LEGACY_HARD_LOCK_KEY, "v": json.dumps(enabled)},
        )
        row = conn.execute(
            text("SELECT value_json FROM ops_runtime_config WHERE key = :k"),
            {"k": POLICY_KEY},
        ).fetchone()
        policy = merge_typing_lock_policy(row[0] if row else None)
        policy["enabled"] = enabled
        conn.execute(
            text(
                """
                INSERT INTO ops_runtime_config (key, value_json)
                VALUES (:k, CAST(:v AS jsonb))
                ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json
                """
            ),
            {"k": POLICY_KEY, "v": json.dumps(policy)},
        )

    print(f"OK: typing lock {'disabled' if args.off else 'enabled'}")
    print(f"  {LEGACY_HARD_LOCK_KEY} = {enabled}")
    print(f"  {POLICY_KEY}.enabled = {enabled}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
