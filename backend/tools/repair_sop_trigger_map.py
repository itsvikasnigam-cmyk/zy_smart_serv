"""Add missing billing entry to alerts.sop_trigger_map (no Alembic required).

Usage:

    python backend/tools/repair_sop_trigger_map.py
"""

from __future__ import annotations

import sys

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE ops_runtime_config
                SET value_json = COALESCE(value_json, '{}'::jsonb)
                  || '{"BILLING_WEBHOOK_PROCESSING_ERROR": "payment-failure"}'::jsonb
                WHERE key = 'alerts.sop_trigger_map';
                """
            )
        )
        row = conn.execute(
            text("SELECT value_json FROM ops_runtime_config WHERE key = 'alerts.sop_trigger_map'")
        ).fetchone()
    print("Updated alerts.sop_trigger_map:")
    print(row[0] if row else "(key missing)")
    print("Now run: python backend\\tools\\fire_test_alert.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
