from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.apps.ai_engine.helpers.respond_logic import NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED
from backend.apps.ai_engine.main import AIResponse, app


def _minimal_payload(batch_text: str) -> dict:
    return {
        "client_id": "00000000-0000-0000-0000-000000000001",
        "chat_id": "00000000-0000-0000-0000-000000000002",
        "batch_id": "00000000-0000-0000-0000-000000000003",
        "customer_phone": "+15551234567",
        "batch_text": batch_text,
    }


@patch(
    "backend.apps.ai_engine.main.load_ai_runtime_strings",
    return_value=([], None),
)
def test_post_ai_respond_json_matches_batch_processor_contract(_mock: object) -> None:
    client = TestClient(app)
    r = client.post("/ai/respond", json=_minimal_payload("Hello"))
    assert r.status_code == 200
    body = r.json()
    parsed = AIResponse.model_validate(body)
    assert parsed.action == "REPLY"
    assert parsed.language == "en"


@patch(
    "backend.apps.ai_engine.main.load_ai_runtime_strings",
    return_value=([], None),
)
def test_post_ai_respond_needs_owner_data_shape(_mock: object) -> None:
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
    "backend.apps.ai_engine.main.load_ai_runtime_strings",
    return_value=([], None),
)
def test_post_ai_respond_detects_hindi(_mock: object) -> None:
    client = TestClient(app)
    r = client.post("/ai/respond", json=_minimal_payload("नमस्ते, कैसे हैं?"))
    assert r.status_code == 200
    assert AIResponse.model_validate(r.json()).language == "hi"


@patch(
    "backend.apps.ai_engine.main.load_ai_runtime_strings",
    return_value=(["priority"], None),
)
def test_post_ai_respond_urgent_bypass_from_config(_mock: object) -> None:
    client = TestClient(app)
    r = client.post("/ai/respond", json=_minimal_payload("priority support needed now"))
    assert r.status_code == 200
    body = r.json()
    parsed = AIResponse.model_validate(body)
    assert parsed.action == "REPLY"
    assert parsed.routing_intent == "urgent"
