"""Register a candidate ops release (Chat Z).

Usage:
  python backend/tools/register_ops_release.py --build-id dev-20260522 --git-sha abc123
"""

from __future__ import annotations

import argparse

from backend.shared.db import engine
from backend.shared.release_manager import register_release


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--build-id", required=True)
    p.add_argument("--git-sha", default=None)
    p.add_argument("--artifact-hash", default=None)
    p.add_argument("--test-report-hash", default=None)
    p.add_argument("--notes", default=None)
    args = p.parse_args()

    with engine.begin() as conn:
        rid = register_release(
            conn,
            build_id=args.build_id,
            git_sha=args.git_sha,
            artifact_hash=args.artifact_hash,
            test_report_hash=args.test_report_hash,
            notes=args.notes,
        )
    print(f"OK: registered release id={rid} build_id={args.build_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
