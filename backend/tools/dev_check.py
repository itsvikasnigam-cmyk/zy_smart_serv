from __future__ import annotations

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
                SELECT id, chat_id, status, kind, body_text, attempt_count, next_attempt_at, meta_message_id, created_at
                FROM wa_outbox
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
        ).fetchone()

    print("=== LATEST inbox_messages ===")
    print(msg or "(none)")
    print("\n=== LATEST inbox_inbound_batches ===")
    print(batch or "(none)")
    print("\n=== LATEST wa_outbox ===")
    print(outbox or "(none)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

