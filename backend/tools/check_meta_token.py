"""Check whether META_ACCESS_TOKEN can read the configured WhatsApp phone number.

Usage:
  cd ...\\empty-window; . .\\dev-env.ps1
  python backend\\tools\\check_meta_token.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from backend.shared.config import settings


PHONE_NUMBER_ID = "1098044196727032"


def main() -> int:
    token = (settings.meta_access_token or "").strip()
    print("META_ACCESS_TOKEN set:", bool(token), "length:", len(token))
    if not token:
        print("ERROR: META_ACCESS_TOKEN is empty in backend\\.env")
        return 1

    url = (
        f"https://graph.facebook.com/{settings.meta_graph_version}/{PHONE_NUMBER_ID}"
        "?fields=id,display_phone_number,verified_name"
    )
    try:
        r = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=20.0)
    except Exception as e:
        print("ERROR: request failed:", type(e).__name__, str(e))
        return 1

    print("HTTP", r.status_code)
    body = r.text[:2000]
    print(body)
    if r.status_code == 200:
        print("OK: token can access this WhatsApp phone number.")
        return 0
    if "Session has expired" in body or '"error_subcode":463' in body or "error_subcode\":463" in body:
        print("")
        print("DIAGNOSIS: token expired (OAuth code 190 / subcode 463).")
        print("Fix META_ACCESS_TOKEN in backend\\.env first — phone number cannot be verified until auth works.")
        return 1
    if r.status_code == 404:
        print("")
        print("DIAGNOSIS: phone_number_id may be wrong for this token/app.")
        print("Compare Meta Console phone_number_id with: python backend\\tools\\show_wa_routing.py")
        return 1
    print("")
    print("FAIL: Meta rejected the request. Refresh token / permissions, then re-run.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
