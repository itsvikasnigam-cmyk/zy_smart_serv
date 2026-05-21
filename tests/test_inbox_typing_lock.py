"""Chat Q: typing lock helpers (no Postgres)."""

from __future__ import annotations

from backend.shared.inbox_typing_lock import merge_typing_lock_policy


def test_merge_typing_lock_policy_defaults() -> None:
    p = merge_typing_lock_policy(None)
    assert p["enabled"] is True


def test_merge_typing_lock_policy_override() -> None:
    p = merge_typing_lock_policy({"enabled": False})
    assert p["enabled"] is False
