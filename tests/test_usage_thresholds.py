"""Unit tests for Chat K usage limit helpers (no database)."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from backend.workers.usage_metrics_common import (
    plan_soft_hard,
    should_mark_hard,
    should_mark_soft,
    utc_calendar_date,
)


@pytest.mark.parametrize(
    "inbound,soft,expected",
    [
        (0, 10, False),
        (9, 10, False),
        (10, 10, True),
        (11, 10, True),
        (5, None, False),
    ],
)
def test_should_mark_soft(inbound: int, soft: int | None, expected: bool) -> None:
    assert should_mark_soft(inbound, soft) is expected


@pytest.mark.parametrize(
    "inbound,hard,expected",
    [
        (0, 10, False),
        (9, 10, False),
        (10, 10, True),
        (0, 1, False),
        (1, 1, True),
        (5, None, False),
    ],
)
def test_should_mark_hard(inbound: int, hard: int | None, expected: bool) -> None:
    assert should_mark_hard(inbound, hard) is expected


def test_plan_soft_hard() -> None:
    limits = {
        "trial": {"soft_warn": 100, "hard_block": 200},
        "_default": {"soft_warn": 1, "hard_block": 2},
    }
    assert plan_soft_hard(limits, "trial") == (100, 200)
    assert plan_soft_hard(limits, "unknown_plan") == (1, 2)


def test_utc_calendar_date_naive_utc_assumed() -> None:
    ts = datetime(2026, 5, 13, 23, 0, 0)
    assert utc_calendar_date(ts) == date(2026, 5, 13)


def test_utc_calendar_date_tz_aware() -> None:
    ts = datetime(2026, 5, 13, 22, 30, 0, tzinfo=timezone.utc)
    assert utc_calendar_date(ts) == date(2026, 5, 13)
