"""Run one metrics rollup cycle (fills metrics_* tables for Dash charts).

Usage (repo root):

    python backend/tools/run_metrics_rollup_once.py
"""

from __future__ import annotations

import sys

from backend.workers.metrics_rollup_worker import run_once


def main() -> int:
    run_once()
    print("OK: metrics rollup completed one cycle.")
    print("Next: python backend\\tools\\check_metrics_rollups.py")
    print("Then refresh super-admin Dash in Flutter (8085 must be running).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
