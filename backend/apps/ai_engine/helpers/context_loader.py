from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AIRequestContext:
    """Server-side context for LLM prompts (does not change ``AIRequest`` JSON contract)."""

    recent_messages: list[str]
    persona_snippet: str | None
    business_name: str | None


def load_ai_request_context(
    engine: Any,
    *,
    client_id: str,
    chat_id: str,
    max_messages: int = 12,
) -> AIRequestContext:
    """
    Load capped recent inbound/outbound text and optional persona for the LLM path.

    Failures return empty context so deterministic routing still works.
    """
    try:
        with engine.connect() as conn:
            msg_rows = conn.execute(
                text(
                    """
                    SELECT direction, COALESCE(text, '')
                    FROM inbox_messages
                    WHERE chat_id = CAST(:cid AS uuid)
                    ORDER BY timestamp DESC
                    LIMIT :lim
                    """
                ),
                {"cid": chat_id, "lim": max(1, min(max_messages, 50))},
            ).all()
            client_row = conn.execute(
                text(
                    """
                    SELECT business_name, category
                    FROM api_clients
                    WHERE id = CAST(:client AS uuid)
                    LIMIT 1
                    """
                ),
                {"client": client_id},
            ).fetchone()
    except Exception:
        logger.exception("load_ai_request_context failed client=%s chat=%s", client_id, chat_id)
        return AIRequestContext(recent_messages=[], persona_snippet=None, business_name=None)

    lines: list[str] = []
    for direction, body in reversed(msg_rows):
        tag = "Customer" if direction == "in" else "Business"
        t = (body or "").strip()
        if t:
            lines.append(f"{tag}: {t[:500]}")

    business_name: str | None = None
    persona_snippet: str | None = None
    if client_row:
        business_name = (client_row[0] or "").strip() or None
        category = (client_row[1] or "").strip() if client_row[1] else ""
        if category:
            persona_snippet = f"Business category: {category}"[:800]

    return AIRequestContext(
        recent_messages=lines,
        persona_snippet=persona_snippet,
        business_name=business_name,
    )


def format_context_block(ctx: AIRequestContext) -> str:
    parts: list[str] = []
    if ctx.business_name:
        parts.append(f"Business name: {ctx.business_name}")
    if ctx.persona_snippet:
        parts.append(f"Business tone/instructions: {ctx.persona_snippet}")
    if ctx.recent_messages:
        parts.append("Recent conversation:\n" + "\n".join(ctx.recent_messages[-12:]))
    return "\n\n".join(parts)
