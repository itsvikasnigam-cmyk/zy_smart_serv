"""List ops_tasks (Chat W).

Usage:
  python backend/tools/list_ops_tasks.py
  python backend/tools/list_ops_tasks.py --status open
"""

from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--status", default="open", help="open | resolved | cancelled | all")
    p.add_argument("--limit", type=int, default=20)
    args = p.parse_args()

    where = ""
    params: dict = {"lim": args.limit}
    if args.status != "all":
        where = "WHERE status = :st"
        params["st"] = args.status

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT id::text, status, priority, alert_type, title, created_at, alert_dedupe_key
                FROM ops_tasks
                {where}
                ORDER BY created_at DESC
                LIMIT :lim
                """
            ),
            params,
        ).all()

    if not rows:
        print("(no tasks)")
        return 0
    for r in rows:
        print(json.dumps({
            "id": r[0],
            "status": r[1],
            "priority": r[2],
            "alert_type": r[3],
            "title": r[4],
            "created_at": r[5].isoformat() if r[5] else None,
            "alert_dedupe_key": r[6],
        }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
