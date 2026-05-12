from __future__ import annotations

import sys
import time
from typing import Any

import httpx


def build_meta_inbound_webhook_payload(
    *,
    meta_phone_number_id: str,
    from_phone: str,
    text_body: str,
    msg_id: str | None = None,
    timestamp: int | None = None,
) -> dict[str, Any]:
    """
    Synthetic Meta Cloud API inbound webhook body (same shape as production).
    Used by this CLI and by tests to keep the contract in one place.
    """
    now = int(time.time())
    mid = msg_id if msg_id is not None else f"wamid.DEV.{now}"
    ts = str(timestamp if timestamp is not None else now)
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": meta_phone_number_id},
                            "messages": [
                                {
                                    "id": mid,
                                    "from": from_phone,
                                    "timestamp": ts,
                                    "type": "text",
                                    "text": {"body": text_body},
                                }
                            ],
                        }
                    }
                ]
            }
        ],
    }


def main() -> int:
    """
    Sends a synthetic Meta inbound webhook to local WA gateway.

    Usage:
      python backend/tools/dev_send_inbound.py --meta-phone-number-id <PHONE_NUMBER_ID> --from <E164> --text "Hi"
    """
    args = sys.argv[1:]
    if "--meta-phone-number-id" not in args or "--from" not in args or "--text" not in args:
        print("Usage: python backend/tools/dev_send_inbound.py --meta-phone-number-id <ID> --from <E164> --text \"Hi\"")
        return 2

    pid = args[args.index("--meta-phone-number-id") + 1]
    from_phone = args[args.index("--from") + 1]
    text_body = args[args.index("--text") + 1]

    payload = build_meta_inbound_webhook_payload(
        meta_phone_number_id=pid,
        from_phone=from_phone,
        text_body=text_body,
    )

    with httpx.Client(timeout=10.0) as client:
        r = client.post("http://127.0.0.1:8081/webhooks/meta/inbound", json=payload)
    print(f"HTTP {r.status_code}")
    print(r.text)
    r.raise_for_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

