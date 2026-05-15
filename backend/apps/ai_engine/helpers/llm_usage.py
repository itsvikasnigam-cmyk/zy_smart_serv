from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy import text

logger = logging.getLogger(__name__)


def check_and_increment_llm_daily_usage(
    engine: Any,
    *,
    client_id: str,
    max_calls_per_day: int,
) -> bool:
    """
    Return True if the client may make one more LLM call today (UTC), after incrementing.

    When ``max_calls_per_day`` <= 0, treat as unlimited.
    """
    if max_calls_per_day <= 0:
        return True
    today = date.today()
    try:
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT call_count FROM ai_llm_daily_usage
                    WHERE client_id = CAST(:cid AS uuid) AND usage_date = :d
                    FOR UPDATE
                    """
                ),
                {"cid": client_id, "d": today},
            ).fetchone()
            current = int(row[0]) if row else 0
            if current >= max_calls_per_day:
                return False
            if row:
                conn.execute(
                    text(
                        """
                        UPDATE ai_llm_daily_usage
                        SET call_count = call_count + 1
                        WHERE client_id = CAST(:cid AS uuid) AND usage_date = :d
                        """
                    ),
                    {"cid": client_id, "d": today},
                )
            else:
                conn.execute(
                    text(
                        """
                        INSERT INTO ai_llm_daily_usage (client_id, usage_date, call_count)
                        VALUES (CAST(:cid AS uuid), :d, 1)
                        ON CONFLICT (client_id, usage_date) DO UPDATE
                        SET call_count = ai_llm_daily_usage.call_count + 1
                        """
                    ),
                    {"cid": client_id, "d": today},
                )
        return True
    except Exception:
        logger.exception("llm daily usage check failed; allowing call (fail-open)")
        return True
