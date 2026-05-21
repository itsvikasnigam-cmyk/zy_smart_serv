"""Apply Option C phase 2 ops_runtime_config (idempotent). Use if migration 0017 not run yet.

Usage:
  cd ...\\empty-window; . .\\dev-env.ps1
  python backend/tools/apply_phase2_config.py
"""

from __future__ import annotations

import json
import sys

from sqlalchemy import text

from backend.shared.db import engine
from backend.shared.product_config import PHASE2_USAGE_LIMITS, PRODUCT_TRIAL_DAYS_KEY


def main() -> int:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO ops_runtime_config (key, value_json)
                VALUES (:k, CAST(:v AS jsonb))
                ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json
                """
            ),
            {"k": PRODUCT_TRIAL_DAYS_KEY, "v": json.dumps(3)},
        )
        conn.execute(
            text(
                """
                INSERT INTO ops_runtime_config (key, value_json)
                VALUES ('usage.daily_inbound_limits', CAST(:v AS jsonb))
                ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json
                """
            ),
            {"v": json.dumps(PHASE2_USAGE_LIMITS)},
        )
        conn.execute(
            text(
                """
                INSERT INTO ops_runtime_config (key, value_json)
                VALUES ('m2.usage_hard_customer_reply', CAST(:v AS jsonb))
                ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json
                """
            ),
            {
                "v": json.dumps(
                    "You've reached today's message limit on your plan. "
                    "Please upgrade or try again tomorrow."
                ),
            },
        )
    print("OK: phase 2 config applied (trial_days=3, trial/starter hard_block=35).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
