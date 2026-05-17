"""Unit tests for Slack ops alert pager (no network)."""

from __future__ import annotations

from typing import Any

from backend.shared.ops_alert_pager import maybe_page_slack_for_alert


class _ExecResult:
    def __init__(self, *, fetchone: tuple | None = None) -> None:
        self._fetchone = fetchone

    def fetchone(self) -> tuple | None:
        return self._fetchone


class _FakeConn:
    def execute(self, *_a: object, **_k: object) -> _ExecResult:
        return _ExecResult(fetchone=({"slack_webhook_url": ""},))


def test_pager_skips_when_no_url(monkeypatch: object) -> None:
    called: list[str] = []

    def _fake_urlopen(*_a: object, **_k: object) -> object:
        called.append("x")
        raise AssertionError("should not call")

    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)  # type: ignore[attr-defined]
    maybe_page_slack_for_alert(
        _FakeConn(),  # type: ignore[arg-type]
        alert_type="T",
        severity="info",
        summary="s",
    )
    assert not called
