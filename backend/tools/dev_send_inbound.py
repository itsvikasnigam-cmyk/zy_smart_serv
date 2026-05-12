from __future__ import annotations

import json
import sys
import time

import httpx


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

    msg_id = f"wamid.DEV.{int(time.time())}"
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": pid},
                            "messages": [
                                {
                                    "id": msg_id,
                                    "from": from_phone,
                                    "timestamp": str(int(time.time())),
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

    with httpx.Client(timeout=10.0) as client:
        r = client.post("http://127.0.0.1:8081/webhooks/meta/inbound", json=payload)
        print(r.status_code, r.text)
        r.raise_for_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

