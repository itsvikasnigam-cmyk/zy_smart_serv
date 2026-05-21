"""Postgres-first agent typing lock (Chat Q): block AI while an agent is typing."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

POLICY_KEY = "inbox.typing_lock.policy"
LEGACY_HARD_LOCK_KEY = "inbox.typing_hard_lock_enabled"

DEFAULT_POLICY: dict[str, Any] = {
    "enabled": True,
}


def merge_typing_lock_policy(value_json: Any | None) -> dict[str, Any]:
    merged = dict(DEFAULT_POLICY)
    if isinstance(value_json, dict):
        for k, v in value_json.items():
            merged[k] = v
    return merged


def _coerce_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("true", "1", "yes", "on"):
            return True
        if s in ("false", "0", "no", "off"):
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def is_typing_lock_enabled(conn: Connection) -> bool:
    """Respect ``inbox.typing_lock.policy`` and legacy ``inbox.typing_hard_lock_enabled``."""
    rows = conn.execute(
        text(
            """
            SELECT key, value_json
            FROM ops_runtime_config
            WHERE key IN (:policy, :legacy)
            """
        ),
        {"policy": POLICY_KEY, "legacy": LEGACY_HARD_LOCK_KEY},
    ).all()
    cfg = {r[0]: r[1] for r in rows}
    legacy = _coerce_bool(cfg.get(LEGACY_HARD_LOCK_KEY))
    if legacy is not None:
        return legacy
    policy = merge_typing_lock_policy(cfg.get(POLICY_KEY))
    return bool(policy.get("enabled", True))


def has_active_agent_typing(conn: Connection, chat_id: str) -> tuple[bool, str | None]:
    """
    True when any agent has a non-expired ``chat_presence`` row with ``state='typing'``.
    Returns ``(active, typing_user_id)``.
    """
    row = conn.execute(
        text(
            """
            SELECT user_id::text
            FROM chat_presence
            WHERE chat_id = CAST(:cid AS uuid)
              AND state = 'typing'
              AND expires_at > now()
            ORDER BY expires_at DESC
            LIMIT 1
            """
        ),
        {"cid": chat_id},
    ).fetchone()
    if not row:
        return False, None
    return True, str(row[0])
