"""Chat P: customer service window policy and outbound resolution (no Postgres)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.shared.wa_service_window import (
    ServiceWindowExpiredError,
    is_session_window_open,
    merge_service_window_policy,
    parse_meta_expiration_timestamp,
    resolve_session_outbound,
    window_expires_after_customer_message,
)


def test_merge_service_window_policy_normalizes_kinds() -> None:
    p = merge_service_window_policy({"session_kinds": ["ai_reply", "agent_reply"]})
    assert "AI_REPLY" in p["session_kinds"]


def test_is_session_window_open_from_expires_at() -> None:
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    policy = merge_service_window_policy(None)
    assert is_session_window_open(
        expires_at=now + timedelta(hours=1),
        last_customer_msg_at=None,
        policy=policy,
        now=now,
    )
    assert not is_session_window_open(
        expires_at=now - timedelta(minutes=1),
        last_customer_msg_at=None,
        policy=policy,
        now=now,
    )


def test_is_session_window_open_fallback_last_customer_msg() -> None:
    now = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)
    policy = merge_service_window_policy({"window_hours": 24, "use_last_customer_msg_fallback": True})
    recent = now - timedelta(hours=2)
    assert is_session_window_open(
        expires_at=None,
        last_customer_msg_at=recent,
        policy=policy,
        now=now,
    )
    old = now - timedelta(hours=30)
    assert not is_session_window_open(
        expires_at=None,
        last_customer_msg_at=old,
        policy=policy,
        now=now,
    )


def test_resolve_session_outbound_inside_window() -> None:
    policy = merge_service_window_policy(None)
    mode, body = resolve_session_outbound(
        kind="AI_REPLY",
        body_text="hello",
        window_open=True,
        policy=policy,
    )
    assert mode == "text"
    assert body == "hello"


def test_resolve_session_outbound_template_fallback() -> None:
    policy = merge_service_window_policy(
        {
            "fallback_templates": {
                "default": {"template_name": "hello_world", "language": "en_US"},
            }
        }
    )
    mode, body = resolve_session_outbound(
        kind="AI_REPLY",
        body_text="long ai reply",
        window_open=False,
        policy=policy,
    )
    assert mode == "template"
    assert "hello_world" in body


def test_resolve_session_outbound_raises_without_template() -> None:
    policy = merge_service_window_policy({"fallback_templates": {}})
    with pytest.raises(ServiceWindowExpiredError):
        resolve_session_outbound(
            kind="AGENT_REPLY",
            body_text="hi",
            window_open=False,
            policy=policy,
        )


def test_parse_meta_expiration_timestamp_unix() -> None:
    exp = parse_meta_expiration_timestamp(1710000000)
    assert exp is not None
    assert exp.tzinfo is not None


def test_window_expires_after_customer_message() -> None:
    at = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    exp = window_expires_after_customer_message(at=at, window_hours=24)
    assert exp == at + timedelta(hours=24)
