"""Rollback a release and disable canary (Chat Z).

Usage:
  python backend/tools/rollback_ops_release.py --build-id dev-20260522 --note "misfire spike"
"""

from __future__ import annotations

import argparse

from backend.shared.db import engine
from backend.shared.release_manager import rollback_release


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--build-id", required=True)
    p.add_argument("--note", default="CLI rollback")
    args = p.parse_args()

    with engine.begin() as conn:
        rid = rollback_release(conn, build_id=args.build_id, note=args.note)
    print(f"OK: rolled back id={rid} build_id={args.build_id}; canary disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
