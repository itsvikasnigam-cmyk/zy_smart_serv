"""Option C phase 2 — product config helpers."""

from __future__ import annotations

from backend.shared.product_config import (
    DEFAULT_TRIAL_DAYS,
    PHASE2_USAGE_LIMITS,
    _coerce_positive_int,
)
from backend.workers.usage_metrics_common import plan_soft_hard, should_mark_hard


def test_phase2_trial_starter_hard_block_35() -> None:
    sw, hb = plan_soft_hard(PHASE2_USAGE_LIMITS, "trial")
    assert sw == 30
    assert hb == 35
    assert not should_mark_hard(35, hb)
    assert should_mark_hard(36, hb)


def test_coerce_trial_days() -> None:
    assert _coerce_positive_int(3, DEFAULT_TRIAL_DAYS) == 3
    assert _coerce_positive_int(None, DEFAULT_TRIAL_DAYS) == DEFAULT_TRIAL_DAYS
