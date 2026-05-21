"""Print Gate 2 (Ollama) env + DB flags.

Usage:
  cd ...\\empty-window; . .\\dev-env.ps1
  python backend/tools/show_gate2_config.py
"""

from __future__ import annotations

import os

from backend.apps.ai_engine.helpers.llm_pipeline import is_local_llm_base_url, llm_fallback_configured
from backend.apps.ai_engine.helpers.runtime_config import load_ai_engine_ops_bundle
from backend.shared.config import settings
from backend.shared.db import engine


def main() -> int:
    ops = load_ai_engine_ops_bundle(engine)
    print("=== Gate 2 (local LLM) ===")
    print(f"AI_LLM_BASE_URL (env): {settings.ai_llm_base_url}")
    print(f"AI_LLM_API_KEY set: {bool((settings.ai_llm_api_key or '').strip())}")
    print(f"AI_LLM_PRIMARY_MODEL: {settings.ai_llm_primary_model}")
    print(f"local base URL: {is_local_llm_base_url(settings.ai_llm_base_url)}")
    print(f"ops ai.fallback.enabled: {ops.fallback_enabled}")
    print(f"ops ai.fallback.use_judge: {ops.fallback_use_judge}")
    print(f"llm_fallback_configured: {llm_fallback_configured(settings, ops)}")
    print(f"AI_ENGINE_URL (worker): {os.environ.get('AI_ENGINE_URL', 'http://127.0.0.1:8083')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
