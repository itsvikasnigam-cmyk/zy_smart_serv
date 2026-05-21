"""Update privacy.policy in ops_runtime_config (Chat V).

Usage:
  python backend/tools/set_privacy_policy.py --blocklist-mode handoff
  python backend/tools/set_privacy_policy.py --blocklist-mode drop --retention-days 14
"""

from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import text

from backend.shared.db import engine
from backend.shared.privacy_config import PRIVACY_POLICY_KEY, merge_privacy_policy


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--blocklist-mode", choices=["drop", "handoff"], default=None)
    p.add_argument("--retention-days", type=int, default=None)
    p.add_argument("--customer-reply", default=None, help="blocklist handoff customer line")
    args = p.parse_args()

    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT value_json FROM ops_runtime_config WHERE key = :k"),
            {"k": PRIVACY_POLICY_KEY},
        ).fetchone()
        merged = merge_privacy_policy(row[0] if row else None)
        if args.blocklist_mode:
            merged["blocklist_mode"] = args.blocklist_mode
        if args.retention_days is not None:
            merged["telemetry_retention_days"] = args.retention_days
        if args.customer_reply is not None:
            merged["blocklist_customer_reply"] = args.customer_reply
        conn.execute(
            text(
                """
                INSERT INTO ops_runtime_config (key, value_json)
                VALUES (:k, CAST(:v AS jsonb))
                ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json
                """
            ),
            {"k": PRIVACY_POLICY_KEY, "v": json.dumps(merged)},
        )
    print("OK: privacy.policy")
    print(json.dumps(merged, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
