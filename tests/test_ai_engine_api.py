from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.apps.ai_engine.helpers.runtime_config import default_ai_engine_ops_bundle
from backend.apps.ai_engine.helpers.respond_logic import NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED
from backend.apps.ai_engine.main import AIResponse, app


def _ops(**kwargs: object) -> object:
    return replace(default_ai_engine_ops_bundle(), **kwargs)


def _minimal_payload(batch_text: str) -> dict:
    return {
        "client_id": "00000000-0000-0000-0000-000000000001",
        "chat_id": "00000000-0000-0000-0000-000000000002",
        "batch_id": "00000000-0000-0000-0000-000000000003",
        "customer_phone": "+15551234567",
        "batch_text": batch_text,
    }


@patch(
    "backend.apps.ai_engine.main.load_ai_engine_ops_bundle",
    return_value=_ops(),
)
@patch("backend.apps.ai_engine.main.maybe_enhance_reply_with_llm", side_effect=lambda d, *a, **k: d)
def test_post_ai_respond_json_matches_batch_processor_contract(_m_llm: object, _mock: object) -> None:
    client = TestClient(app)
    r = client.post("/ai/respond", json=_minimal_payload("Hello"))
    assert r.status_code == 200
    body = r.json()
    parsed = AIResponse.model_validate(body)
    assert parsed.action == "REPLY"
    assert parsed.language == "en"


@patch(
    "backend.apps.ai_engine.main.load_ai_engine_ops_bundle",
    return_value=_ops(),
)
@patch("backend.apps.ai_engine.main.maybe_enhance_reply_with_llm", side_effect=lambda d, *a, **k: d)
def test_post_ai_respond_needs_owner_data_shape(_m_llm: object, _mock: object) -> None:
    client = TestClient(app)
    r = client.post("/ai/respond", json=_minimal_payload("Please send my invoice"))
    assert r.status_code == 200
    body = r.json()
    parsed = AIResponse.model_validate(body)
    assert parsed.action == "NEEDS_OWNER_DATA"
    assert parsed.routing_intent == "owner_data"
    assert parsed.reply_text == NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED
    assert parsed.language == "en"


@patch(
    "backend.apps.ai_engine.main.load_ai_engine_ops_bundle",
    return_value=_ops(),
)
@patch("backend.apps.ai_engine.main.maybe_enhance_reply_with_llm", side_effect=lambda d, *a, **k: d)
def test_post_ai_respond_detects_hindi(_m_llm: object, _mock: object) -> None:
    client = TestClient(app)
    r = client.post("/ai/respond", json=_minimal_payload("नमस्ते, कैसे हैं?"))
    assert r.status_code == 200
    assert AIResponse.model_validate(r.json()).language == "hi"


@patch(
    "backend.apps.ai_engine.main.load_ai_engine_ops_bundle",
    return_value=_ops(),
)
@patch("backend.apps.ai_engine.main.maybe_enhance_reply_with_llm", side_effect=lambda d, *a, **k: d)
def test_post_ai_respond_detects_hinglish(_m_llm: object, _mock: object) -> None:
    client = TestClient(app)
    r = client.post("/ai/respond", json=_minimal_payload("kya आप Sunday को deliver करते हो?"))
    assert r.status_code == 200
    assert AIResponse.model_validate(r.json()).language == "hinglish"


@patch(
    "backend.apps.ai_engine.main.load_ai_engine_ops_bundle",
    return_value=_ops(),
)
@patch("backend.apps.ai_engine.main.maybe_enhance_reply_with_llm", side_effect=lambda d, *a, **k: d)
def test_post_ai_respond_handoff_routing_intent(_m_llm: object, _mock: object) -> None:
    client = TestClient(app)
    r = client.post("/ai/respond", json=_minimal_payload("Please connect me to a real person"))
    assert r.status_code == 200
    parsed = AIResponse.model_validate(r.json())
    assert parsed.action == "HANDOFF"
    assert parsed.routing_intent == "human_request"
    assert parsed.reply_text is None
    assert parsed.handoff_reason == "customer_requested_human"


@patch(
    "backend.apps.ai_engine.main.load_ai_engine_ops_bundle",
    return_value=_ops(urgent_bypass_substrings=["priority"]),
)
@patch("backend.apps.ai_engine.main.maybe_enhance_reply_with_llm", side_effect=lambda d, *a, **k: d)
def test_post_ai_respond_urgent_bypass_from_config(_m_llm: object, _mock: object) -> None:
    client = TestClient(app)
    r = client.post("/ai/respond", json=_minimal_payload("priority support needed now"))
    assert r.status_code == 200
    body = r.json()
    parsed = AIResponse.model_validate(body)
    assert parsed.action == "REPLY"
    assert parsed.routing_intent == "urgent"
