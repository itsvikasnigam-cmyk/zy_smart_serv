"""Chat X: optional Redis client — disabled by default; Postgres stays authoritative."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from backend.shared.config import Settings, settings

log = logging.getLogger("redis_client")

try:
    import redis as _redis_lib
except ImportError:  # pragma: no cover
    _redis_lib = None  # type: ignore[assignment]

_client: Any | None = None
_client_init_attempted = False


@dataclass(frozen=True)
class RedisHealth:
    enabled: bool
    configured: bool
    reachable: bool
    dedupe_mirror: bool
    telemetry_buffer: bool
    url: str
    error: str | None = None


def redis_feature_enabled(cfg: Settings | None = None) -> bool:
    c = cfg or settings
    return bool(c.redis_enabled)


def redis_dedupe_mirror_enabled(cfg: Settings | None = None) -> bool:
    c = cfg or settings
    return redis_feature_enabled(c) and bool(c.redis_dedupe_mirror_enabled)


def redis_telemetry_buffer_enabled(cfg: Settings | None = None) -> bool:
    c = cfg or settings
    return redis_feature_enabled(c) and bool(c.redis_telemetry_buffer_enabled)


def _dedupe_key(meta_msg_id: str) -> str:
    return f"processed:{meta_msg_id.strip()}"


def get_redis_client(cfg: Settings | None = None) -> Any | None:
    """Lazy singleton. Returns None when disabled, package missing, or ping fails."""
    global _client, _client_init_attempted
    c = cfg or settings
    if not redis_feature_enabled(c):
        return None
    if _redis_lib is None:
        log.warning("redis package not installed; pip install redis")
        return None
    if _client_init_attempted:
        return _client
    _client_init_attempted = True
    try:
        client = _redis_lib.Redis.from_url(c.redis_url, decode_responses=True)
        client.ping()
        _client = client
    except Exception as exc:
        log.warning("Redis unavailable (%s); continuing without Redis", exc)
        _client = None
    return _client


def check_redis_health(cfg: Settings | None = None) -> RedisHealth:
    c = cfg or settings
    enabled = redis_feature_enabled(c)
    if not enabled:
        return RedisHealth(
            enabled=False,
            configured=False,
            reachable=False,
            dedupe_mirror=False,
            telemetry_buffer=False,
            url=c.redis_url,
            error=None,
        )
    if _redis_lib is None:
        return RedisHealth(
            enabled=True,
            configured=True,
            reachable=False,
            dedupe_mirror=redis_dedupe_mirror_enabled(c),
            telemetry_buffer=redis_telemetry_buffer_enabled(c),
            url=c.redis_url,
            error="redis package not installed",
        )
    try:
        client = _redis_lib.Redis.from_url(c.redis_url, decode_responses=True)
        client.ping()
        return RedisHealth(
            enabled=True,
            configured=True,
            reachable=True,
            dedupe_mirror=redis_dedupe_mirror_enabled(c),
            telemetry_buffer=redis_telemetry_buffer_enabled(c),
            url=c.redis_url,
            error=None,
        )
    except Exception as exc:
        return RedisHealth(
            enabled=True,
            configured=True,
            reachable=False,
            dedupe_mirror=redis_dedupe_mirror_enabled(c),
            telemetry_buffer=redis_telemetry_buffer_enabled(c),
            url=c.redis_url,
            error=str(exc)[:500],
        )


def meta_msg_processed_mirror(meta_msg_id: str, *, cfg: Settings | None = None) -> bool:
    """True if dedupe mirror key exists (fast duplicate webhook skip)."""
    mid = (meta_msg_id or "").strip()
    if not mid or not redis_dedupe_mirror_enabled(cfg):
        return False
    client = get_redis_client(cfg)
    if not client:
        return False
    try:
        return bool(client.exists(_dedupe_key(mid)))
    except Exception:
        log.debug("redis dedupe exists failed", exc_info=True)
        return False


def mark_meta_msg_processed_mirror(meta_msg_id: str, *, cfg: Settings | None = None) -> None:
    """Set dedupe mirror after Postgres accepted the inbound row."""
    mid = (meta_msg_id or "").strip()
    if not mid or not redis_dedupe_mirror_enabled(cfg):
        return
    c = cfg or settings
    client = get_redis_client(c)
    if not client:
        return
    try:
        client.set(_dedupe_key(mid), "1", ex=int(c.redis_dedupe_ttl_seconds))
    except Exception:
        log.debug("redis dedupe set failed", exc_info=True)


def reset_redis_client_for_tests() -> None:
    """Test helper: clear lazy client cache."""
    global _client, _client_init_attempted
    _client = None
    _client_init_attempted = False
