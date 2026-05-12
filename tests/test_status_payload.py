from __future__ import annotations

from backend.apps.wa_gateway.status_payload import extract_status_events


def test_extract_status_events_maps_status_strings() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {"id": "wamid.1", "status": "sent"},
                                {"id": "wamid.2", "status": "delivered"},
                                {"id": "wamid.3", "status": "read"},
                                {"id": "wamid.4", "status": "failed"},
                            ],
                        }
                    }
                ]
            }
        ]
    }
    events = extract_status_events(payload)
    types = {e.meta_message_id: e.event_type for e in events}
    assert types["wamid.1"] == "SENT"
    assert types["wamid.2"] == "DELIVERED"
    assert types["wamid.3"] == "READ"
    assert types["wamid.4"] == "FAILED"


def test_extract_status_events_ignores_unknown_status() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {"id": "wamid.x", "status": "queued"},
                                {"id": "wamid.y", "status": "DELIVERED"},
                            ],
                        }
                    }
                ]
            }
        ]
    }
    events = extract_status_events(payload)
    assert len(events) == 1
    assert events[0].meta_message_id == "wamid.y"
    assert events[0].event_type == "DELIVERED"


def test_extract_status_events_skips_missing_id() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {"status": "sent"},
                            ],
                        }
                    }
                ]
            }
        ]
    }
    assert extract_status_events(payload) == []


def test_extract_status_events_empty() -> None:
    assert extract_status_events({}) == []
