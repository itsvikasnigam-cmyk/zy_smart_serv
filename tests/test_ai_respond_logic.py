from __future__ import annotations

import pytest

from backend.apps.ai_engine.helpers.respond_logic import (
    NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED,
    decide_response,
    decision_to_response_dict,
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


@pytest.mark.parametrize(
    "batch_text",
    [
        "I was overcharged — need a refund",
        "Please email the invoice for March",
        "I want a custom quote for 500 units",
        "We are considering legal action",
    ],
)
def test_needs_owner_data_routing_intent_owner_data_variants(batch_text: str) -> None:
    d = decide_response(
        batch_text,
        urgent_bypass_substrings=[],
        needs_owner_customer_reply=NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED,
    )
    assert d.action == "NEEDS_OWNER_DATA"
    assert d.routing_intent == "owner_data"


@pytest.mark.parametrize(
    ("batch_text", "urgent_substrings", "expected_routing"),
    [
        ("I'd like to talk to a human please", [], "human_request"),
        ("Urgent: delivery failed today", ["urgent"], "urgent"),
        ("What time do you close?", [], "general"),
    ],
)
def test_routing_intent_classification(
    batch_text: str,
    urgent_substrings: list[str],
    expected_routing: str,
) -> None:
    d = decide_response(
        batch_text,
        urgent_bypass_substrings=urgent_substrings,
        needs_owner_customer_reply=NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED,
    )
    assert d.routing_intent == expected_routing


def test_decision_to_response_dict_stable_keys_for_batch_processor() -> None:
    """Keys/types must stay aligned with ``AIResponse`` and ``batch_processor`` ``r.json()``."""
    d = decide_response(
        "invoice question",
        urgent_bypass_substrings=[],
        needs_owner_customer_reply=NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED,
    )
    payload = decision_to_response_dict(d)
    assert set(payload.keys()) == {
        "action",
        "reply_text",
        "intent",
        "routing_intent",
        "confidence",
        "language",
        "handoff_reason",
        "missing_fields",
        "risk_reason",
    }
    assert isinstance(payload["missing_fields"], list)
