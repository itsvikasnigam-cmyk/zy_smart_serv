from __future__ import annotations

"""WebSocket route for client_api real-time events.

Client connects to ``ws://<host>/ws?token=<JWT>``.

Server → Client envelope (JSON):
    { "event": <event_name>, "data": {...}, "ts": <iso8601> }

Events:
    hello                — sent immediately after accept with user identity
    message_new          — new inbound (customer) message OR new outbound (AI/agent)
    assignment_changed   — assignment created / reassigned / ended
    typing               — typing presence update for a chat
    chat_state_changed   — chat.state transition (in-process emissions only)
    error                — terminal error envelope before close

Client → Server (optional):
    {"type": "ping"} → server replies with {"event": "hello", "data": {"pong": true}}
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from .auth import decode_jwt
from .events import hub


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ws"])


async def _send_envelope(ws: WebSocket, env: dict) -> None:
    await ws.send_text(json.dumps(env, default=str))


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="missing token")
        return
    try:
        claims = decode_jwt(token)
    except jwt.ExpiredSignatureError:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="token expired")
        return
    except jwt.PyJWTError as e:
        logger.info("ws auth failed: %s", e)
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="invalid token")
        return

    user_id = claims.get("sub")
    client_id = claims.get("cid")
    role = claims.get("role")
    if not user_id or not role:
        await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="malformed claims")
        return
    if not client_id:
        # super_admin without cid must specify ?client_id= to scope subscription.
        client_id = ws.query_params.get("client_id")
        if not client_id:
            await ws.close(code=status.WS_1008_POLICY_VIOLATION, reason="missing client_id for super_admin")
            return

    await ws.accept()
    q = await hub.subscribe(client_id)
    try:
        await _send_envelope(
            ws,
            {
                "event": "hello",
                "data": {"user_id": user_id, "client_id": client_id, "role": role},
                "ts": _now_iso(),
            },
        )

        async def reader() -> None:
            # Best-effort read loop; bail on disconnect. Responds to {"type":"ping"}.
            while True:
                try:
                    msg = await ws.receive_text()
                except WebSocketDisconnect:
                    raise
                try:
                    parsed = json.loads(msg)
                except Exception:
                    parsed = None
                if isinstance(parsed, dict) and parsed.get("type") == "ping":
                    await _send_envelope(ws, {"event": "hello", "data": {"pong": True}, "ts": _now_iso()})

        async def writer() -> None:
            while True:
                env = await q.get()
                await _send_envelope(ws, env)

        reader_task = asyncio.create_task(reader(), name=f"ws-reader-{user_id}")
        writer_task = asyncio.create_task(writer(), name=f"ws-writer-{user_id}")
        done, pending = await asyncio.wait(
            {reader_task, writer_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
        for t in done:
            exc = t.exception()
            if exc and not isinstance(exc, WebSocketDisconnect):
                logger.info("ws task ended with %s: %s", type(exc).__name__, exc)
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("ws handler failed")
        try:
            await ws.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass
    finally:
        await hub.unsubscribe(client_id, q)
