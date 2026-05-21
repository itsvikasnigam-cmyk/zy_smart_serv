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
import time
from typing import Any, Literal

from fastapi import FastAPI, Header
from pydantic import BaseModel, ConfigDict, Field

from backend.apps.ai_engine.helpers.llm_pipeline import (
    llm_fallback_configured,
    maybe_enhance_reply_with_llm,
)
from backend.apps.ai_engine.helpers.respond_logic import (
    AIRespondDecision,
    NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED,
    decide_response,
    decision_to_response_dict,
)
from backend.apps.ai_engine.helpers.runtime_config import load_ai_engine_ops_bundle
from backend.shared.catalog_lookup import (
    fetch_catalog_items_engine,
    try_catalog_decision_for_ai,
)
from backend.shared.config import settings
from backend.shared.db import engine
from backend.shared.gpu_sentinel import get_gpu_sentinel_state
from backend.shared.release_manager import get_promoted_build_id, load_canary_policy_engine
from backend.shared.observability import new_trace_id, record_trace_safe

logger = logging.getLogger(__name__)

app = FastAPI(title="ZY Smart Serv - AI Engine", version="0.3.1")


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
    ops = load_ai_engine_ops_bundle(engine)
    gpu = get_gpu_sentinel_state()
    canary = load_canary_policy_engine(engine)
    promoted_build: str | None = None
    try:
        with engine.connect() as conn:
            promoted_build = get_promoted_build_id(conn)
    except Exception:
        promoted_build = None
    return {
        "ok": True,
        "catalog_lookup": "top_item_fix",
        "gpu_sentinel": {
            "status": gpu.status,
            "source": gpu.source,
            "owner": gpu.owner,
        },
        "release": {
            "promoted_build_id": promoted_build,
            "canary_enabled": canary.enabled,
            "canary_percent": canary.percent,
            "canary_active_build_id": canary.active_build_id,
        },
        "gate2": {
            "fallback_enabled": ops.fallback_enabled,
            "llm_fallback_configured": llm_fallback_configured(settings, ops),
            "ai_llm_base_url": settings.ai_llm_base_url,
            "ai_llm_primary_model": settings.ai_llm_primary_model,
        },
    }


@app.post("/ai/respond", response_model=AIResponse)
def respond(
    req: AIRequest,
    x_trace_id: str | None = Header(default=None, alias="X-Trace-Id"),
) -> AIResponse:
    trace_id = (x_trace_id or "").strip() or new_trace_id()
    t0 = time.perf_counter()
    try:
        return _respond_impl(req, trace_id=trace_id, t0=t0)
    except Exception:
        logger.exception("POST /ai/respond failed")
        return AIResponse(
            action="HANDOFF",
            reply_text=None,
            intent="internal_error",
            routing_intent="handoff",
            confidence=0.0,
            language="auto",
            handoff_reason="ai_internal_error",
            missing_fields=[],
            risk_reason=None,
        )


def _respond_impl(req: AIRequest, *, trace_id: str, t0: float) -> AIResponse:
    ops = load_ai_engine_ops_bundle(engine)
    owner_reply = ops.needs_owner_data_reply_override or NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED
    try:
        catalog_items = fetch_catalog_items_engine(engine, req.client_id)
    except Exception:
        logger.exception("catalog fetch failed; continuing without catalog rows")
        catalog_items = []
    catalog_payload = try_catalog_decision_for_ai(
        req.batch_text,
        catalog_items,
        needs_owner_customer_reply=owner_reply,
    )
    if catalog_payload is not None:
        decision = AIRespondDecision(
            action=catalog_payload["action"],
            reply_text=catalog_payload.get("reply_text"),
            intent=catalog_payload["intent"],
            routing_intent=catalog_payload["routing_intent"],
            confidence=catalog_payload["confidence"],
            language=catalog_payload["language"],
            handoff_reason=catalog_payload.get("handoff_reason"),
            missing_fields=catalog_payload.get("missing_fields") or [],
            risk_reason=catalog_payload.get("risk_reason"),
        )
    else:
        decision = decide_response(
            req.batch_text,
            urgent_bypass_substrings=ops.urgent_bypass_substrings,
            needs_owner_customer_reply=owner_reply,
        )
    misfire_ctx = {
        "_engine": engine,
        "trace_id": trace_id,
        "client_id": req.client_id,
        "chat_id": req.chat_id,
        "batch_text_preview": req.batch_text[:500],
    }
    decision = maybe_enhance_reply_with_llm(
        decision,
        req.batch_text,
        settings=settings,
        ops=ops,
        misfire_context=misfire_ctx,
    )
    payload = decision_to_response_dict(decision)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    record_trace_safe(
        engine,
        trace_id=trace_id,
        service="ai_engine",
        route="/ai/respond",
        latency_ms=latency_ms,
        status="ok",
        client_id=req.client_id,
        chat_id=req.chat_id,
        meta={"intent": payload.get("intent"), "action": payload.get("action")},
    )
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

