"""Print recent telemetry + misfires (Phase 5).

Usage:
  cd ...\\empty-window; . .\\dev-env.ps1
  python backend/tools/show_observability_recent.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    with engine.connect() as conn:
        traces = conn.execute(
            text(
                """
                SELECT service, route, latency_ms, status, trace_id, created_at
                FROM telemetry_trace_logs
                ORDER BY created_at DESC
                LIMIT 10
                """
            )
        ).all()
        misfires = conn.execute(
            text(
                """
                SELECT source, reason, batch_text_preview, created_at
                FROM misfires_log
                ORDER BY created_at DESC
                LIMIT 10
                """
            )
        ).all()
    print("=== telemetry_trace_logs (last 10) ===")
    for row in traces or []:
        print(row)
    if not traces:
        print("(none - run migration 0020 and send inbound / ai/respond)")
    print("\n=== misfires_log (last 10) ===")
    for row in misfires or []:
        print(row)
    if not misfires:
        print("(none)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
