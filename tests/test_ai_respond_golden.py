from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.apps.ai_engine.helpers.respond_logic import NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED, decide_response
from backend.apps.ai_engine.main import AIResponse

_GOLDEN_DIR = Path(__file__).resolve().parent / "golden" / "ai_respond"


def _iter_deterministic_cases():
    for path in sorted(_GOLDEN_DIR.glob("deterministic_*.json")):
        yield path


@pytest.mark.parametrize("path", list(_iter_deterministic_cases()), ids=lambda p: p.name)
def test_golden_deterministic_routing(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    batch = data["batch_text"]
    urgent = data.get("urgent_bypass_substrings") or []
    exp = data["expected"]
    d = decide_response(
        batch,
        urgent_bypass_substrings=urgent,
        needs_owner_customer_reply=NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED,
    )
    assert d.action == exp["action"]
    assert d.intent == exp["intent"]
    assert d.routing_intent == exp["routing_intent"]
    assert d.language == exp["language"]
    if "handoff_reason" in exp:
        assert d.handoff_reason == exp["handoff_reason"]


def test_golden_contract_batch_processor_response_keys() -> None:
    """Golden file documents the exact JSON shape ``batch_processor`` reads via ``r.json()``."""
    path = _GOLDEN_DIR / "contract_batch_processor_response.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    body = data["response"]
    parsed = AIResponse.model_validate(body)
    assert parsed.action == "REPLY"
    assert parsed.reply_text == "Hello"
