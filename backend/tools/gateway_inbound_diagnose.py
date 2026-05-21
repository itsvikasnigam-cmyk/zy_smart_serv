"""Diagnose HTTP 500 on POST /webhooks/meta/inbound (runs same DB path as gateway).

Usage:

    cd ...\\empty-window; . .\\dev-env.ps1
    python backend/tools/gateway_inbound_diagnose.py --meta-phone-number-id 1098044196727032 --from +919876543210
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from sqlalchemy import text

from backend.apps.wa_gateway.main import (
    _fetch_client_row,
    _fetch_inbound_usage_today,
    _load_gateway_runtime,
    _merge_urgent_substrings,
    _load_service_inactive_reply,
    _open_or_extend_batch,
    _resolve_inbound_route,
    _inbound_ai_block_reason,
)
from backend.shared.db import engine
from backend.workers.usage_metrics_common import load_daily_inbound_limits_json
from backend.apps.wa_gateway.meta_payload import normalize_customer_phone_for_route


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--meta-phone-number-id", required=True)
    p.add_argument("--from", dest="from_phone", required=True)
    p.add_argument("--text", default="hello gate 1 diagnose")
    args = p.parse_args()
    meta_id = args.meta_phone_number_id.strip()
    from_phone = args.from_phone.strip()
    text_body = args.text
    meta_msg_id = f"wamid.dev.diagnose.{int(time.time())}"

    try:
        with engine.begin() as conn:
            print("1) resolve route...")
            client_id, wa_number_id = _resolve_inbound_route(
                conn,
                to_phone_number_id=meta_id,
                customer_phone_raw=from_phone,
                x_zy_client_id=None,
            )
            print(f"   client_id={client_id} wa_number_id={wa_number_id}")

            print("2) load runtime config...")
            rt = _load_gateway_runtime(conn)
            limits_root = load_daily_inbound_limits_json(conn)
            urgent_substrings = _merge_urgent_substrings(conn)
            _load_service_inactive_reply(conn)

            print("3) client row + usage...")
            crow = _fetch_client_row(conn, client_id)
            print(f"   entitlement/trial_end={crow}")
            usage = _fetch_inbound_usage_today(conn, client_id)
            print(f"   inbound_usage_today={usage}")

            block_reason, _ = _inbound_ai_block_reason(
                entitlement=crow[0] if crow else "trial",
                trial_end=crow[1] if crow else None,
                inbound_today_before_this_message=usage,
                limits_root=limits_root,
            )
            print(f"   block_reason={block_reason!r}")

            customer_phone = normalize_customer_phone_for_route(from_phone)
            print("4) upsert chat...")
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
            print(f"   chat_id={chat_id}")

            print("5) insert message...")
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
                    "text": text_body,
                    "meta_msg_id": meta_msg_id,
                    "meta_payload": json.dumps({"diagnose": True}),
                },
            ).fetchone()
            print(f"   message inserted={ins is not None}")

            if not block_reason and ins:
                print("6) open/extend batch...")
                _open_or_extend_batch(
                    conn,
                    chat_id=str(chat_id),
                    debounce_seconds=rt["debounce_seconds"],
                    max_debounce_seconds=rt["max_debounce_seconds"],
                    adaptive_enabled=rt["adaptive_enabled"],
                    burst_sec=rt["adaptive_burst_sec"],
                    urgent=False,
                )
                print("   batch OK")

        print("\nOK: diagnose path completed (DB). Try dev_send_inbound again.")
        return 0
    except Exception as e:
        print(f"\nFAILED: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
