from __future__ import annotations

import sys
from pathlib import Path

# Allow: python backend\tools\dev_check.py (repo root on sys.path without dev-env.ps1)
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    with engine.begin() as conn:
        msg = conn.execute(
            text(
                """
                SELECT id, chat_id, sender, direction, text, timestamp, meta_msg_id
                FROM inbox_messages
                ORDER BY timestamp DESC
                LIMIT 1
                """
            )
        ).fetchone()
        batch = conn.execute(
            text(
                """
                SELECT id, chat_id, status, process_after, max_process_after, inbound_msg_count, opened_at, sealed_at
                FROM inbox_inbound_batches
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
        ).fetchone()
        outbox = conn.execute(
            text(
                """
                SELECT id, chat_id, status, kind, body_text, attempt_count, next_attempt_at,
                       meta_message_id, created_at, last_error_code, last_error_detail, dead_at, sent_at
                FROM wa_outbox
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
        ).fetchone()
        chat_outbox = None
        chat = None
        if msg:
            chat = conn.execute(
                text(
                    """
                    SELECT id, customer_phone, state, assigned_agent_id, ai_paused_until,
                           handoff_reason, pending_since, last_customer_msg_at, last_outbound_at
                    FROM inbox_chats
                    WHERE id = CAST(:chat_id AS uuid)
                    """
                ),
                {"chat_id": str(msg[1])},
            ).fetchone()
            chat_outbox = conn.execute(
                text(
                    """
                    SELECT id, chat_id, status, kind, body_text, attempt_count, next_attempt_at,
                           meta_message_id, created_at, last_error_code, last_error_detail, dead_at, sent_at
                    FROM wa_outbox
                    WHERE chat_id = CAST(:chat_id AS uuid)
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"chat_id": str(msg[1])},
            ).fetchone()

    print("=== LATEST inbox_messages ===")
    print(msg or "(none)")
    print("\n=== CHAT FOR LATEST MESSAGE ===")
    print(chat or "(none)")
    print("\n=== LATEST inbox_inbound_batches ===")
    print(batch or "(none)")
    print("\n=== LATEST wa_outbox FOR LATEST MESSAGE CHAT ===")
    print(chat_outbox or "(none)")
    print("\n=== LATEST wa_outbox ===")
    print(outbox or "(none)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

