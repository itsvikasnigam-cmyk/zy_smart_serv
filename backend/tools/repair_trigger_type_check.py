"""Allow ops_run_logs.trigger_type = 'alert' (fixes CheckViolation on auto-trigger).

Usage:

    python backend/tools/repair_trigger_type_check.py
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
                ALTER TABLE ops_run_logs DROP CONSTRAINT IF EXISTS ops_run_logs_trigger_type_check;
                ALTER TABLE ops_run_logs ADD CONSTRAINT ops_run_logs_trigger_type_check
                  CHECK (trigger_type IN ('manual', 'auto', 'alert'));
                """
            )
        )
    print("OK: ops_run_logs now allows trigger_type = alert")
    print("Next: python backend\\tools\\fire_test_alert.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
