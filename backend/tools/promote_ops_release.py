"""Promote a registered release (Chat Z).

Usage:
  python backend/tools/promote_ops_release.py --build-id dev-20260522
  python backend/tools/promote_ops_release.py --build-id dev-20260522 --canary-percent 5
"""

from __future__ import annotations

import argparse

from backend.shared.db import engine
from backend.shared.release_manager import promote_release


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--build-id", required=True)
    p.add_argument("--canary-percent", type=int, default=0)
    p.add_argument("--canary-model", default=None)
    p.add_argument("--note", default=None)
    args = p.parse_args()

    with engine.begin() as conn:
        rid = promote_release(
            conn,
            build_id=args.build_id,
            canary_percent=args.canary_percent,
            canary_primary_model=args.canary_model,
            note=args.note,
        )
    print(f"OK: promoted id={rid} build_id={args.build_id} canary={args.canary_percent}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
