"""Flush buffered telemetry from Redis stream into Postgres (Chat X).

Usage:
  REDIS_ENABLED=true python backend/tools/flush_redis_telemetry.py
  REDIS_ENABLED=true python backend/tools/flush_redis_telemetry.py --max 1000
"""

from __future__ import annotations

import argparse
import sys

from backend.shared.db import engine
from backend.shared.redis_client import redis_feature_enabled
from backend.shared.redis_telemetry import flush_telemetry_stream_to_postgres


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--max", type=int, default=500, help="Max stream entries per run")
    args = p.parse_args()

    if not redis_feature_enabled():
        print("SKIP: REDIS_ENABLED is false")
        return 0
    n = flush_telemetry_stream_to_postgres(engine, max_entries=args.max)
    print(f"OK: flushed {n} telemetry rows to Postgres")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
