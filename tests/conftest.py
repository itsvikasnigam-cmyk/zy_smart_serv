"""Pytest hooks for the ``tests/`` package."""

from __future__ import annotations

import os

# Optional Postgres integration (Chat N): keep default ``python -m pytest tests/`` output
# free of extra skips — omit the module unless explicitly enabled + DATABASE_URL set.
if not (
    os.environ.get("RUN_POSTGRES_INTEGRATION") == "1"
    and os.environ.get("DATABASE_URL", "").strip()
):
    collect_ignore = ["test_postgres_integration_optional.py"]
