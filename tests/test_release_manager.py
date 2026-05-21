from __future__ import annotations

from backend.shared.release_manager import (
    merge_canary_policy,
    should_route_chat_to_canary,
    policy_from_merged,
)


def test_canary_bucket_stable() -> None:
    p = policy_from_merged({"enabled": True, "percent": 50})
    a = should_route_chat_to_canary("chat-abc", p)
    b = should_route_chat_to_canary("chat-abc", p)
    assert a == b


def test_canary_disabled() -> None:
    p = policy_from_merged({"enabled": False, "percent": 100})
    assert should_route_chat_to_canary("chat-abc", p) is False


def test_disable_defaults() -> None:
    m = merge_canary_policy(None)
    assert m["enabled"] is False
    assert m["percent"] == 0
