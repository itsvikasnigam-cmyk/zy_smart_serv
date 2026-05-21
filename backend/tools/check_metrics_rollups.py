"""Show rollup table row counts (Dash chart data source).

Usage:

    python backend/tools/check_metrics_rollups.py
"""

from __future__ import annotations

import sys

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    with engine.connect() as conn:
        hourly = conn.execute(
            text(
                """
                SELECT hour_bucket_utc, customer_in_messages, ai_out_messages,
                       agent_out_messages, wa_outbox_rows_dead
                FROM metrics_hourly_system
                ORDER BY hour_bucket_utc DESC
                LIMIT 5
                """
            )
        ).all()
        daily = conn.execute(
            text(
                """
                SELECT metric_date,
                       COUNT(*)::int,
                       COALESCE(SUM(ai_invocations), 0)::bigint,
                       COALESCE(SUM(estimated_ai_cost_inr), 0)::float,
                       COALESCE(SUM(estimated_revenue_inr), 0)::float,
                       COALESCE(SUM(estimated_margin_inr), 0)::float
                FROM metrics_daily_client
                GROUP BY metric_date
                ORDER BY metric_date DESC
                LIMIT 5
                """
            )
        ).all()
        msg_count = conn.execute(
            text("SELECT COUNT(*)::int FROM inbox_messages")
        ).scalar_one()

    print(f"inbox_messages total: {msg_count}")
    print("metrics_daily_client (date, client_rows):")
    if not daily:
        print("  (empty — no messages in lookback window, or run rollup after traffic)")
    for d in daily:
        print(
            f"  {d[0]}  rows={d[1]} ai_calls={d[2]} "
            f"cost_inr={d[3]:.4f} revenue_inr={d[4]:.4f} margin_inr={d[5]:.4f}"
        )
    print("metrics_hourly_system (newest 5 hours):")
    if not hourly:
        print("  (empty — run: python backend\\tools\\run_metrics_rollup_once.py)")
    for h in hourly:
        print(
            f"  {h[0]}  in={h[1]} ai={h[2]} agent={h[3]} dead_outbox={h[4]}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
