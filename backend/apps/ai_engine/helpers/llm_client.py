from __future__ import annotations

import json
from typing import Any

import httpx


def openai_chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float = 0.35,
    timeout_seconds: float = 45.0,
) -> str:
    """
    Minimal OpenAI-compatible ``POST /chat/completions`` client (no streaming).

    Works with OpenAI and many proxies that expose the same JSON shape.
    """
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    with httpx.Client(timeout=timeout_seconds) as client:
        r = client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("LLM response missing choices")
    msg = (choices[0] or {}).get("message") or {}
    content = msg.get("content")
    if not isinstance(content, str):
        raise ValueError("LLM response missing string content")
    return content.strip()


def parse_judge_json(raw: str) -> tuple[bool, float]:
    """
    Parse judge output into (approved, score).

    Expects JSON like ``{"approve": true, "score": 0.82}``; tolerates extra text by
    scanning for the first ``{`` .. last ``}``.
    """
    s = raw.strip()
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return False, 0.0
    try:
        obj = json.loads(s[start : end + 1])
    except json.JSONDecodeError:
        return False, 0.0
    if not isinstance(obj, dict):
        return False, 0.0
    score = float(obj.get("score", 0.0))
    approve = bool(obj.get("approve", False))
    return approve, max(0.0, min(1.0, score))
