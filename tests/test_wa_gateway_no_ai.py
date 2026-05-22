"""Regression: WA gateway must never invoke the AI engine from the webhook path (M2 / blueprint)."""

from __future__ import annotations

import pathlib
import re


def test_wa_gateway_main_source_has_no_ai_http_calls() -> None:
    root = pathlib.Path(__file__).resolve().parents[1]
    main_py = root / "backend" / "apps" / "wa_gateway" / "main.py"
    text = main_py.read_text(encoding="utf-8")
    lower = text.lower()
    # Forbid real HTTP client usage / AI engine calls (docstrings may mention M1 paths).
    assert "import httpx" not in lower
    assert "from httpx" not in lower
    assert "import aiohttp" not in lower
    assert "from aiohttp" not in lower
    assert not re.search(r"httpx\.(get|post|put|patch|delete|request|client)", lower)
    assert not re.search(r"aiohttp\.client", lower)
    assert not re.search(r'["\']/ai/respond["\']', text)
    assert "ai_engine_url" not in lower
    assert "import openai" not in lower
    assert "from openai" not in lower
