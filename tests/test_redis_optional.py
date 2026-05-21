from __future__ import annotations

from backend.shared.config import Settings
from backend.shared.redis_client import (
    _dedupe_key,
    check_redis_health,
    meta_msg_processed_mirror,
    redis_dedupe_mirror_enabled,
    redis_feature_enabled,
    reset_redis_client_for_tests,
)


def test_redis_disabled_by_default() -> None:
    cfg = Settings(redis_enabled=False)
    assert not redis_feature_enabled(cfg)
    assert not redis_dedupe_mirror_enabled(cfg)
    h = check_redis_health(cfg)
    assert h.enabled is False
    assert h.reachable is False
    assert meta_msg_processed_mirror("wamid.123", cfg=cfg) is False


def test_dedupe_key_format() -> None:
    assert _dedupe_key("wamid.dev.1") == "processed:wamid.dev.1"


def test_reset_client_cache() -> None:
    reset_redis_client_for_tests()
