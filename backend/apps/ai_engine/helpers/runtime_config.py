from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)

# ops_runtime_config keys (JSONB values; no migration required — rows optional)
URGENT_BYPASS_KEY = "ai.urgent_bypass_substrings"
NEEDS_OWNER_REPLY_KEY = "ai.needs_owner_data_customer_reply"


def _coerce_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
        return out
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return _coerce_string_list(parsed)
        except json.JSONDecodeError:
            return [value.strip()]
    return []


def _coerce_customer_reply(value: Any, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def load_ai_runtime_strings(engine: Any) -> tuple[list[str], str | None]:
    """
    Read urgent bypass substrings and optional NEEDS_OWNER_DATA customer reply override.

    Returns (urgent_substrings, owner_reply_override_or_none).
    On any DB error, returns ([], None) so the engine still serves /ai/respond.
    """
    try:
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT key, value_json
                    FROM ops_runtime_config
                    WHERE key IN (:k_urgent, :k_owner)
                    """
                ),
                {"k_urgent": URGENT_BYPASS_KEY, "k_owner": NEEDS_OWNER_REPLY_KEY},
            ).all()
    except Exception:
        logger.exception("ops_runtime_config read failed; using defaults for AI runtime strings")
        return [], None

    by_key = {r[0]: r[1] for r in rows}
    urgent = _coerce_string_list(by_key.get(URGENT_BYPASS_KEY))
    raw_owner = by_key.get(NEEDS_OWNER_REPLY_KEY)
    owner_override: str | None
    if raw_owner is None:
        owner_override = None
    else:
        s = _coerce_customer_reply(raw_owner, "")
        owner_override = s if s else None
    return urgent, owner_override
