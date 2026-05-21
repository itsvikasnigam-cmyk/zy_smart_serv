"""Enable Gate 2: local Ollama LLM + ai.fallback.enabled in ops_runtime_config.

Usage:
  cd ...\\empty-window; . .\\dev-env.ps1
  python backend/tools/enable_gate2_ollama.py

Then add to backend\\.env (see printed lines), restart 8083 + batch_processor, send inbound test.
"""

from __future__ import annotations

import json
import sys

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    keys = {
        "ai.fallback.enabled": True,
        "ai.fallback.use_judge": False,
        "ai.fallback.quality_threshold": 0.65,
        "ai.fallback.max_primary_tokens": 512,
        "ai.fallback.max_judge_tokens": 256,
    }
    with engine.begin() as conn:
        for k, v in keys.items():
            conn.execute(
                text(
                    """
                    INSERT INTO ops_runtime_config (key, value_json)
                    VALUES (:k, CAST(:v AS jsonb))
                    ON CONFLICT (key) DO UPDATE SET value_json = EXCLUDED.value_json
                    """
                ),
                {"k": k, "v": json.dumps(v)},
            )

    print("OK: ai.fallback.enabled=true in database.")
    print("")
    print("Project-local Ollama (moves with ZY_BASE_DIR / D: drive):")
    print("  .\\scripts\\setup_ollama_local.ps1")
    print("  .\\scripts\\start_ollama_local.ps1    # keep window open")
    print("  .\\scripts\\pull_ollama_model_local.ps1")
    print("")
    print("backend\\.env should include (port 11435 = local copy, not system :11434):")
    print("  AI_LLM_BASE_URL=http://127.0.0.1:11435/v1")
    print("  AI_LLM_API_KEY=ollama")
    print("  AI_LLM_PRIMARY_MODEL=llama3.2")
    print("  AI_LLM_JUDGE_MODEL=llama3.2")
    print("")
    print("Then restart ai_engine on 8083 + batch_processor.")
    print("")
    print("Verify:")
    print("  python backend\\tools\\test_ai_respond_local.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
