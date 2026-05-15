from __future__ import annotations

"""AI Engine HTTP app.

``ops_runtime_config`` keys (``value_json``), read at request time:

- ``ai.urgent_bypass_substrings``: JSON array of substrings → **REPLY** / ``routing_intent`` ``urgent``.
- ``ai.needs_owner_data_customer_reply``: optional JSON string for **NEEDS_OWNER_DATA** customer line.
- ``ai.fallback.enabled``: JSON boolean — allow **external LLM** spend for the default general path
  (still requires ``AI_LLM_API_KEY`` in Settings / env).
- ``ai.fallback.use_judge``: JSON boolean — second **judge** model call + ``ai.fallback.quality_threshold``.
- ``ai.fallback.quality_threshold``: JSON number 0–1 (default 0.65).
- ``ai.fallback.max_primary_tokens`` / ``ai.fallback.max_judge_tokens``: JSON integers (capped in code).

**Contract:** ``POST /ai/respond`` request/response models are frozen for ``batch_processor`` (Chat **C**).
Any new *required* JSON keys need a Stem-approved change in ``batch_processor`` + this doc + ``HANDOFF.md``.
"""

import logging
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

from backend.apps.ai_engine.helpers.llm_pipeline import maybe_enhance_reply_with_llm
from backend.apps.ai_engine.helpers.respond_logic import (
    NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED,
    decide_response,
    decision_to_response_dict,
)
from backend.apps.ai_engine.helpers.runtime_config import load_ai_engine_ops_bundle
from backend.shared.config import settings
from backend.shared.db import engine

logger = logging.getLogger(__name__)

app = FastAPI(title="ZY Smart Serv - AI Engine", version="0.3.0")


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
    language: str = Field(
        default="auto",
        description="Detected or best-effort language tag (en, hi, hinglish, auto)",
    )
    handoff_reason: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    risk_reason: str | None = None


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True}


@app.post("/ai/respond", response_model=AIResponse)
def respond(req: AIRequest) -> AIResponse:
    ops = load_ai_engine_ops_bundle(engine)
    owner_reply = ops.needs_owner_data_reply_override or NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED
    decision = decide_response(
        req.batch_text,
        urgent_bypass_substrings=ops.urgent_bypass_substrings,
        needs_owner_customer_reply=owner_reply,
    )
    decision = maybe_enhance_reply_with_llm(decision, req.batch_text, settings=settings, ops=ops)
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
