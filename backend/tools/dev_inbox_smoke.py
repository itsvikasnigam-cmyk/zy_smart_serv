from __future__ import annotations

"""End-to-end smoke for client_api (M3/M4) — no Flutter required.

Drives the assign flow:
    1) login as owner + agent (httpx)
    2) list inbox chats; auto-pick the most recent OR the one matching --chat-id
    3) (optionally) connect a WebSocket as the agent and stream events
    4) owner assigns the chat to the agent
    5) agent posts a typing heartbeat
    6) agent posts a reply (mirrors inbox_messages + enqueues wa_outbox AGENT_REPLY)
    7) reassign to owner, then unassign (expect ``HUMAN_REQ``)
    8) owner resolves the chat (``POST …/resolve`` → ``CLOSED``)
    9) prints captured WS events (if --listen-seconds > 0)

Usage:
    python backend/tools/dev_inbox_smoke.py \
        --base-url http://127.0.0.1:8085 \
        --owner-email owner1@example.com --owner-password Owner!2026 \
        --agent-email agent1@example.com --agent-password Agent!2026 \
        [--chat-id <UUID>] [--listen-seconds 6]

Pre-reqs:
    - Run migrations + seed (dev_seed.py)
    - Run wa_gateway and post at least one inbound (dev_send_inbound.py)
    - Run client_api on --port 8085
    - Run dev_seed_users.py --client-id <CLIENT_ID>
"""

import argparse
import asyncio
import json
import sys
from typing import Any

import httpx

try:
    import websockets  # bundled with uvicorn[standard]
except Exception:  # pragma: no cover - environment without websockets
    websockets = None  # type: ignore[assignment]


def login(client: httpx.Client, base_url: str, email: str, password: str) -> dict[str, Any]:
    r = client.post(f"{base_url}/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def list_chats(client: httpx.Client, base_url: str, token: str) -> list[dict[str, Any]]:
    r = client.get(f"{base_url}/inbox/chats", headers=bearer(token), params={"limit": 25})
    r.raise_for_status()
    return r.json()["items"]


def get_chat(client: httpx.Client, base_url: str, token: str, chat_id: str) -> dict[str, Any]:
    r = client.get(f"{base_url}/inbox/chats/{chat_id}", headers=bearer(token))
    r.raise_for_status()
    return r.json()


def assign(
    client: httpx.Client, base_url: str, token: str, chat_id: str, user_id: str, *, mode: str = "assign", reason: str | None = None
) -> dict[str, Any]:
    path = "assign" if mode == "assign" else "reassign"
    r = client.post(
        f"{base_url}/inbox/chats/{chat_id}/{path}",
        headers=bearer(token),
        json={"user_id": user_id, "reason": reason},
    )
    r.raise_for_status()
    return r.json()


def resolve_chat(
    client: httpx.Client, base_url: str, token: str, chat_id: str, reason: str | None = None
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if reason:
        body["reason"] = reason
    r = client.post(
        f"{base_url}/inbox/chats/{chat_id}/resolve",
        headers=bearer(token),
        json=body,
    )
    r.raise_for_status()
    return r.json()


def unassign(client: httpx.Client, base_url: str, token: str, chat_id: str, reason: str | None) -> dict[str, Any]:
    r = client.post(
        f"{base_url}/inbox/chats/{chat_id}/unassign",
        headers=bearer(token),
        json={"reason": reason},
    )
    r.raise_for_status()
    return r.json()


def typing(client: httpx.Client, base_url: str, token: str, chat_id: str, *, state: str = "typing") -> dict[str, Any]:
    r = client.post(
        f"{base_url}/inbox/chats/{chat_id}/typing",
        headers=bearer(token),
        json={"state": state, "ttl_seconds": 5},
    )
    r.raise_for_status()
    return r.json()


def reply(client: httpx.Client, base_url: str, token: str, chat_id: str, body: str) -> dict[str, Any]:
    r = client.post(
        f"{base_url}/inbox/chats/{chat_id}/reply",
        headers=bearer(token),
        json={"text": body},
    )
    r.raise_for_status()
    return r.json()


async def ws_listener(base_url: str, token: str, seconds: float, captured: list[dict[str, Any]]) -> None:
    if websockets is None:
        print("[ws] 'websockets' lib not available; skipping WS listener")
        return
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://") + f"/ws?token={token}"
    try:
        async with websockets.connect(ws_url, ping_interval=None, open_timeout=5) as conn:
            try:
                while True:
                    msg = await asyncio.wait_for(conn.recv(), timeout=seconds)
                    try:
                        env = json.loads(msg)
                    except Exception:
                        env = {"raw": msg}
                    captured.append(env)
                    print(f"[ws] {env.get('event')}  {json.dumps(env.get('data'), default=str)[:200]}")
            except asyncio.TimeoutError:
                pass
    except Exception as e:
        print(f"[ws] error: {type(e).__name__}: {e}")


async def amain() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8085")
    p.add_argument("--owner-email", default="owner1@example.com")
    p.add_argument("--owner-password", default="Owner!2026")
    p.add_argument("--agent-email", default="agent1@example.com")
    p.add_argument("--agent-password", default="Agent!2026")
    p.add_argument("--chat-id", default=None, help="If omitted, picks the most recent chat for the client")
    p.add_argument("--listen-seconds", type=float, default=6.0, help="WS observation window (0 to skip)")
    p.add_argument("--reply-text", default="Hi! An agent here — how can I help?")
    args = p.parse_args()

    with httpx.Client(timeout=20.0) as client:
        try:
            owner = login(client, args.base_url, args.owner_email, args.owner_password)
            agent = login(client, args.base_url, args.agent_email, args.agent_password)
        except httpx.HTTPStatusError as e:
            print(f"login failed: {e.response.status_code} {e.response.text}", file=sys.stderr)
            return 2

        print(f"[auth] owner.id={owner['user']['id']}  agent.id={agent['user']['id']}  client_id={owner['user']['client_id']}")
        owner_tok = owner["access_token"]
        agent_tok = agent["access_token"]

        chats = list_chats(client, args.base_url, owner_tok)
        if not chats:
            print("no chats found — run dev_send_inbound.py first to seed one")
            return 3
        chat = next((c for c in chats if c["id"] == args.chat_id), chats[0]) if args.chat_id else chats[0]
        chat_id = chat["id"]
        print(f"[inbox] picked chat_id={chat_id}  customer={chat['customer_phone']}  state={chat['state']}  assigned={chat['assigned_agent_id']}")

        captured: list[dict[str, Any]] = []
        ws_task: asyncio.Task | None = None
        if args.listen_seconds > 0:
            ws_task = asyncio.create_task(
                ws_listener(args.base_url, agent_tok, args.listen_seconds, captured),
                name="ws-listener",
            )
            await asyncio.sleep(0.4)

        # 1) Owner assigns to agent
        r1 = assign(client, args.base_url, owner_tok, chat_id, agent["user"]["id"], reason="picking up")
        print(f"[assign] OK  assignment_id={r1['id']}  assigned_to={r1['assigned_to_user_id']}")

        # 2) Agent typing
        r2 = typing(client, args.base_url, agent_tok, chat_id, state="typing")
        print(f"[typing] OK  expires_at={r2.get('expires_at')}")

        # 3) Agent replies
        r3 = reply(client, args.base_url, agent_tok, chat_id, args.reply_text)
        print(f"[reply] OK  msg_id={r3['message']['id']}  outbox_id={r3['outbox_id']}  idem={r3['idempotency_key']}")

        # 4) Owner reassigns back to themselves
        r4 = assign(
            client, args.base_url, owner_tok, chat_id, owner["user"]["id"], mode="reassign", reason="taking over"
        )
        print(f"[reassign] OK  assignment_id={r4['id']}  assigned_to={r4['assigned_to_user_id']}")

        # 5) Owner unassigns
        r5 = unassign(client, args.base_url, owner_tok, chat_id, "wrapping up")
        print(f"[unassign] OK  state={r5.get('state')}")

        r6 = resolve_chat(client, args.base_url, owner_tok, chat_id, reason="dev_inbox_smoke")
        print(f"[resolve] OK  state={r6.get('state')}  changed={r6.get('changed')}")

        # Re-fetch detail for final view
        detail = get_chat(client, args.base_url, owner_tok, chat_id)
        print(f"[detail] state={detail['chat']['state']}  msgs={len(detail['messages'])}  pending_outbound={len(detail['pending_outbound'])}")

        if ws_task is not None:
            try:
                await asyncio.wait_for(ws_task, timeout=args.listen_seconds + 2)
            except asyncio.TimeoutError:
                pass
            print(f"[ws] captured {len(captured)} envelope(s):")
            for e in captured:
                print(f"      - {e.get('event')}")

    print("OK")
    return 0


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    raise SystemExit(main())
