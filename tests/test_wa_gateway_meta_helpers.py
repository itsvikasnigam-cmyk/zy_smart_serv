from __future__ import annotations

from backend.apps.wa_gateway.meta_payload import (
    coerce_string_list_json,
    inbound_matches_urgent_substrings,
)
from backend.apps.wa_gateway.status_payload import extract_meta_errors


def test_inbound_matches_urgent_substrings_case_insensitive() -> None:
    assert inbound_matches_urgent_substrings("Please HELP urgently", ["urgent", "help"])
    assert not inbound_matches_urgent_substrings("hello", ["urgent"])


def test_coerce_string_list_json() -> None:
    assert coerce_string_list_json(["a", "", "b"]) == ["a", "b"]
    assert coerce_string_list_json('["x","y"]') == ["x", "y"]


def test_extract_meta_errors_minimal_payload() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "errors": [
                                {"code": 131047, "title": "Re-engagement message"},
                            ]
                        }
                    }
                ]
            }
        ]
    }
    errs = extract_meta_errors(payload)
    assert len(errs) == 1
    assert errs[0].get("code") == 131047
