"""Tests for blueprint remainder slice (no Postgres unless noted)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.apps.ai_engine.helpers.context_loader import (
    AIRequestContext,
    format_context_block,
    load_ai_request_context,
)
from backend.apps.ai_engine.helpers.runtime_config import default_ai_engine_ops_bundle
from backend.shared.path_layout import zy_base_dir


def test_format_context_block_includes_business_and_messages() -> None:
    ctx = AIRequestContext(
        recent_messages=["Customer: hi", "Business: hello"],
        persona_snippet="Business category: retail",
        business_name="Acme",
    )
    block = format_context_block(ctx)
    assert "Acme" in block
    assert "retail" in block
    assert "Customer: hi" in block


def test_load_ai_request_context_fail_open() -> None:
    bad = MagicMock()
    bad.connect.side_effect = RuntimeError("no db")
    ctx = load_ai_request_context(bad, client_id="c", chat_id="ch")
    assert ctx.recent_messages == []


def test_default_ops_bundle_has_llm_daily_cap() -> None:
    b = default_ai_engine_ops_bundle()
    assert b.fallback_max_calls_per_client_per_day == 200


def test_zy_base_dir_creates_dir(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZY_BASE_DIR", str(tmp_path / "zy"))
    p = zy_base_dir()
    assert p.is_dir()
