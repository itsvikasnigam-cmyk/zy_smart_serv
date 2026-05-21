"""Smoke-test POST /ai/respond on local ai_engine (8083).

Usage:
  cd ...\\empty-window; . .\\dev-env.ps1
  python backend/tools/test_ai_respond_local.py
"""

from __future__ import annotations

import os
import sys

import httpx

URL = os.environ.get("AI_ENGINE_URL", "http://127.0.0.1:8083").rstrip("/") + "/ai/respond"


def main() -> int:
    # Must match AIRequest in backend/apps/ai_engine/main.py (same shape as batch_processor).
    body = {
        "client_id": "00000000-0000-0000-0000-000000000001",
        "chat_id": "00000000-0000-0000-0000-000000000002",
        "batch_id": "00000000-0000-0000-0000-000000000099",
        "customer_phone": "919876543210",
        "batch_text": "Namaste, kya aapke paas blue shirts hain?",
    }
    try:
        health = httpx.get(URL.replace("/ai/respond", "/health"), timeout=5.0).json()
        g2 = health.get("gate2") or {}
        if g2 and not g2.get("llm_fallback_configured"):
            print("WARN: 8083 reports llm_fallback_configured=False")
            print("  gate2:", g2)
            print("  Restart 8083 after: . .\\dev-env.ps1 (and confirm Ollama on :11435)")
    except httpx.ConnectError:
        print("ERROR: cannot reach 8083 - start:")
        print("  cd ...\\empty-window; . .\\dev-env.ps1")
        print("  python -m uvicorn backend.apps.ai_engine.main:app --host 127.0.0.1 --port 8083")
        return 1

    try:
        r = httpx.post(URL, json=body, timeout=120.0)
    except httpx.ConnectError:
        print("ERROR: cannot reach", URL)
        return 1
    print("HTTP", r.status_code)
    print(r.text[:2000])
    if r.status_code != 200:
        return 1
    data = r.json()
    intent = data.get("intent")
    print("action:", data.get("action"), "intent:", intent)
    if intent == "llm_assist":
        print("OK: LLM fallback path was used (Gate 2).")
    else:
        print("NOTE: deterministic reply. Run: python backend\\tools\\probe_gate2_llm.py")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
