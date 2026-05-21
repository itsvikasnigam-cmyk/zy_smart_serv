from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
from typing import Any

import httpx


def build_meta_inbound_webhook_payload(
    *,
    meta_phone_number_id: str,
    from_phone: str,
    text_body: str,
    message_type: str = "text",
    msg_id: str | None = None,
    timestamp: int | None = None,
) -> dict[str, Any]:
    """
    Synthetic Meta Cloud API inbound webhook body (same shape as production).
    Used by this CLI and by tests to keep the contract in one place.
    """
    now = int(time.time())
    mid = msg_id if msg_id is not None else f"wamid.DEV.{now}"
    ts = timestamp if timestamp is not None else now
    if message_type == "text":
        msg = {
            "id": mid,
            "from": from_phone,
            "timestamp": ts,
            "type": "text",
            "text": {"body": text_body},
        }
    elif message_type == "interactive_button":
        msg = {
            "id": mid,
            "from": from_phone,
            "timestamp": ts,
            "type": "interactive",
            "interactive": {"type": "button_reply", "button_reply": {"id": "btn_dev", "title": text_body}},
        }
    else:
        msg = {
            "id": mid,
            "from": from_phone,
            "timestamp": ts,
            "type": message_type,
            message_type: {"id": f"{message_type}_dev", "caption": text_body, "mime_type": "application/octet-stream"},
        }
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": meta_phone_number_id},
                            "messages": [msg],
                        }
                    }
                ]
            }
        ],
    }


def _sign_body(body_bytes: bytes) -> dict[str, str]:
    secret = (os.environ.get("META_APP_SECRET") or "").strip()
    if not secret:
        return {}
    digest = hmac.new(secret.encode("utf-8"), msg=body_bytes, digestmod=hashlib.sha256).hexdigest()
    return {"X-Hub-Signature-256": f"sha256={digest}"}


def main() -> int:
    """
    Sends a synthetic Meta inbound webhook to local WA gateway.

    Usage:
      python backend/tools/dev_send_inbound.py
      python backend/tools/dev_send_inbound.py --meta-phone-number-id <ID> --from <E164> --text "Hi"
    """
    args = sys.argv[1:]

    def _arg(flag: str, default: str) -> str:
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args) or args[i + 1].startswith("-"):
                raise SystemExit(f"Missing value after {flag}")
            return args[i + 1]
        return default

    pid = _arg("--meta-phone-number-id", (os.environ.get("DEV_META_PHONE_NUMBER_ID") or "1098044196727032").strip())
    from_phone = _arg("--from", "+919876543210")
    text_body = _arg("--text", f"Gate 2 E2E test {int(time.time())}")
    message_type = _arg("--type", "text")
    print(f"meta_phone_number_id={pid} from={from_phone} type={message_type} text={text_body!r}")

    msg_id = f"wamid.dev.{int(time.time() * 1000)}"
    payload = build_meta_inbound_webhook_payload(
        meta_phone_number_id=pid,
        from_phone=from_phone,
        text_body=text_body,
        message_type=message_type,
        msg_id=msg_id,
    )
    body_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = {"Content-Type": "application/json", **_sign_body(body_bytes)}

    with httpx.Client(timeout=10.0) as client:
        r = client.post(
            "http://127.0.0.1:8081/webhooks/meta/inbound",
            content=body_bytes,
            headers=headers,
        )
    print(f"HTTP {r.status_code}")
    print(f"Content-Type: {r.headers.get('content-type', '(none)')}")
    print(r.text or "(empty body)")
    if r.status_code >= 400:
        print("\nIf HTTP 500 with plain text: restart 8081 (Ctrl+C, start uvicorn again).")
        print("Then run: python backend\\tools\\gate1_probe.py")
        print("Or check 8081 terminal for Traceback.")
    r.raise_for_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
