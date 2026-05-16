"""Insert a test ops alert (and auto-trigger SOP run if map + slug exist).

Usage (repo root, venv + DATABASE_URL):

    python backend/tools/fire_test_alert.py
    python backend/tools/fire_test_alert.py --type BILLING_WEBHOOK_PROCESSING_ERROR
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from backend.shared.db import engine
from backend.shared.ops_alerts import insert_ops_alert_event


def main() -> int:
    parser = argparse.ArgumentParser(description="Fire one test ops alert (+ SOP auto-run).")
    parser.add_argument(
        "--type",
        default="BILLING_WEBHOOK_PROCESSING_ERROR",
        help="alert_type (must exist in alerts.sop_trigger_map for a run)",
    )
    args = parser.parse_args()
    alert_type = args.type.strip()
    bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    dedupe_key = f"dev_test_alert:{alert_type}:{bucket}"

    with engine.begin() as conn:
        inserted = insert_ops_alert_event(
            conn,
            alert_type=alert_type,
            severity="warning",
            summary=f"Dev test alert ({alert_type})",
            detail={"source": "fire_test_alert.py"},
            dedupe_key=dedupe_key,
        )

    if inserted:
        print(f"OK: inserted alert {alert_type} (dedupe_key={dedupe_key})")
        print("Check super-admin Runs tab for trigger_type=alert, or:")
        print("  SELECT id, trigger_type, created_at FROM ops_run_logs ORDER BY created_at DESC LIMIT 5;")
    else:
        print("SKIP: duplicate dedupe_key (alert not inserted, no new run)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
