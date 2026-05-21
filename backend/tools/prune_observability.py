"""Delete old telemetry_trace_logs and misfires_log rows (Chat V retention).

Usage:
  python backend/tools/prune_observability.py
  python backend/tools/prune_observability.py --days 30 --dry-run
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import text

from backend.shared.db import engine
from backend.shared.privacy_config import load_privacy_policy_engine


def main() -> int:
    p = argparse.ArgumentParser(description="Prune observability tables by age.")
    p.add_argument("--days", type=int, default=None, help="Override privacy.policy retention days")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    policy = load_privacy_policy_engine(engine)
    days = args.days if args.days is not None else policy.telemetry_retention_days

    with engine.connect() as conn:
        trace_count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM telemetry_trace_logs
                WHERE created_at < now() - make_interval(days => :days)
                """
            ),
            {"days": days},
        ).scalar_one()
        misfire_count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM misfires_log
                WHERE created_at < now() - make_interval(days => :days)
                """
            ),
            {"days": days},
        ).scalar_one()

    print(f"Retention: {days} days")
    print(f"telemetry_trace_logs rows to delete: {trace_count}")
    print(f"misfires_log rows to delete: {misfire_count}")

    if args.dry_run:
        print("(dry-run — no deletes)")
        return 0

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                DELETE FROM telemetry_trace_logs
                WHERE created_at < now() - make_interval(days => :days)
                """
            ),
            {"days": days},
        )
        conn.execute(
            text(
                """
                DELETE FROM misfires_log
                WHERE created_at < now() - make_interval(days => :days)
                """
            ),
            {"days": days},
        )
    print("OK: prune complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
