"""Print Postgres NOTIFY payloads on channel ``zy_chat_events`` (dev / ops).

``batch_processor`` emits ``pg_notify('zy_chat_events', '<json>')`` when a sealed
batch results in HANDOFF / NEEDS_OWNER_DATA so downstream services can react
without polling ``inbox_chats``.

Usage (repo root, venv, DATABASE_URL set):

    $env:PYTHONPATH = "$PWD"
    $env:DATABASE_URL = "postgresql+psycopg://..."
    python backend/tools/dev_listen_chat_events.py

Ctrl+C to stop. In another terminal, trigger a handoff (e.g. stop AI engine, send
inbound, let ``batch_processor`` seal the batch).
"""

from __future__ import annotations

import json
import signal
import sys

CHANNEL = "zy_chat_events"


def main() -> int:
    try:
        import psycopg
    except ImportError as e:  # pragma: no cover
        print("psycopg is required (install backend/requirements.txt).", file=sys.stderr)
        raise SystemExit(2) from e

    from backend.shared.config import settings

    dsn = settings.database_url
    stop = False

    def _sigint(_a, _b) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _sigint)

    print(f"LISTEN {CHANNEL} … (Ctrl+C to exit)", flush=True)
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(f"LISTEN {CHANNEL};")
        while not stop:
            try:
                for notify in conn.notifies(timeout=1.0):
                    if stop:
                        break
                    if notify.channel != CHANNEL:
                        continue
                    raw = notify.payload or ""
                    try:
                        obj = json.loads(raw)
                        print(json.dumps(obj, indent=2), flush=True)
                    except Exception:
                        print(raw, flush=True)
            except KeyboardInterrupt:
                break
    print("done.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
