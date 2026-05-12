from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Action = Literal["REPLY", "HANDOFF", "NEEDS_OWNER_DATA"]

# Canonical customer-visible line when the model cannot answer without owner-only data.
NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED = (
    "Thanks for your message. I need to confirm a few details with the business owner "
    "before I can answer that accurately. Someone will follow up shortly."
)

URGENT_DEFAULT_REPLY = (
    "Thanks — we've received your message and flagged it as time-sensitive. "
    "We'll prioritize this and follow up shortly."
)

GREETING_EMPTY = "Hi! How can I help you today?"

# Substrings (lowercased batch text); order of classification is decided in decide_response.
_HANDOFF_MARKERS = (
    "speak to a human",
    "speak to human",
    "talk to a human",
    "talk to human",
    "real person",
    "human agent",
    "connect me to an agent",
    "transfer me to",
    "talk to someone",
    "customer support human",
    "want a human",
)

_OWNER_DATA_MARKERS = (
    "refund",
    "chargeback",
    "invoice",
    "discount code",
    "custom quote",
    "legal action",
    "lawyer",
    "complaint about your staff",
    "who owns this business",
)


def detect_language(batch_text: str) -> str:
    """Return BCP-47 style tag: 'hi' | 'en' | 'auto' (unknown / empty)."""
    if not batch_text or not batch_text.strip():
        return "auto"
    for ch in batch_text:
        if "\u0900" <= ch <= "\u097f":
            return "hi"
    return "en"


def _lower_contains(haystack: str, needle: str) -> bool:
    return needle in haystack


@dataclass(frozen=True)
class AIRespondDecision:
    action: Action
    reply_text: str | None
    intent: str
    routing_intent: str
    confidence: float
    language: str
    handoff_reason: str | None
    missing_fields: list[str]
    risk_reason: str | None


def decide_response(
    batch_text: str,
    *,
    urgent_bypass_substrings: list[str],
    needs_owner_customer_reply: str,
) -> AIRespondDecision:
    """
    Deterministic routing for the batch_processor contract (no external LLM).

    Precedence: empty greeting → explicit human request (HANDOFF) → urgent bypass (REPLY) →
    owner-only topics (NEEDS_OWNER_DATA) → default REPLY.
    """
    text = batch_text.strip()
    language = detect_language(text)

    if not text:
        return AIRespondDecision(
            action="REPLY",
            reply_text=GREETING_EMPTY,
            intent="greeting",
            routing_intent="general",
            confidence=0.9,
            language=language,
            handoff_reason=None,
            missing_fields=[],
            risk_reason=None,
        )

    lowered = text.lower()

    for marker in _HANDOFF_MARKERS:
        if _lower_contains(lowered, marker):
            return AIRespondDecision(
                action="HANDOFF",
                reply_text=None,
                intent="human_request",
                routing_intent="human_request",
                confidence=0.85,
                language=language,
                handoff_reason="customer_requested_human",
                missing_fields=[],
                risk_reason=None,
            )

    for urgent in urgent_bypass_substrings:
        if urgent and urgent.lower() in lowered:
            return AIRespondDecision(
                action="REPLY",
                reply_text=URGENT_DEFAULT_REPLY,
                intent="urgent",
                routing_intent="urgent",
                confidence=0.88,
                language=language,
                handoff_reason=None,
                missing_fields=[],
                risk_reason=None,
            )

    for marker in _OWNER_DATA_MARKERS:
        if _lower_contains(lowered, marker):
            return AIRespondDecision(
                action="NEEDS_OWNER_DATA",
                reply_text=needs_owner_customer_reply,
                intent="owner_only_information",
                routing_intent="owner_data",
                confidence=0.8,
                language=language,
                handoff_reason=None,
                missing_fields=["owner_confirmation"],
                risk_reason=None,
            )

    # Default helpful echo (stable shape for batch_processor)
    snippet = text if len(text) <= 280 else text[:277] + "..."
    return AIRespondDecision(
        action="REPLY",
        reply_text=f"Thanks — I've noted that: {snippet}",
        intent="general_ack",
        routing_intent="general",
        confidence=0.72,
        language=language,
        handoff_reason=None,
        missing_fields=[],
        risk_reason=None,
    )


def decision_to_response_dict(d: AIRespondDecision) -> dict[str, Any]:
    """Serialize to the JSON shape batch_processor expects from POST /ai/respond."""
    return {
        "action": d.action,
        "reply_text": d.reply_text,
        "intent": d.intent,
        "routing_intent": d.routing_intent,
        "confidence": d.confidence,
        "language": d.language,
        "handoff_reason": d.handoff_reason,
        "missing_fields": d.missing_fields,
        "risk_reason": d.risk_reason,
    }
