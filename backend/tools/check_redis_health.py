"""Chat X: Redis connectivity and feature flags.

Usage:
  python backend/tools/check_redis_health.py
  REDIS_ENABLED=true python backend/tools/check_redis_health.py
"""

from __future__ import annotations

import json
import sys

from backend.shared.config import settings
from backend.shared.redis_client import check_redis_health, get_redis_client, redis_feature_enabled


def main() -> int:
    h = check_redis_health()
    print(json.dumps({
        "redis_enabled_env": settings.redis_enabled,
        "redis_url": settings.redis_url,
        "enabled": h.enabled,
        "reachable": h.reachable,
        "dedupe_mirror": h.dedupe_mirror,
        "telemetry_buffer": h.telemetry_buffer,
        "error": h.error,
        "lazy_client": get_redis_client() is not None,
    }, indent=2))
    if not redis_feature_enabled():
        print("\nOK: Redis disabled (Postgres-only mode). Set REDIS_ENABLED=true to enable.")
        return 0
    if not h.reachable:
        print("\nWARN: REDIS_ENABLED but not reachable — app continues without Redis.", file=sys.stderr)
        return 1
    print("\nOK: Redis reachable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
