"""Compare wa_gateway code on disk vs what is answering on :8081.

Usage:
  cd ...\\empty-window; . .\\dev-env.ps1
  python backend/tools/verify_gateway_disk_vs_http.py
"""

from __future__ import annotations

import httpx

from backend.apps.wa_gateway.main import GATEWAY_BUILD_ID, health


def main() -> int:
    disk = health()
    print("=== On disk (this repo) ===")
    print(f"GATEWAY_BUILD_ID={GATEWAY_BUILD_ID}")
    print(f"health()={disk!r}")

    print("\n=== On http://127.0.0.1:8081/health ===")
    try:
        r = httpx.get("http://127.0.0.1:8081/health", timeout=5.0)
        print(f"status={r.status_code} body={r.text!r}")
    except httpx.ConnectError:
        print("ERROR: nothing listening on 8081. Run .\\scripts\\start_wa_gateway.ps1")
        return 1

    if r.text.strip() == "ok":
        print("\nMISMATCH: port 8081 is OLD code (plain ok). Disk has new code.")
        print("Fix: close ALL uvicorn windows, run .\\scripts\\start_wa_gateway.ps1,")
        print("     confirm startup line: WA Gateway build=gate1-2026-05-15")
        return 1

    try:
        http_body = r.json()
    except Exception:
        print("\nMISMATCH: HTTP response is not JSON.")
        return 1

    if http_body.get("build") == GATEWAY_BUILD_ID:
        print("\nMATCH: 8081 is running this repo's gateway.")
        return 0

    print(f"\nMISMATCH: HTTP build={http_body.get('build')!r} disk={GATEWAY_BUILD_ID!r}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
