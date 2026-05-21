from __future__ import annotations

from backend.shared.ops_tasks import (
    _severity_meets_min,
    merge_ops_task_policy,
    _task_title,
)


def test_merge_ops_task_policy_defaults() -> None:
    p = merge_ops_task_policy(None)
    assert p["enabled"] is True
    assert "OUTBOX_DEAD_SPIKE" in p["alert_types"]


def test_severity_gate() -> None:
    assert _severity_meets_min("error", "warning")
    assert not _severity_meets_min("info", "warning")


def test_task_title() -> None:
    t = _task_title("OUTBOX_DEAD_SPIKE", "DEAD rows >= 5")
    assert t.startswith("[OUTBOX_DEAD_SPIKE]")
