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
) -> AIRespondDecision:
    """
    Optional generative pass for the default ``general_ack`` path only.

    Requires **both** a non-empty ``settings.ai_llm_api_key`` and ``ops.fallback_enabled``.
    On any failure or failed quality gate, returns the original *deterministic* decision unchanged
    (still ``REPLY``) so ``batch_processor`` behavior stays predictable.
    """
    if not is_llm_eligible_decision(decision):
        return decision
    if not (settings.ai_llm_api_key or "").strip():
        return decision
    if not ops.fallback_enabled:
        return decision

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
            api_key=settings.ai_llm_api_key,
            model=settings.ai_llm_primary_model,
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
            max_tokens=ops.fallback_max_primary_tokens,
            temperature=0.35,
        )
    except Exception:
        logger.exception("Primary LLM call failed; using deterministic reply")
        return decision

    if not heuristic_reply_ok(draft, customer_text=batch_text):
        logger.info("Primary LLM reply failed local quality gate; using deterministic reply")
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
                api_key=settings.ai_llm_api_key,
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
                return decision
        except Exception:
            logger.exception("Judge LLM failed; using deterministic reply")
            return decision

    return replace(
        decision,
        reply_text=draft.strip(),
        intent="llm_assist",
        confidence=min(0.95, max(confidence, 0.72)),
    )
