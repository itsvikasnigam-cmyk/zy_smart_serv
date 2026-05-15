from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)

# ops_runtime_config keys (JSONB values; no migration required — rows optional)
URGENT_BYPASS_KEY = "ai.urgent_bypass_substrings"
NEEDS_OWNER_REPLY_KEY = "ai.needs_owner_data_customer_reply"

FALLBACK_ENABLED_KEY = "ai.fallback.enabled"
FALLBACK_USE_JUDGE_KEY = "ai.fallback.use_judge"
FALLBACK_QUALITY_THRESHOLD_KEY = "ai.fallback.quality_threshold"
FALLBACK_MAX_PRIMARY_TOKENS_KEY = "ai.fallback.max_primary_tokens"
FALLBACK_MAX_JUDGE_TOKENS_KEY = "ai.fallback.max_judge_tokens"

_AI_OPS_KEYS = (
    URGENT_BYPASS_KEY,
    NEEDS_OWNER_REPLY_KEY,
    FALLBACK_ENABLED_KEY,
    FALLBACK_USE_JUDGE_KEY,
    FALLBACK_QUALITY_THRESHOLD_KEY,
    FALLBACK_MAX_PRIMARY_TOKENS_KEY,
    FALLBACK_MAX_JUDGE_TOKENS_KEY,
)


@dataclass(frozen=True)
class AIEngineOpsBundle:
    """Snapshot of AI-related ops_runtime_config rows + safe defaults."""

    urgent_bypass_substrings: list[str]
    needs_owner_data_reply_override: str | None
    fallback_enabled: bool
    fallback_use_judge: bool
    fallback_quality_threshold: float
    fallback_max_primary_tokens: int
    fallback_max_judge_tokens: int


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


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(int(value))
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("true", "1", "yes", "on"):
            return True
        if s in ("false", "0", "no", "off", ""):
            return False
    return default


def _coerce_float(value: Any, default: float, *, lo: float = 0.0, hi: float = 1.0) -> float:
    if value is None:
        return default
    try:
        x = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, x))


def _coerce_int(value: Any, default: int, *, lo: int = 1, hi: int = 8192) -> int:
    if value is None:
        return default
    try:
        x = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, x))


def default_ai_engine_ops_bundle() -> AIEngineOpsBundle:
    return AIEngineOpsBundle(
        urgent_bypass_substrings=[],
        needs_owner_data_reply_override=None,
        fallback_enabled=False,
        fallback_use_judge=False,
        fallback_quality_threshold=0.65,
        fallback_max_primary_tokens=512,
        fallback_max_judge_tokens=256,
    )


def load_ai_engine_ops_bundle(engine: Any) -> AIEngineOpsBundle:
    """
    Read AI-related ops_runtime_config keys in one round-trip.

    On DB error, returns defaults (no LLM spend flags, no urgent strings).
    """
    base = default_ai_engine_ops_bundle()
    try:
        with engine.connect() as conn:
            q = text(
                """
                SELECT key, value_json
                FROM ops_runtime_config
                WHERE key IN (
                  :k0, :k1, :k2, :k3, :k4, :k5, :k6
                )
                """
            )
            rows = conn.execute(
                q,
                {
                    "k0": _AI_OPS_KEYS[0],
                    "k1": _AI_OPS_KEYS[1],
                    "k2": _AI_OPS_KEYS[2],
                    "k3": _AI_OPS_KEYS[3],
                    "k4": _AI_OPS_KEYS[4],
                    "k5": _AI_OPS_KEYS[5],
                    "k6": _AI_OPS_KEYS[6],
                },
            ).all()
    except Exception:
        logger.exception("ops_runtime_config read failed; using defaults for AI engine ops bundle")
        return base

    by_key = {r[0]: r[1] for r in rows}
    urgent = _coerce_string_list(by_key.get(URGENT_BYPASS_KEY))
    raw_owner = by_key.get(NEEDS_OWNER_REPLY_KEY)
    owner_override: str | None
    if raw_owner is None:
        owner_override = None
    else:
        s = _coerce_customer_reply(raw_owner, "")
        owner_override = s if s else None

    fb_enabled = _coerce_bool(by_key.get(FALLBACK_ENABLED_KEY), False)
    fb_judge = _coerce_bool(by_key.get(FALLBACK_USE_JUDGE_KEY), False)
    fb_thr = _coerce_float(by_key.get(FALLBACK_QUALITY_THRESHOLD_KEY), 0.65, lo=0.0, hi=1.0)
    fb_ptok = _coerce_int(by_key.get(FALLBACK_MAX_PRIMARY_TOKENS_KEY), 512, lo=32, hi=4096)
    fb_jtok = _coerce_int(by_key.get(FALLBACK_MAX_JUDGE_TOKENS_KEY), 256, lo=32, hi=2048)

    return AIEngineOpsBundle(
        urgent_bypass_substrings=urgent,
        needs_owner_data_reply_override=owner_override,
        fallback_enabled=fb_enabled,
        fallback_use_judge=fb_judge,
        fallback_quality_threshold=fb_thr,
        fallback_max_primary_tokens=fb_ptok,
        fallback_max_judge_tokens=fb_jtok,
    )


def load_ai_runtime_strings(engine: Any) -> tuple[list[str], str | None]:
    """Backward-compatible narrow loader used by older tests."""
    b = load_ai_engine_ops_bundle(engine)
    return b.urgent_bypass_substrings, b.needs_owner_data_reply_override
