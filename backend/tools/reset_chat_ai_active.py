"""Reset one inbox chat to AI_ACTIVE for dev testing.

Usage:
  cd ...\\empty-window; . .\\dev-env.ps1
  python backend/tools/reset_chat_ai_active.py --chat-id 3e3e24e7-4c41-4999-afb4-5259ce71ed8b
  python backend/tools/reset_chat_ai_active.py --phone 919769825350
"""

from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from sqlalchemy import text

from backend.shared.db import engine


def main() -> int:
    args = sys.argv[1:]
    chat_id = ""
    phone = ""
    if "--chat-id" in args:
        chat_id = args[args.index("--chat-id") + 1]
    if "--phone" in args:
        phone = args[args.index("--phone") + 1].lstrip("+")

    if not chat_id and not phone:
        print("Usage:")
        print("  python backend/tools/reset_chat_ai_active.py --chat-id <uuid>")
        print("  python backend/tools/reset_chat_ai_active.py --phone 919769825350")
        return 2

    with engine.begin() as conn:
        if chat_id:
            row = conn.execute(
                text(
                    """
                    UPDATE inbox_chats
                    SET state = 'AI_ACTIVE',
                        assigned_agent_id = NULL,
                        ai_paused_until = NULL,
                        handoff_reason = NULL,
                        pending_since = NULL
                    WHERE id = CAST(:cid AS uuid)
                    RETURNING id::text, customer_phone, state
                    """
                ),
                {"cid": chat_id},
            ).fetchone()
        else:
            row = conn.execute(
                text(
                    """
                    UPDATE inbox_chats
                    SET state = 'AI_ACTIVE',
                        assigned_agent_id = NULL,
                        ai_paused_until = NULL,
                        handoff_reason = NULL,
                        pending_since = NULL
                    WHERE customer_phone = :phone
                    RETURNING id::text, customer_phone, state
                    """
                ),
                {"phone": phone},
            ).fetchone()

    if not row:
        print("No chat updated.")
        return 1
    print("OK: reset chat to AI_ACTIVE")
    print("  chat_id:", row[0])
    print("  customer_phone:", row[1])
    print("  state:", row[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
