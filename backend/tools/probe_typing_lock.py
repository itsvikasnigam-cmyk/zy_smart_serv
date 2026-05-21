"""Dev probe: show typing lock config + active typing rows for a chat.

Usage:
  python backend/tools/probe_typing_lock.py --chat-id <uuid>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import text

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from backend.shared.db import engine
from backend.shared.inbox_typing_lock import (
    LEGACY_HARD_LOCK_KEY,
    POLICY_KEY,
    has_active_agent_typing,
    is_typing_lock_enabled,
    merge_typing_lock_policy,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chat-id", required=True)
    args = ap.parse_args()

    with engine.connect() as conn:
        enabled = is_typing_lock_enabled(conn)
        active, uid = has_active_agent_typing(conn, args.chat_id)
        rows = conn.execute(
            text(
                """
                SELECT key, value_json
                FROM ops_runtime_config
                WHERE key IN (:p, :l)
                """
            ),
            {"p": POLICY_KEY, "l": LEGACY_HARD_LOCK_KEY},
        ).all()
        presence = conn.execute(
            text(
                """
                SELECT user_id::text, state, expires_at, updated_at
                FROM chat_presence
                WHERE chat_id = CAST(:cid AS uuid)
                ORDER BY expires_at DESC
                """
            ),
            {"cid": args.chat_id},
        ).all()

    cfg = {r[0]: r[1] for r in rows}
    print(f"typing_lock_enabled={enabled}")
    print(f"agent_typing_active={active} user_id={uid}")
    for k, v in cfg.items():
        print(f"ops {k} = {v}")
    print(f"policy merged = {merge_typing_lock_policy(cfg.get(POLICY_KEY))}")
    print("chat_presence rows:")
    for r in presence:
        print(f"  {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
