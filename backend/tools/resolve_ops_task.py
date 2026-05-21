"""Resolve an open ops_task with audit event (Chat W).

Usage:
  python backend/tools/resolve_ops_task.py --task-id <uuid> --note "Fixed dead letter queue"
"""

from __future__ import annotations

import argparse
import sys

from backend.shared.db import engine
from backend.shared.ops_tasks import resolve_ops_task


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--task-id", required=True)
    p.add_argument("--note", default="Resolved via CLI")
    p.add_argument("--user-id", default=None, help="api_users.id for audit (optional)")
    args = p.parse_args()

    with engine.begin() as conn:
        ok = resolve_ops_task(
            conn,
            task_id=args.task_id.strip(),
            resolved_by_user_id=args.user_id.strip() if args.user_id else None,
            resolution_note=args.note,
        )
    if not ok:
        print("FAIL: task not found or not open", file=sys.stderr)
        return 1
    print(f"OK: resolved task {args.task_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
