"""Phase 5 observability helpers."""

from __future__ import annotations

from backend.shared.observability import new_trace_id


def test_new_trace_id_uuid_shape() -> None:
    tid = new_trace_id()
    assert len(tid) == 36
    assert tid.count("-") == 4
