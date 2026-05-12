from __future__ import annotations

import pytest

from backend.apps.ai_engine.helpers.respond_logic import (
    NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED,
    decide_response,
    detect_language,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", "auto"),
        ("   ", "auto"),
        ("Hello there", "en"),
        ("नमस्ते कैसे हो", "hi"),
    ],
)
def test_detect_language(text: str, expected: str) -> None:
    assert detect_language(text) == expected


def test_needs_owner_data_routing_intent_and_fixed_reply() -> None:
    d = decide_response(
        "I need a refund for my last order",
        urgent_bypass_substrings=[],
        needs_owner_customer_reply=NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED,
    )
    assert d.action == "NEEDS_OWNER_DATA"
    assert d.routing_intent == "owner_data"
    assert d.reply_text == NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED
    assert "owner_confirmation" in d.missing_fields


def test_needs_owner_data_custom_reply_override_from_caller() -> None:
    custom = "Custom owner-pending message."
    d = decide_response(
        "Please send the invoice PDF",
        urgent_bypass_substrings=[],
        needs_owner_customer_reply=custom,
    )
    assert d.action == "NEEDS_OWNER_DATA"
    assert d.routing_intent == "owner_data"
    assert d.reply_text == custom


def test_handoff_beats_urgent_and_owner_data() -> None:
    d = decide_response(
        "I want a refund and need to speak to a human",
        urgent_bypass_substrings=["refund"],
        needs_owner_customer_reply=NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED,
    )
    assert d.action == "HANDOFF"
    assert d.routing_intent == "human_request"


def test_urgent_bypass_from_ops_list() -> None:
    d = decide_response(
        "This is an emergency — package was stolen",
        urgent_bypass_substrings=["emergency"],
        needs_owner_customer_reply=NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED,
    )
    assert d.action == "REPLY"
    assert d.routing_intent == "urgent"


def test_urgent_bypass_before_owner_data_when_no_human_request() -> None:
    d = decide_response(
        "Emergency: also mention invoice number 12",
        urgent_bypass_substrings=["emergency"],
        needs_owner_customer_reply=NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED,
    )
    assert d.action == "REPLY"
    assert d.routing_intent == "urgent"


def test_default_reply_routing_intent_general() -> None:
    d = decide_response(
        "What are your store hours tomorrow?",
        urgent_bypass_substrings=[],
        needs_owner_customer_reply=NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED,
    )
    assert d.action == "REPLY"
    assert d.routing_intent == "general"
