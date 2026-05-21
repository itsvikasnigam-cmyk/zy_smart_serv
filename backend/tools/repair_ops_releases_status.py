"""Repair ops_releases.status CHECK when promote fails (Chat Z).

Usage:
  python backend/tools/repair_ops_releases_status.py
"""

from __future__ import annotations

import sys

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT conname, pg_get_constraintdef(c.oid)
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                WHERE t.relname = 'ops_releases' AND c.contype = 'c'
                """
            )
        ).all()
        print("=== CHECK constraints on ops_releases ===")
        for r in rows or []:
            print(r[0], ":", r[1])

        conn.execute(text("ALTER TABLE ops_releases DROP CONSTRAINT IF EXISTS ops_releases_status_check"))
        conn.execute(
            text(
                """
                UPDATE ops_releases SET status = 'promoted'
                WHERE status IN ('active', 'production', 'live')
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE ops_releases SET status = 'candidate'
                WHERE status NOT IN ('candidate', 'promoted', 'rolled_back')
                """
            )
        )
        conn.execute(
            text(
                """
                ALTER TABLE ops_releases
                ADD CONSTRAINT ops_releases_status_check
                CHECK (status IN ('candidate', 'promoted', 'rolled_back'))
                """
            )
        )
    print("OK: ops_releases_status_check repaired (candidate | promoted | rolled_back)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
