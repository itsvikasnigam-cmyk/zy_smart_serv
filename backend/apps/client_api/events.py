from __future__ import annotations

"""In-process pub/sub Hub + background poller for cross-process DB events.

Topology:
- ``Hub.subscribe(client_id)`` returns an asyncio.Queue that receives event dicts
  for that client. Multiple subscribers per client are supported (each gets its
  own queue).
- ``hub.publish(client_id, event_dict)`` fans out non-blocking; if a subscriber
  queue is full it's silently dropped for that subscriber (we never block a
  publisher).
- ``DBPoller`` runs as a background asyncio task. It scans:
    * ``inbox_messages`` for new rows (direction='in', sender='customer') →
      ``message_new``
    * ``wa_outbox`` for new AI_REPLY / AGENT_REPLY / OWNER_ALERT rows → ``message_new``
    * ``chat_assignments`` for new rows → ``assignment_changed``
    * ``inbox_notifications`` for new rows → ``notification`` (in-app + cross-process fan-out)
  Watermarks are kept in-memory; on startup we anchor to ``now()`` so we don't
  fan out historical state. Note: cross-process ``chat_state_changed`` is not
  detected here yet; in-process endpoints publish it directly. ``batch_processor``
  emits ``pg_notify('zy_chat_events', …)`` on HANDOFF / NEEDS_OWNER_DATA; use
  ``python backend/tools/dev_listen_chat_events.py`` to watch payloads locally.
  The in-process ``DBPoller`` remains the default fan-out for ``inbox_messages`` /
  ``wa_outbox`` / ``chat_assignments`` / ``inbox_notifications`` until a LISTEN
  bridge replaces polling. Do not ``hub.publish('notification', …)`` from REST
  handlers for rows also inserted into ``inbox_notifications`` — that would
  duplicate the poller-delivered event for in-process subscribers.
"""

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from backend.shared.config import settings
from backend.shared.db import engine

logger = logging.getLogger(__name__)

EVENT_MESSAGE_NEW = "message_new"
EVENT_ASSIGNMENT_CHANGED = "assignment_changed"
EVENT_TYPING = "typing"
EVENT_CHAT_STATE_CHANGED = "chat_state_changed"
EVENT_NOTIFICATION = "notification"

_QUEUE_MAX = 256


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _envelope(event: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"event": event, "data": data, "ts": _now_iso()}


class Hub:
    """Lightweight in-process pub/sub keyed by client_id."""

    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, client_id: str) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_QUEUE_MAX)
        async with self._lock:
            self._subs[client_id].append(q)
        return q

    async def unsubscribe(self, client_id: str, q: asyncio.Queue[dict[str, Any]]) -> None:
        async with self._lock:
            lst = self._subs.get(client_id)
            if not lst:
                return
            try:
                lst.remove(q)
            except ValueError:
                pass
            if not lst:
                self._subs.pop(client_id, None)

    def publish(self, client_id: str, event: str, data: dict[str, Any]) -> None:
        """Non-blocking fan-out; drops on a full subscriber queue."""
        env = _envelope(event, data)
        subs = self._subs.get(client_id)
        if not subs:
            return
        for q in list(subs):
            try:
                q.put_nowait(env)
            except asyncio.QueueFull:
                logger.warning("WS subscriber queue full; dropping event=%s for client=%s", event, client_id)

    def subscriber_count(self, client_id: str | None = None) -> int:
        if client_id is None:
            return sum(len(v) for v in self._subs.values())
        return len(self._subs.get(client_id, []))


hub = Hub()


class DBPoller:
    """Polls DB tables for new rows since startup and fans events into the Hub.

    Watermarks are timestamps; we re-fetch with strict `>` to avoid replays.
    A `seen_ids` ring is kept to suppress same-timestamp duplicates (UUID v4
    rows occasionally share a `now()` value).
    """

    SEEN_RING = 500

    def __init__(self, *, poll_ms: int | None = None) -> None:
        self.poll_seconds = max(0.1, (poll_ms or settings.client_api_event_poll_ms) / 1000.0)
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        # Watermarks anchored on first run() invocation.
        self._wm_inbox_msg: datetime | None = None
        self._wm_outbox: datetime | None = None
        self._wm_assignment: datetime | None = None
        self._wm_notification: datetime | None = None
        self._seen_msg: list[str] = []
        self._seen_outbox: list[str] = []
        self._seen_assignment: list[str] = []
        self._seen_notification: list[str] = []

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="client_api.db_poller")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        # Anchor watermarks to "now" so we don't replay history on first start.
        anchor = datetime.now(tz=timezone.utc)
        self._wm_inbox_msg = anchor
        self._wm_outbox = anchor
        self._wm_assignment = anchor
        self._wm_notification = anchor
        logger.info("client_api DBPoller started (interval=%.2fs)", self.poll_seconds)
        while not self._stop.is_set():
            t0 = time.monotonic()
            try:
                await asyncio.to_thread(self._tick)
            except Exception:
                logger.exception("DBPoller tick failed")
            dt = time.monotonic() - t0
            sleep_for = max(0.0, self.poll_seconds - dt)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=sleep_for)
            except asyncio.TimeoutError:
                pass

    def _remember(self, ring: list[str], row_id: str) -> bool:
        if row_id in ring:
            return False
        ring.append(row_id)
        if len(ring) > self.SEEN_RING:
            del ring[: len(ring) - self.SEEN_RING]
        return True

    def _tick(self) -> None:
        # If no subscribers, skip DB load entirely (cheap idle).
        if hub.subscriber_count() == 0:
            return
        self._poll_inbox_messages()
        self._poll_outbox()
        self._poll_assignments()
        self._poll_notifications()

    def _poll_inbox_messages(self) -> None:
        wm = self._wm_inbox_msg
        if wm is None:
            return
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT m.id::text, m.chat_id::text, m.direction, m.sender, m.text,
                           m.timestamp, m.meta_msg_id, c.client_id::text
                    FROM inbox_messages m
                    JOIN inbox_chats c ON c.id = m.chat_id
                    WHERE m.timestamp >= :wm
                    ORDER BY m.timestamp ASC
                    LIMIT 200
                    """
                ),
                {"wm": wm},
            ).all()
        max_ts = wm
        for r in rows:
            row_id = r[0]
            if not self._remember(self._seen_msg, row_id):
                continue
            ts = r[5]
            if ts and ts > max_ts:
                max_ts = ts
            client_id = r[7]
            hub.publish(
                client_id,
                EVENT_MESSAGE_NEW,
                {
                    "chat_id": r[1],
                    "message": {
                        "id": row_id,
                        "chat_id": r[1],
                        "direction": r[2],
                        "sender": r[3],
                        "text": r[4],
                        "timestamp": ts.isoformat() if ts else None,
                        "meta_msg_id": r[6],
                        "source": "inbox_messages",
                    },
                },
            )
        self._wm_inbox_msg = max_ts

    def _poll_outbox(self) -> None:
        wm = self._wm_outbox
        if wm is None:
            return
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id::text, client_id::text, chat_id::text, kind, body_text,
                           status, created_at
                    FROM wa_outbox
                    WHERE created_at >= :wm
                      AND kind IN ('AI_REPLY','AGENT_REPLY','OWNER_ALERT')
                    ORDER BY created_at ASC
                    LIMIT 200
                    """
                ),
                {"wm": wm},
            ).all()
        max_ts = wm
        for r in rows:
            row_id = r[0]
            if not self._remember(self._seen_outbox, row_id):
                continue
            ts = r[6]
            if ts and ts > max_ts:
                max_ts = ts
            client_id = r[1]
            sender = {"AI_REPLY": "ai", "AGENT_REPLY": "agent", "OWNER_ALERT": "system"}.get(r[3], "system")
            hub.publish(
                client_id,
                EVENT_MESSAGE_NEW,
                {
                    "chat_id": r[2],
                    "message": {
                        "id": row_id,
                        "chat_id": r[2],
                        "direction": "out",
                        "sender": sender,
                        "text": r[4],
                        "timestamp": ts.isoformat() if ts else None,
                        "meta_msg_id": None,
                        "source": "wa_outbox",
                        "outbox_kind": r[3],
                        "outbox_status": r[5],
                    },
                },
            )
        self._wm_outbox = max_ts

    def _poll_assignments(self) -> None:
        wm = self._wm_assignment
        if wm is None:
            return
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id::text, chat_id::text, client_id::text,
                           assigned_to_user_id::text, assigned_by_user_id::text,
                           reason, status, created_at, ended_at
                    FROM chat_assignments
                    WHERE created_at >= :wm OR (ended_at IS NOT NULL AND ended_at >= :wm)
                    ORDER BY created_at ASC
                    LIMIT 200
                    """
                ),
                {"wm": wm},
            ).all()
        max_ts = wm
        for r in rows:
            row_id = r[0]
            # Key on (id, status, ended_at) so we emit once for ACTIVE and once
            # for the terminal transition when ended_at lands in our window.
            seen_key = f"{row_id}:{r[6]}:{r[8].isoformat() if r[8] else ''}"
            if not self._remember(self._seen_assignment, seen_key):
                continue
            ts = r[7]
            if ts and ts > max_ts:
                max_ts = ts
            if r[8] and r[8] > max_ts:
                max_ts = r[8]
            client_id = r[2]
            hub.publish(
                client_id,
                EVENT_ASSIGNMENT_CHANGED,
                {
                    "chat_id": r[1],
                    "assignment_id": row_id,
                    "assigned_to_user_id": r[3],
                    "assigned_by_user_id": r[4],
                    "reason": r[5],
                    "status": r[6],
                    "created_at": ts.isoformat() if ts else None,
                    "ended_at": r[8].isoformat() if r[8] else None,
                },
            )
        self._wm_assignment = max_ts

    def _poll_notifications(self) -> None:
        wm = self._wm_notification
        if wm is None:
            return
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    """
                    SELECT id::text, client_id::text, recipient_user_id::text, chat_id::text,
                           kind, title, body, created_at
                    FROM inbox_notifications
                    WHERE created_at >= :wm
                    ORDER BY created_at ASC
                    LIMIT 200
                    """
                ),
                {"wm": wm},
            ).all()
        max_ts = wm
        for r in rows:
            row_id = r[0]
            if not self._remember(self._seen_notification, row_id):
                continue
            ts = r[7]
            if ts and ts > max_ts:
                max_ts = ts
            client_id = r[1]
            hub.publish(
                client_id,
                EVENT_NOTIFICATION,
                {
                    "client_id": client_id,
                    "notification_id": row_id,
                    "recipient_user_id": r[2],
                    "kind": r[4],
                    "title": r[5],
                    "body": r[6],
                    "chat_id": r[3],
                    "created_at": ts.isoformat() if ts else None,
                },
            )
        self._wm_notification = max_ts


poller = DBPoller()
