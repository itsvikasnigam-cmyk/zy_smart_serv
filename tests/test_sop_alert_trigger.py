"""Unit tests for alert → SOP run auto-trigger (mocked DB)."""

from __future__ import annotations

import json
from typing import Any

from backend.shared.sop_alert_trigger import maybe_trigger_sop_run_for_alert


class _ExecResult:
    def __init__(self, *, fetchone: tuple | None = None) -> None:
        self._fetchone = fetchone

    def fetchone(self) -> tuple | None:
        return self._fetchone


class _FakeConn:
    def __init__(self, handlers: list[Any]) -> None:
        self._handlers = list(handlers)
        self.executed: list[tuple[str, dict[str, Any] | None]] = []

    def execute(self, stmt: object, params: dict[str, Any] | None = None) -> _ExecResult:
        self.executed.append((str(stmt), params))
        if not self._handlers:
            raise AssertionError("unexpected execute")
        handler = self._handlers.pop(0)
        if callable(handler):
            return handler(stmt, params)
        return handler


def test_maybe_trigger_maps_alert_to_run() -> None:
    sop_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    run_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"

    def _enabled(_s: object, _p: dict[str, Any] | None) -> _ExecResult:
        return _ExecResult(fetchone=(True,))

    def _map(_s: object, _p: dict[str, Any] | None) -> _ExecResult:
        return _ExecResult(
            fetchone=(
                {
                    "BILLING_WEBHOOK_PROCESSING_ERROR": "payment-failure",
                },
            )
        )

    def _sop(_s: object, p: dict[str, Any] | None) -> _ExecResult:
        assert p and p["slug"] == "payment-failure"
        return _ExecResult(fetchone=(sop_id, 1))

    def _dedupe_check(_s: object, _p: dict[str, Any] | None) -> _ExecResult:
        return _ExecResult(fetchone=None)

    def _insert(_s: object, p: dict[str, Any] | None) -> _ExecResult:
        assert p is not None
        ctx = json.loads(p["ctx"])
        assert ctx["alert_type"] == "BILLING_WEBHOOK_PROCESSING_ERROR"
        assert ctx["alert_dedupe_key"] == "dk1"
        return _ExecResult(fetchone=(run_id,))

    conn = _FakeConn(
        [
            _enabled,
            _map,
            _sop,
            _dedupe_check,
            _insert,
        ]
    )
    rid = maybe_trigger_sop_run_for_alert(
        conn,  # type: ignore[arg-type]
        alert_type="BILLING_WEBHOOK_PROCESSING_ERROR",
        summary="billing failed",
        detail={"client_id": None},
        dedupe_key="dk1",
    )
    assert rid == run_id
    assert not conn._handlers


def test_maybe_trigger_skips_unknown_alert_type() -> None:
    conn = _FakeConn(
        [
            lambda _s, _p: _ExecResult(fetchone=(True,)),
            lambda _s, _p: _ExecResult(fetchone=({})),
        ]
    )
    assert (
        maybe_trigger_sop_run_for_alert(
            conn,  # type: ignore[arg-type]
            alert_type="UNKNOWN_ALERT",
            summary="x",
        )
        is None
    )
