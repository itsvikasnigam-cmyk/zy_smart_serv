"""Print what is listening on 8081 and probe WA gateway health (no DB required).

Usage:
  cd ...\\empty-window; . .\\dev-env.ps1
  python backend/tools/check_port_8081.py
"""

from __future__ import annotations

import json
import subprocess
import sys

import httpx

URL = "http://127.0.0.1:8081"


def main() -> int:
    print("=== Port 8081 (Windows netstat) ===")
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            errors="replace",
        )
        hits = [ln for ln in out.splitlines() if ":8081" in ln.replace(" ", "")]
        if hits:
            for ln in hits[:12]:
                print(ln)
        else:
            print("(nothing listening on 8081)")
    except Exception as exc:
        print(f"netstat failed: {exc}")

    print(f"\n=== HTTP probe {URL} ===")
    try:
        r = httpx.get(f"{URL}/health", timeout=5.0)
        print(f"GET /health -> {r.status_code}")
        print(r.text[:500])
        try:
            body = r.json()
            if isinstance(body, dict):
                build = body.get("build")
                print(f"build field: {build!r} app_env={body.get('app_env')!r}")
                if build == "gate1-2026-05-15":
                    print("OK: NEW wa_gateway code is running.")
                elif body.get("service") == "wa_gateway":
                    print("WARN: wa_gateway but OLD build (restart 8081).")
        except json.JSONDecodeError:
            if r.text.strip() == "ok":
                print("WARN: plain 'ok' only = OLD wa_gateway still on 8081.")
                print("Run: .\\scripts\\start_wa_gateway.ps1")
            else:
                print("WARN: not JSON — may be a different app on 8081.")
    except httpx.ConnectError:
        print("ERROR: cannot connect — start wa_gateway on 8081 first.")
        return 1
    except Exception as exc:
        print(f"probe failed: {exc}")
        return 1

    try:
        o = httpx.get(f"{URL}/openapi.json", timeout=5.0).json()
        title = (o.get("info") or {}).get("title")
        paths = list((o.get("paths") or {}).keys())
        print(f"\nOpenAPI title: {title}")
        print(f"has /dev/gate1-status: {'/dev/gate1-status' in paths}")
        print(f"has /webhooks/meta/inbound: {'/webhooks/meta/inbound' in paths}")
    except Exception as exc:
        print(f"openapi.json: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
