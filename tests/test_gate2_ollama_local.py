"""Gate 2 — local Ollama URL detection."""

from __future__ import annotations

from backend.apps.ai_engine.helpers.llm_pipeline import (
    effective_llm_api_key,
    is_local_llm_base_url,
    llm_fallback_configured,
)
from backend.apps.ai_engine.helpers.runtime_config import AIEngineOpsBundle
from backend.shared.config import Settings


def test_local_ollama_base_url() -> None:
    assert is_local_llm_base_url("http://127.0.0.1:11434/v1")
    assert not is_local_llm_base_url("https://api.openai.com/v1")


def test_effective_api_key_for_ollama() -> None:
    assert effective_llm_api_key("", "http://127.0.0.1:11434/v1") == "ollama"


def test_llm_fallback_configured_local_without_secret() -> None:
    s = Settings(
        ai_llm_base_url="http://127.0.0.1:11434/v1",
        ai_llm_api_key="",
    )
    ops = AIEngineOpsBundle(
        urgent_bypass_substrings=[],
        needs_owner_data_reply_override=None,
        fallback_enabled=True,
        fallback_use_judge=False,
        fallback_quality_threshold=0.65,
        fallback_max_primary_tokens=512,
        fallback_max_judge_tokens=256,
    )
    assert llm_fallback_configured(s, ops)
