"""OpenAPI contract snapshot for POST /ai/respond (Chat N)."""

from __future__ import annotations

from backend.apps.ai_engine.main import app


def test_ai_respond_openapi_request_response_fields() -> None:
    schema = app.openapi()
    post = schema["paths"]["/ai/respond"]["post"]
    req_name = post["requestBody"]["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]
    req_schema = schema["components"]["schemas"][req_name]
    assert set(req_schema["properties"]) == {
        "client_id",
        "chat_id",
        "batch_id",
        "customer_phone",
        "batch_text",
    }
    resp_name = post["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]
    resp_schema = schema["components"]["schemas"][resp_name]
    resp_props = set(resp_schema["properties"])
    assert "action" in resp_props
    assert "routing_intent" in resp_props
    assert "language" in resp_props
    assert set(resp_schema["properties"]["action"]["enum"]) == {
        "REPLY",
        "HANDOFF",
        "NEEDS_OWNER_DATA",
    }
