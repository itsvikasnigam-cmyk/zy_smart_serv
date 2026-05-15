"""Blueprint acceptance scenarios (unit-level; no full E2E Meta)."""

from __future__ import annotations

from backend.apps.ai_engine.helpers.respond_logic import (
    NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED,
    decide_response,
)
from backend.workers.batch_processor import apply_u2_strict_after_ai


def test_u2_urgent_reply_normalized_to_handoff() -> None:
    payload = {
        "action": "REPLY",
        "reply_text": "urgent line",
        "intent": "urgent",
        "routing_intent": "urgent",
    }
    out = apply_u2_strict_after_ai(payload)
    assert out["action"] == "HANDOFF"
    assert out.get("reply_text") in (None, "")
    assert out.get("handoff_reason") == "urgent_time_sensitive_u2"


def test_needs_owner_fixed_customer_string_stable() -> None:
    d = decide_response(
        "I need a refund for my invoice",
        urgent_bypass_substrings=[],
        needs_owner_customer_reply=NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED,
    )
    assert d.action == "NEEDS_OWNER_DATA"
    assert d.reply_text == NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED


def test_human_request_handoff() -> None:
    d = decide_response(
        "please connect me to a human agent",
        urgent_bypass_substrings=[],
        needs_owner_customer_reply=NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED,
    )
    assert d.action == "HANDOFF"
    assert d.handoff_reason == "customer_requested_human"
