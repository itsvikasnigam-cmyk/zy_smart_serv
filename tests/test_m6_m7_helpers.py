"""Unit tests for M6/M7 shared helpers (no Postgres required)."""

from __future__ import annotations

import json

from backend.shared.broadcast_gating import (
    build_template_outbox_body,
    merge_m6_policy,
    plan_allows_broadcast,
    validate_template_only_body,
)
from backend.shared.ops_alerts import insert_ops_alert_event


def test_merge_m6_policy_defaults() -> None:
    p = merge_m6_policy(None)
    assert "trial" in [x.lower() for x in p["blocked_entitlement_plans"]]


def test_plan_allows_broadcast_matrix() -> None:
    p = merge_m6_policy({"blocked_entitlement_plans": ["trial", "starter"]})
    assert plan_allows_broadcast("growth", p) is True
    assert plan_allows_broadcast("Trial", p) is False
    assert plan_allows_broadcast("STARTER", p) is False


def test_validate_template_only_body() -> None:
    body = build_template_outbox_body(template_name="hello_world", language="en_US")
    assert validate_template_only_body(body, template_only=True)[0] is True
    assert validate_template_only_body("not json", template_only=True)[0] is False
    assert validate_template_only_body(
        json.dumps({"template_name": "x", "language": "en", "extra": 1}),
        template_only=True,
    )[0] is False


def test_insert_ops_alert_event_mock_conn() -> None:
    """Smoke: single execute path + IntegrityError swallowed by caller pattern."""

    class _R:
        def fetchone(self) -> tuple[str]:
            return ("evt-1",)

    class _Conn:
        def __init__(self) -> None:
            self.calls = 0

        def execute(self, *_a, **_k) -> _R:
            self.calls += 1
            return _R()

    c = _Conn()
    inserted, eid = insert_ops_alert_event(
        c,  # type: ignore[arg-type]
        alert_type="TEST",
        severity="info",
        summary="s",
        detail={"k": 1},
        dedupe_key=None,
    )
    assert c.calls == 1
    assert inserted is True
    assert eid == "evt-1"
