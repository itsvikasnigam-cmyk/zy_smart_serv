from __future__ import annotations

"""AI Engine HTTP app.

Ops keys (``ops_runtime_config.value_json``), read at request time:

- ``ai.urgent_bypass_substrings``: JSON array of substrings; if any appear in ``batch_text``
  (case-insensitive), the response is REPLY with ``routing_intent`` ``urgent`` (unless a human
  handoff phrase matches first).
- ``ai.needs_owner_data_customer_reply``: optional JSON string overriding the fixed
  NEEDS_OWNER_DATA customer line.
"""

import logging
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from backend.apps.ai_engine.helpers.respond_logic import (
    NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED,
    decide_response,
    decision_to_response_dict,
)
from backend.apps.ai_engine.helpers.runtime_config import load_ai_runtime_strings
from backend.shared.db import engine

logger = logging.getLogger(__name__)

app = FastAPI(title="ZY Smart Serv - AI Engine", version="0.2.0")


class AIRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: str
    chat_id: str
    batch_id: str
    customer_phone: str
    batch_text: str = Field(default="", description="Concatenated customer messages")


class AIResponse(BaseModel):
    """
    Stable JSON contract for `batch_processor` (httpx r.json()).

    Fields and types should remain backward compatible when extending behavior.
    """

    model_config = ConfigDict(extra="forbid")

    action: Literal["REPLY", "HANDOFF", "NEEDS_OWNER_DATA"]
    reply_text: str | None = None
    intent: str = "unknown"
    routing_intent: str = "general"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    language: str = Field(default="auto", description="Detected or best-effort language tag (e.g. en, hi, auto)")
    handoff_reason: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    risk_reason: str | None = None


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True}


@app.post("/ai/respond", response_model=AIResponse)
def respond(req: AIRequest) -> AIResponse:
    urgent, owner_override = load_ai_runtime_strings(engine)
    owner_reply = owner_override or NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED
    decision = decide_response(
        req.batch_text,
        urgent_bypass_substrings=urgent,
        needs_owner_customer_reply=owner_reply,
    )
    payload = decision_to_response_dict(decision)
    try:
        return AIResponse.model_validate(payload)
    except Exception:
        logger.exception("AIResponse validation failed; falling back to HANDOFF")
        return AIResponse(
            action="HANDOFF",
            reply_text=None,
            intent="internal_error",
            routing_intent="handoff",
            confidence=0.0,
            language="auto",
            handoff_reason="ai_response_shape_error",
            missing_fields=[],
            risk_reason=None,
        )
