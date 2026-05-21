from __future__ import annotations

import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from backend.apps.ai_engine.helpers.llm_client import openai_chat_completion, parse_judge_json
from backend.apps.ai_engine.helpers.quality_gate import heuristic_reply_ok
from backend.apps.ai_engine.helpers.respond_logic import AIRespondDecision, is_llm_eligible_decision

if TYPE_CHECKING:
    from backend.apps.ai_engine.helpers.runtime_config import AIEngineOpsBundle
    from backend.shared.config import Settings

logger = logging.getLogger(__name__)

# Ollama and other local OpenAI-compatible servers (Gate 2 / Option C phase 3).
_LOCAL_LLM_HOST_MARKERS = ("127.0.0.1", "localhost", ":11434", ":11435")


def is_local_llm_base_url(base_url: str) -> bool:
    u = (base_url or "").strip().lower()
    return any(m in u for m in _LOCAL_LLM_HOST_MARKERS)


def effective_llm_api_key(api_key: str, base_url: str) -> str:
    """Ollama often needs no real secret; use a placeholder bearer when local."""
    key = (api_key or "").strip()
    if key:
        return key
    if is_local_llm_base_url(base_url):
        return "ollama"
    return ""


def llm_fallback_configured(settings: "Settings", ops: "AIEngineOpsBundle") -> bool:
    if not ops.fallback_enabled:
        return False
    return bool(effective_llm_api_key(settings.ai_llm_api_key, settings.ai_llm_base_url))


def _log_misfire(ctx: dict[str, str] | None, reason: str, detail: dict) -> None:
    if not ctx or not ctx.get("_engine"):
        return
    from backend.shared.observability import record_misfire_safe

    record_misfire_safe(
        ctx["_engine"],
        source="ai_engine",
        reason=reason,
        trace_id=ctx.get("trace_id"),
        client_id=ctx.get("client_id"),
        chat_id=ctx.get("chat_id"),
        batch_text_preview=ctx.get("batch_text_preview"),
        detail=detail,
    )


def _language_instruction(language: str) -> str:
    if language == "hinglish":
        return (
            "The customer writes in Hinglish (Hindi + English mixed). Reply in the same natural mix: "
            "short, polite, clear; avoid overly formal Sanskritized Hindi unless they used it."
        )
    if language == "hi":
        return "The customer writes in Hindi (Devanagari). Reply in Hindi, short and polite."
    if language == "en":
        return "The customer writes in English. Reply in English, short and polite."
    return "Match the customer's language (English or Hindi / mixed) in a short, polite reply."


def maybe_enhance_reply_with_llm(
    decision: AIRespondDecision,
    batch_text: str,
    *,
    settings: "Settings",
    ops: "AIEngineOpsBundle",
    misfire_context: dict[str, str] | None = None,
) -> AIRespondDecision:
    """
    Optional generative pass for the default ``general_ack`` path only.

    Requires ``ops.fallback_enabled`` and either ``AI_LLM_API_KEY`` or a local base URL (Ollama on :11434).
    On any failure or failed quality gate, returns the original *deterministic* decision unchanged
    (still ``REPLY``) so ``batch_processor`` behavior stays predictable.
    """
    if not is_llm_eligible_decision(decision):
        logger.debug("LLM skip: not eligible intent=%s", decision.intent)
        return decision
    if not llm_fallback_configured(settings, ops):
        logger.info(
            "LLM skip: fallback not configured (enabled=%s base_url=%s)",
            ops.fallback_enabled,
            settings.ai_llm_base_url,
        )
        return decision

    api_key = effective_llm_api_key(settings.ai_llm_api_key, settings.ai_llm_base_url)
    lang = decision.language
    sys = (
        "You are a concise WhatsApp assistant for a small business. "
        + _language_instruction(lang)
        + " Max ~600 characters. Plain text only — no JSON, no markdown fences, no emojis unless the customer used them."
    )
    user = f"Customer message:\n{batch_text.strip()}"

    try:
        draft = openai_chat_completion(
            base_url=settings.ai_llm_base_url,
            api_key=api_key,
            model=settings.ai_llm_primary_model,
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
            max_tokens=ops.fallback_max_primary_tokens,
            temperature=0.35,
            timeout_seconds=120.0 if is_local_llm_base_url(settings.ai_llm_base_url) else 45.0,
        )
    except Exception as e:
        logger.warning("Primary LLM call failed (%s); using deterministic reply", e)
        _log_misfire(misfire_context, "llm_primary_failed", {"error": str(e)[:500]})
        return decision

    if not heuristic_reply_ok(draft, customer_text=batch_text):
        logger.warning(
            "Primary LLM reply failed quality gate (len=%s); draft=%r",
            len(draft or ""),
            (draft or "")[:120],
        )
        _log_misfire(
            misfire_context,
            "llm_quality_gate",
            {"draft_preview": (draft or "")[:200]},
        )
        return decision

    confidence = 0.78

    if ops.fallback_use_judge:
        jsys = (
            "You grade short WhatsApp business replies. Return JSON only with keys: "
            '`approve` (boolean), `score` (0-1 float), `notes` (short string). '
            "Approve only if the reply is helpful, safe, on-topic, and not echoing the question alone."
        )
        juser = f"Customer:\n{batch_text.strip()}\n\nProposed reply:\n{draft}"
        try:
            raw_j = openai_chat_completion(
                base_url=settings.ai_llm_base_url,
                api_key=api_key,
                model=settings.ai_llm_judge_model,
                messages=[{"role": "system", "content": jsys}, {"role": "user", "content": juser}],
                max_tokens=ops.fallback_max_judge_tokens,
                temperature=0.0,
            )
            approve, score = parse_judge_json(raw_j)
            confidence = max(confidence, score)
            if not approve or score < ops.fallback_quality_threshold:
                logger.info(
                    "Judge rejected LLM reply (approve=%s score=%s threshold=%s); using deterministic reply",
                    approve,
                    score,
                    ops.fallback_quality_threshold,
                )
                _log_misfire(misfire_context, "llm_judge_rejected", {"score": score, "approve": approve})
                return decision
        except Exception as e:
            logger.exception("Judge LLM failed; using deterministic reply")
            _log_misfire(misfire_context, "llm_judge_failed", {"error": str(e)[:500]})
            return decision

    return replace(
        decision,
        reply_text=draft.strip(),
        intent="llm_assist",
        confidence=min(0.95, max(confidence, 0.72)),
    )
