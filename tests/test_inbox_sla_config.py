"""Phase 4 inbox SLA config helpers."""

from __future__ import annotations

from backend.shared.inbox_sla_config import (
    DEFAULT_APOLOGY_HOURS,
    DEFAULT_REALERT_HOURS,
    OwnerWaitConfig,
)


def test_owner_wait_defaults() -> None:
    ow = OwnerWaitConfig(
        realert_hours=DEFAULT_REALERT_HOURS,
        apology_hours=DEFAULT_APOLOGY_HOURS,
        apology_customer_reply="test",
    )
    assert ow.realert_hours == 4
    assert ow.apology_hours == 8
