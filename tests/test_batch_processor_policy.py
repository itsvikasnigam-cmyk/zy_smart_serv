"""Unit tests for Chat C batch_processor policy helpers (U2, second-line paywall)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.workers.batch_processor import apply_u2_strict_after_ai, second_line_paywall_block


def test_apply_u2_strict_converts_urgent_reply_to_handoff() -> None:
    ai = {
        "action": "REPLY",
        "reply_text": "Thanks — we've received your message and flagged it as time-sensitive.",
        "intent": "urgent",
        "routing_intent": "urgent",
        "confidence": 0.88,
        "language": "en",
        "handoff_reason": None,
        "missing_fields": [],
        "risk_reason": None,
    }
    out = apply_u2_strict_after_ai(ai)
    assert out["action"] == "HANDOFF"
    assert out["handoff_reason"] == "urgent_time_sensitive_u2"
    assert out.get("reply_text") is None
    assert out["intent"] == "urgent"


def test_apply_u2_strict_intent_urgent_only() -> None:
    ai = {
        "action": "REPLY",
        "reply_text": "x",
        "intent": "urgent",
        "routing_intent": "general",
        "confidence": 0.5,
        "language": "en",
        "handoff_reason": None,
        "missing_fields": [],
        "risk_reason": None,
    }
    out = apply_u2_strict_after_ai(ai)
    assert out["action"] == "HANDOFF"


def test_apply_u2_strict_routing_intent_urgent_only() -> None:
    ai = {
        "action": "REPLY",
        "reply_text": "x",
        "intent": "general_ack",
        "routing_intent": "urgent",
        "confidence": 0.5,
        "language": "en",
        "handoff_reason": None,
        "missing_fields": [],
        "risk_reason": None,
    }
    out = apply_u2_strict_after_ai(ai)
    assert out["action"] == "HANDOFF"


def test_apply_u2_strict_leaves_general_reply() -> None:
    ai = {
        "action": "REPLY",
        "reply_text": "Thanks — I've noted that: hello",
        "intent": "general_ack",
        "routing_intent": "general",
        "confidence": 0.72,
        "language": "en",
        "handoff_reason": None,
        "missing_fields": [],
        "risk_reason": None,
    }
    assert apply_u2_strict_after_ai(ai) == ai


def test_apply_u2_strict_leaves_handoff() -> None:
    ai = {
        "action": "HANDOFF",
        "reply_text": None,
        "intent": "human_request",
        "routing_intent": "human_request",
        "confidence": 0.85,
        "language": "en",
        "handoff_reason": "customer_requested_human",
        "missing_fields": [],
        "risk_reason": None,
    }
    assert apply_u2_strict_after_ai(ai) == ai


def test_apply_u2_strict_non_dict_passthrough() -> None:
    assert apply_u2_strict_after_ai([]) == []  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("entitlement", "trial_end", "inbound_today", "limits", "expect_reason"),
    [
        ("churned", None, 0, {}, "churned"),
        ("trial", datetime.now(timezone.utc) - timedelta(days=1), 0, {}, "trial_expired"),
        ("paid", None, 100, {"paid": {"soft_warn": 80, "hard_block": 100}}, "usage_hard"),
        ("paid", None, 99, {"paid": {"soft_warn": 80, "hard_block": 100}}, None),
        ("trial", datetime.now(timezone.utc) + timedelta(days=1), 500, {"trial": {"hard_block": 10}}, "usage_hard"),
    ],
)
def test_second_line_paywall_block(
    entitlement: str,
    trial_end: datetime | None,
    inbound_today: int,
    limits: dict,
    expect_reason: str | None,
) -> None:
    reason, suffix = second_line_paywall_block(
        entitlement=entitlement,
        trial_end=trial_end,
        inbound_today=inbound_today,
        limits_root=limits,
    )
    assert reason == expect_reason
    if expect_reason:
        assert suffix is not None
