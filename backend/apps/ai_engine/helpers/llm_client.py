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
    headers: dict[str, str] = {"Content-Type": "application/json"}
    key = (api_key or "").strip()
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }
    with httpx.Client(timeout=timeout_seconds) as client:
        r = client.post(url, headers=headers, json=body)
        if r.status_code >= 400:
            raise ValueError(f"LLM HTTP {r.status_code}: {r.text[:500]}")
        data = r.json()
    choices = data.get("choices") or []
    if not choices:
        raise ValueError(f"LLM response missing choices: {data!r}")
    msg = (choices[0] or {}).get("message") or {}
    content = msg.get("content")
    if not isinstance(content, str) or not content.strip():
        # Some Ollama builds put text in ``reasoning`` when ``content`` is empty.
        reasoning = msg.get("reasoning")
        if isinstance(reasoning, str) and reasoning.strip():
            content = reasoning
    if not isinstance(content, str) or not content.strip():
        raise ValueError(f"LLM response empty content: {data!r}")
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
