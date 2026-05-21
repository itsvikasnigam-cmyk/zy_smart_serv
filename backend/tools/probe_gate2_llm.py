"""Diagnose Gate 2: env, DB flags, direct Ollama call, and /ai/respond.

Usage:
  cd ...\\empty-window; . .\\dev-env.ps1
  python backend/tools/probe_gate2_llm.py
"""

from __future__ import annotations

import json
import sys

import httpx

from backend.apps.ai_engine.helpers.llm_client import openai_chat_completion
from backend.apps.ai_engine.helpers.llm_pipeline import effective_llm_api_key, llm_fallback_configured
from backend.apps.ai_engine.helpers.runtime_config import load_ai_engine_ops_bundle
from backend.shared.config import settings
from backend.shared.db import engine

AI_URL = "http://127.0.0.1:8083"


def main() -> int:
    print("=== Gate 2 probe ===")
    print(f"AI_LLM_BASE_URL: {settings.ai_llm_base_url}")
    print(f"AI_LLM_PRIMARY_MODEL: {settings.ai_llm_primary_model}")
    print(f"AI_LLM_API_KEY set: {bool((settings.ai_llm_api_key or '').strip())}")

    with engine.connect() as conn:
        ops = load_ai_engine_ops_bundle(engine)
    print(f"ops ai.fallback.enabled: {ops.fallback_enabled}")
    print(f"llm_fallback_configured: {llm_fallback_configured(settings, ops)}")

    try:
        h = httpx.get(f"{AI_URL}/health", timeout=5.0).json()
        print(f"8083 /health gate2: {json.dumps(h.get('gate2', h), indent=2)}")
    except httpx.ConnectError:
        print("ERROR: ai_engine not on 8083 - start with dev-env.ps1 then uvicorn")
        return 1

    key = effective_llm_api_key(settings.ai_llm_api_key, settings.ai_llm_base_url)
    print("\n--- Direct Ollama chat/completions ---")
    try:
        reply = openai_chat_completion(
            base_url=settings.ai_llm_base_url,
            api_key=key,
            model=settings.ai_llm_primary_model,
            messages=[
                {"role": "user", "content": "Say hello in one short sentence."},
            ],
            max_tokens=64,
            timeout_seconds=120.0,
        )
        print("OK:", reply[:300])
    except Exception as e:
        print("FAIL:", e)
        print("Try: ollama list  (use exact model name from NAME column)")
        print("Set AI_LLM_PRIMARY_MODEL=llama3.2:latest in backend\\.env, restart 8083.")
        return 1

    print("\n--- POST /ai/respond ---")
    body = {
        "client_id": "00000000-0000-0000-0000-000000000001",
        "chat_id": "00000000-0000-0000-0000-000000000002",
        "batch_id": "00000000-0000-0000-0000-000000000099",
        "customer_phone": "919876543210",
        "batch_text": "Namaste, kya aapke paas blue shirts hain?",
    }
    r = httpx.post(f"{AI_URL}/ai/respond", json=body, timeout=120.0)
    print("HTTP", r.status_code)
    data = r.json()
    print("intent:", data.get("intent"), "reply:", (data.get("reply_text") or "")[:200])
    if data.get("intent") == "llm_assist":
        print("OK: LLM path used.")
        return 0
    print("Still deterministic - check 8083 terminal logs for 'LLM skip' or 'Primary LLM call failed'")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
