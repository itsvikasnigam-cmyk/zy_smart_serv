"""Gate 1 probe: run inbound DB steps and write gate1_probe_result.txt (no HTTP).

Usage:
  cd ...\\empty-window; . .\\dev-env.ps1
  python backend/tools/gate1_probe.py
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path

from sqlalchemy import text

from backend.apps.wa_gateway.main import (
    _fetch_client_row,
    _fetch_inbound_usage_today,
    _inbound_ai_block_reason,
    _load_gateway_runtime,
    _load_service_inactive_reply,
    _merge_urgent_substrings,
    _open_or_extend_batch,
    _resolve_inbound_route,
)
from backend.apps.wa_gateway.meta_payload import normalize_customer_phone_for_route
from backend.shared.config import settings
from backend.shared.db import engine
from backend.workers.usage_metrics_common import load_daily_inbound_limits_json

META_ID = "1098044196727032"
FROM_PHONE = "+919876543210"
TEXT = "hello gate 1 probe"
OUT = Path(__file__).resolve().parents[2] / "gate1_probe_result.txt"


def log(lines: list[str], msg: str) -> None:
    lines.append(msg)


def main() -> int:
    lines: list[str] = []
    log(lines, f"app_env={settings.app_env!r}")
    log(lines, f"database_url={settings.database_url[:40]}...")
    log(lines, f"meta_app_secret_set={bool(settings.meta_app_secret)}")
    try:
        with engine.begin() as conn:
            log(lines, "db: connected")
            client_id, wa_number_id = _resolve_inbound_route(
                conn,
                to_phone_number_id=META_ID,
                customer_phone_raw=FROM_PHONE,
                x_zy_client_id=None,
            )
            log(lines, f"route: client_id={client_id} wa_number_id={wa_number_id}")
            rt = _load_gateway_runtime(conn)
            log(lines, f"runtime: {rt}")
            limits_root = load_daily_inbound_limits_json(conn)
            log(lines, f"limits keys: {list(limits_root.keys())}")
            _merge_urgent_substrings(conn)
            _load_service_inactive_reply(conn)
            crow = _fetch_client_row(conn, client_id)
            log(lines, f"client: {crow}")
            usage = _fetch_inbound_usage_today(conn, client_id)
            block, _ = _inbound_ai_block_reason(
                entitlement=crow[0] if crow else "trial",
                trial_end=crow[1] if crow else None,
                inbound_today_before_this_message=usage,
                limits_root=limits_root,
            )
            log(lines, f"usage_today={usage} block_reason={block!r}")
            customer_phone = normalize_customer_phone_for_route(FROM_PHONE)
            chat_id = conn.execute(
                text(
                    """
                    INSERT INTO inbox_chats (client_id, customer_phone, waba_number, state, last_customer_msg_at)
                    VALUES (CAST(:client_id AS uuid), :customer_phone, CAST(:waba_number AS uuid), 'AI_ACTIVE', now())
                    ON CONFLICT (client_id, customer_phone)
                    DO UPDATE SET last_customer_msg_at = EXCLUDED.last_customer_msg_at,
                                  waba_number = COALESCE(inbox_chats.waba_number, EXCLUDED.waba_number)
                    RETURNING id
                    """
                ),
                {
                    "client_id": client_id,
                    "customer_phone": customer_phone,
                    "waba_number": wa_number_id,
                },
            ).scalar_one()
            log(lines, f"chat_id={chat_id}")
            meta_msg_id = "wamid.dev.gate1.probe"
            ins = conn.execute(
                text(
                    """
                    INSERT INTO inbox_messages (chat_id, direction, sender, text, timestamp, meta_msg_id, meta_payload)
                    SELECT
                      CAST(:chat_id AS uuid), 'in', 'customer', :text, now(), :meta_msg_id,
                      CAST(:meta_payload AS jsonb)
                    WHERE NOT EXISTS (
                      SELECT 1 FROM inbox_messages
                      WHERE meta_msg_id = :meta_msg_id AND meta_msg_id IS NOT NULL
                    )
                    RETURNING id
                    """
                ),
                {
                    "chat_id": str(chat_id),
                    "text": TEXT,
                    "meta_msg_id": meta_msg_id,
                    "meta_payload": json.dumps({"probe": True}),
                },
            ).fetchone()
            log(lines, f"message inserted={ins is not None}")
            if not block and ins:
                _open_or_extend_batch(
                    conn,
                    chat_id=str(chat_id),
                    debounce_seconds=rt["debounce_seconds"],
                    max_debounce_seconds=rt["max_debounce_seconds"],
                    adaptive_enabled=rt["adaptive_enabled"],
                    burst_sec=rt["adaptive_burst_sec"],
                    urgent=False,
                )
                log(lines, "batch: OK")
        log(lines, "RESULT: OK")
        code = 0
    except Exception as exc:
        log(lines, f"RESULT: FAILED {type(exc).__name__}: {exc}")
        log(lines, traceback.format_exc())
        code = 1
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT}")
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
