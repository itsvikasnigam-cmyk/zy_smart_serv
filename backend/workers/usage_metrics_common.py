"""Shared helpers for Chat K usage + metrics workers (no imports from batch_processor)."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

USAGE_DAILY_LIMITS_KEY = "usage.daily_inbound_limits"
CURSOR_KEY_INBOX_MESSAGES = "inbox_messages_usage"


def utc_calendar_date(ts: datetime) -> date:
    """Calendar day in UTC for usage_date / metric_date (aligns with SQL timezone('utc', ts)::date)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc).date()


def _coerce_limit_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def load_daily_inbound_limits_json(conn: Connection) -> dict[str, Any]:
    row = conn.execute(
        text("SELECT value_json FROM ops_runtime_config WHERE key = :k"),
        {"k": USAGE_DAILY_LIMITS_KEY},
    ).fetchone()
    if not row or row[0] is None:
        return {}
    raw = row[0]
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    try:
        return dict(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return {}


def plan_soft_hard(limits: dict[str, Any], entitlement_plan: str) -> tuple[int | None, int | None]:
    """
    Returns (soft_warn, hard_block) inbound message counts for the calendar day.
    None means unset / do not enforce that side.
    """
    entry = limits.get(entitlement_plan) or limits.get("_default")
    if not isinstance(entry, dict):
        return (None, None)
    return (_coerce_limit_int(entry.get("soft_warn")), _coerce_limit_int(entry.get("hard_block")))


def should_mark_soft(inbound: int, soft: int | None) -> bool:
    return soft is not None and inbound >= soft


def should_mark_hard(inbound: int, hard: int | None) -> bool:
    return hard is not None and inbound >= hard
