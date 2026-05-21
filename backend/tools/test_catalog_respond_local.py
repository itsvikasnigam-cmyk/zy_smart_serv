"""Smoke-test catalog routing on local ai_engine (8083).

Usage:
  . .\\dev-env.ps1
  python backend/tools/test_catalog_respond_local.py
  python backend/tools/test_catalog_respond_local.py --text "What is the price of WIDGET-A?"
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx

DEFAULT_CLIENT = "17682c77-1524-4ebd-94e5-958e7f37ac60"
BASE = os.environ.get("AI_ENGINE_URL", "http://127.0.0.1:8083").rstrip("/")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--client-id", default=DEFAULT_CLIENT)
    p.add_argument("--text", default="What is the price of WIDGET-A?")
    args = p.parse_args()

    try:
        httpx.get(f"{BASE}/health", timeout=5.0)
    except httpx.ConnectError:
        print("ERROR: ai_engine not reachable on", BASE)
        print("Start: python -m uvicorn backend.apps.ai_engine.main:app --host 127.0.0.1 --port 8083")
        return 1

    body = {
        "client_id": args.client_id,
        "chat_id": "00000000-0000-0000-0000-000000000002",
        "batch_id": "00000000-0000-0000-0000-000000000099",
        "customer_phone": "919769825350",
        "batch_text": args.text,
    }
    r = httpx.post(f"{BASE}/ai/respond", json=body, timeout=30.0)
    print("HTTP", r.status_code)
    print(r.text[:1500])
    if r.status_code != 200:
        return 1
    data = r.json()
    intent = data.get("intent")
    action = data.get("action")
    reply = (data.get("reply_text") or "")[:200]
    print("action:", action, "intent:", intent)
    if intent == "catalog_fact" and action == "REPLY" and "499" in reply:
        print("OK: catalog deterministic reply.")
        return 0
    if intent == "catalog_unknown_product" and action == "NEEDS_OWNER_DATA":
        print("OK: unknown product -> NEEDS_OWNER_DATA.")
        return 0
    print("WARN: unexpected catalog routing; check migration + seed_client_catalog.py")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
