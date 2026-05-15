from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

from backend.apps.ai_engine.helpers.llm_pipeline import maybe_enhance_reply_with_llm
from backend.apps.ai_engine.helpers.respond_logic import decide_response
from backend.apps.ai_engine.helpers.runtime_config import AIEngineOpsBundle, default_ai_engine_ops_bundle
from backend.shared.config import Settings


def _decision_general(batch: str) -> object:
    return decide_response(
        batch,
        urgent_bypass_substrings=[],
        needs_owner_customer_reply="fixed owner msg",
    )


def test_llm_skipped_when_ops_disabled_even_with_api_key() -> None:
    d0 = _decision_general("What are your hours on Sunday?")
    settings = Settings(ai_llm_api_key="sk-test", ai_llm_base_url="https://api.openai.com/v1")
    ops = default_ai_engine_ops_bundle()  # fallback_enabled False
    d1 = maybe_enhance_reply_with_llm(d0, "What are your hours on Sunday?", settings=settings, ops=ops)
    assert d1 == d0


def test_llm_skipped_when_not_general_path() -> None:
    d0 = decide_response(
        "speak to human",
        urgent_bypass_substrings=[],
        needs_owner_customer_reply="x",
    )
    settings = Settings(ai_llm_api_key="sk-test")
    ops = replace(default_ai_engine_ops_bundle(), fallback_enabled=True)
    d1 = maybe_enhance_reply_with_llm(d0, "speak to human", settings=settings, ops=ops)
    assert d1.action == "HANDOFF"


@patch("backend.apps.ai_engine.helpers.llm_pipeline.openai_chat_completion")
def test_llm_replaces_reply_when_primary_ok(mock_cc: object) -> None:
    mock_cc.return_value = "We are open 10am–6pm on Sundays."
    d0 = _decision_general("Sunday hours?")
    settings = Settings(ai_llm_api_key="sk-test")
    ops = replace(default_ai_engine_ops_bundle(), fallback_enabled=True, fallback_use_judge=False)
    d1 = maybe_enhance_reply_with_llm(d0, "Sunday hours?", settings=settings, ops=ops)
    assert d1.reply_text == "We are open 10am–6pm on Sundays."
    assert d1.intent == "llm_assist"
    mock_cc.assert_called_once()


@patch("backend.apps.ai_engine.helpers.llm_pipeline.openai_chat_completion")
def test_llm_falls_back_when_judge_rejects(mock_cc: object) -> None:
    def _side_effect(**kwargs: object) -> str:
        msgs = kwargs.get("messages") or []
        sys = msgs[0]["content"] if msgs else ""
        if "grade" in sys.lower() or "judge" in sys.lower():
            return '{"approve": false, "score": 0.2}'
        return "bad reply"

    mock_cc.side_effect = _side_effect
    d0 = _decision_general("Sunday hours?")
    settings = Settings(ai_llm_api_key="sk-test")
    ops = replace(
        default_ai_engine_ops_bundle(),
        fallback_enabled=True,
        fallback_use_judge=True,
        fallback_quality_threshold=0.5,
    )
    d1 = maybe_enhance_reply_with_llm(d0, "Sunday hours?", settings=settings, ops=ops)
    assert d1 == d0
    assert mock_cc.call_count == 2


def test_ops_bundle_dataclass_for_tests() -> None:
    b = AIEngineOpsBundle(
        urgent_bypass_substrings=["a"],
        needs_owner_data_reply_override=None,
        fallback_enabled=True,
        fallback_use_judge=True,
        fallback_quality_threshold=0.5,
        fallback_max_primary_tokens=100,
        fallback_max_judge_tokens=50,
        fallback_max_calls_per_client_per_day=200,
    )
    assert b.fallback_max_primary_tokens == 100
