"""Regression: WA gateway must never invoke the AI engine from the webhook path (M2 / blueprint)."""

from __future__ import annotations

import pathlib


def test_wa_gateway_main_source_has_no_ai_http_calls() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    main_py = root / "backend" / "apps" / "wa_gateway" / "main.py"
    text = main_py.read_text(encoding="utf-8")
    lower = text.lower()
    assert "httpx" not in lower
    assert "aiohttp" not in lower
    assert "/ai/respond" not in text
    assert "ai_engine_url" not in lower
    assert "openai" not in lower
