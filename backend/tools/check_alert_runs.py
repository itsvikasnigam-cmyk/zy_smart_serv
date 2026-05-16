"""Print SOP slug + recent ops_run_logs rows (for alert auto-trigger debugging).

Usage (repo root):

    python backend/tools/check_alert_runs.py
"""

from __future__ import annotations

import sys

from sqlalchemy import text

from backend.shared.db import engine


def _trigger_type_allows_alert(conn) -> bool:
    row = conn.execute(
        text(
            """
            SELECT pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conname = 'ops_run_logs_trigger_type_check'
            LIMIT 1
            """
        )
    ).fetchone()
    if not row or not row[0]:
        return False
    return "alert" in str(row[0])


def main() -> int:
    with engine.connect() as conn:
        if not _trigger_type_allows_alert(conn):
            print(
                "DB CHECK constraint does NOT allow trigger_type=alert — run: "
                "python backend\\tools\\repair_trigger_type_check.py"
            )
        sop = conn.execute(
            text("SELECT slug, id::text FROM ops_sops WHERE slug = 'payment-failure' LIMIT 1")
        ).fetchone()
        print("payment-failure SOP:", sop if sop else "NOT FOUND (run: alembic upgrade head)")

        map_row = conn.execute(
            text("SELECT value_json FROM ops_runtime_config WHERE key = 'alerts.sop_trigger_map'")
        ).fetchone()
        m = map_row[0] if map_row else None
        print("alerts.sop_trigger_map:", m)
        if isinstance(m, dict) and "BILLING_WEBHOOK_PROCESSING_ERROR" not in m:
            print(
                "  MISSING BILLING_WEBHOOK_PROCESSING_ERROR — run: "
                "alembic upgrade head   OR   python backend\\tools\\repair_sop_trigger_map.py"
            )

        runs = conn.execute(
            text(
                """
                SELECT trigger_type, created_at::text, id::text
                FROM ops_run_logs
                ORDER BY created_at DESC
                LIMIT 5
                """
            )
        ).all()
        print("Recent runs (newest first):")
        if not runs:
            print("  (none)")
        for r in runs:
            print(f"  {r[0]}  {r[1]}  id={r[2][:8]}…")

        alerts = conn.execute(
            text(
                """
                SELECT alert_type, created_at::text
                FROM ops_alert_events
                ORDER BY created_at DESC
                LIMIT 3
                """
            )
        ).all()
        print("Recent alerts:")
        for a in alerts:
            print(f"  {a[0]}  {a[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
