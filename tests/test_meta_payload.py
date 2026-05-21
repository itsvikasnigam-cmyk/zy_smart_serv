from __future__ import annotations

from backend.apps.wa_gateway.meta_payload import (
    extract_inbound_messages,
    normalize_customer_phone_for_route,
)


def test_normalize_customer_phone_for_route_strips_non_digits() -> None:
    assert normalize_customer_phone_for_route(" +91 98765 43210 ") == "919876543210"
    assert normalize_customer_phone_for_route("15551234567") == "15551234567"


def test_extract_inbound_messages_text_message() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "123456789"},
                            "messages": [
                                {
                                    "id": "wamid.HBgM",
                                    "from": "15551234567",
                                    "timestamp": "1710000000",
                                    "type": "text",
                                    "text": {"body": "Hello from tests"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    msgs = extract_inbound_messages(payload)
    assert len(msgs) == 1
    m = msgs[0]
    assert m.meta_msg_id == "wamid.HBgM"
    assert m.from_phone == "15551234567"
    assert m.to_phone_number_id == "123456789"
    assert m.timestamp == 1710000000
    assert m.text == "Hello from tests"
    assert m.raw["type"] == "text"


def test_extract_inbound_messages_non_text_uses_placeholder() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "999"},
                            "messages": [
                                {
                                    "id": "wamid.media",
                                    "from": "18005550199",
                                    "type": "image",
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    msgs = extract_inbound_messages(payload)
    assert len(msgs) == 1
    assert msgs[0].text == "[image]"
    assert msgs[0].message_type == "image"
    assert msgs[0].text_like is False
    assert msgs[0].media_metadata["type"] == "image"


def test_extract_inbound_messages_interactive_button_is_text_like() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "999"},
                            "messages": [
                                {
                                    "id": "wamid.button",
                                    "from": "18005550199",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {"id": "yes", "title": "Yes please"},
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    msgs = extract_inbound_messages(payload)
    assert len(msgs) == 1
    assert msgs[0].text == "[button] Yes please"
    assert msgs[0].message_type == "interactive"
    assert msgs[0].text_like is True


def test_extract_inbound_messages_skips_incomplete_rows() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {"from": "1"},  # missing id
                                {"id": "ok", "from": "2", "type": "text", "text": {"body": "x"}},
                            ],
                        }
                    }
                ]
            }
        ]
    }
    msgs = extract_inbound_messages(payload)
    assert len(msgs) == 1
    assert msgs[0].meta_msg_id == "ok"


def test_extract_inbound_messages_empty_payload() -> None:
    assert extract_inbound_messages({}) == []
    assert extract_inbound_messages({"entry": []}) == []
