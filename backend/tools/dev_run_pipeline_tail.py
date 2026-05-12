"""
After inbound: wait for debounce, run batch_processor until work, then outbox_sender.

Usage (repo root, PYTHONPATH + DATABASE_URL set):
  python backend/tools/dev_run_pipeline_tail.py

Env:
  AI_ENGINE_URL       default http://127.0.0.1:8083
  DEV_SMOKE_WAIT_SEC  seconds to sleep before first batch (default 12)
"""
from __future__ import annotations

import os
import sys
import time


def main() -> int:
    wait = int(os.environ.get("DEV_SMOKE_WAIT_SEC", "12"))
    print(f"==> sleep {wait}s for inbound debounce (OPEN batch process_after)...")
    time.sleep(wait)

    from backend.workers.batch_processor import run_once as batch_once

    batch_total = 0
    for i in range(12):
        n = batch_once()
        batch_total += n
        print(f"==> batch try {i + 1}: processed {n} (cumulative {batch_total})")
        if n > 0:
            break
        time.sleep(2)
    else:
        print(
            "WARN: batch still 0 after retries. Check: AI_ENGINE_URL, "
            "uvicorn ai_engine on 8083, and latest OPEN batch process_after in DB.",
            file=sys.stderr,
        )

    if os.environ.get("META_ACCESS_TOKEN") and "--skip-outbox" not in sys.argv:
        from backend.workers.outbox_sender import run_once as out_once

        for j in range(8):
            t = out_once()
            print(f"==> outbox try {j + 1}: return {t}")
            if t > 0:
                break
            time.sleep(1)
    else:
        print("==> skip outbox (META_ACCESS_TOKEN not set)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
