from __future__ import annotations

"""Manual integration smoke for ``ops_api`` (M9) against running servers + real Postgres.

Requires:
  - ``client_api`` on ``--client-api-base`` (default http://127.0.0.1:8085)
  - ``ops_api`` on ``--ops-api-base`` (default http://127.0.0.1:8087)
  - Same ``CLIENT_API_JWT_SECRET`` on both apps (ops reuses client_api JWT)
  - Alembic ``0006_ops_sops`` applied
  - A user with role ``super_admin`` in ``api_users`` (login via ``POST /auth/login``)

Example (PowerShell from repo root):

    $env:PYTHONPATH = "$PWD"
    python backend/tools/dev_ops_api_smoke.py --email admin@example.com --password 'YourSecret'

Create a super_admin (one-time) if needed — attach to an existing client id, or use NULL client_id
if your DB allows it for that column:

    python -c "from backend.apps.client_api.auth import hash_password; print(hash_password('Admin!2026'))"

Then INSERT into api_users with role super_admin (see HANDOFF seed flow).
"""

import argparse
import sys
import uuid

import httpx


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--client-api-base", default="http://127.0.0.1:8085")
    p.add_argument("--ops-api-base", default="http://127.0.0.1:8087")
    p.add_argument("--email", required=True, help="super_admin email for POST /auth/login")
    p.add_argument("--password", required=True)
    p.add_argument(
        "--client-id",
        default="",
        help="Optional api_clients.id UUID to send on POST .../run (must exist if set).",
    )
    args = p.parse_args()

    slug = f"smoke-{uuid.uuid4().hex[:12]}"
    headers: dict[str, str] = {}

    with httpx.Client(timeout=30.0) as http:
        r = http.post(
            f"{args.client_api_base.rstrip('/')}/auth/login",
            json={"email": args.email, "password": args.password},
        )
        if r.status_code != 200:
            print(f"login failed: {r.status_code} {r.text}", file=sys.stderr)
            return 1
        body = r.json()
        user = body.get("user") or {}
        if user.get("role") != "super_admin":
            print("user is not super_admin; ops_api will return 403.", file=sys.stderr)
            return 1
        token = body["access_token"]
        headers["Authorization"] = f"Bearer {token}"

        c = http.post(
            f"{args.ops_api_base.rstrip('/')}/ops/sops",
            headers=headers,
            json={
                "title": "Smoke SOP",
                "slug": slug,
                "category": "smoke",
                "status": "active",
                "body_markdown": "# Smoke\nHello.",
            },
        )
        if c.status_code != 201:
            print(f"POST /ops/sops failed: {c.status_code} {c.text}", file=sys.stderr)
            return 1
        sop_id = c.json()["id"]
        print(f"CREATED_SOP_ID={sop_id} SLUG={slug}")

        g = http.get(f"{args.ops_api_base.rstrip('/')}/ops/sops/{sop_id}", headers=headers)
        if g.status_code != 200:
            print(f"GET /ops/sops/{{id}} failed: {g.status_code} {g.text}", file=sys.stderr)
            return 1
        print(f"GET_OK version={g.json().get('current_version')}")

        u = http.put(
            f"{args.ops_api_base.rstrip('/')}/ops/sops/{sop_id}",
            headers=headers,
            json={
                "title": "Smoke SOP v2",
                "category": "smoke",
                "status": "archived",
                "body_markdown": "# Smoke\nUpdated.",
            },
        )
        if u.status_code != 200:
            print(f"PUT /ops/sops/{{id}} failed: {u.status_code} {u.text}", file=sys.stderr)
            return 1
        print(f"PUT_OK version={u.json().get('current_version')}")

        run_body: dict = {
            "context_json": {"source": "dev_ops_api_smoke"},
            "trigger_type": "manual",
        }
        cid = (args.client_id or "").strip()
        if cid:
            run_body["client_id"] = cid

        rr = http.post(
            f"{args.ops_api_base.rstrip('/')}/ops/sops/{sop_id}/run",
            headers=headers,
            json=run_body,
        )
        if rr.status_code != 201:
            print(f"POST /ops/sops/{{id}}/run failed: {rr.status_code} {rr.text}", file=sys.stderr)
            return 1
        run_id = rr.json()["id"]
        print(f"RUN_ID={run_id}")

        lr = http.get(f"{args.ops_api_base.rstrip('/')}/ops/runs", headers=headers, params={"sop_id": sop_id})
        if lr.status_code != 200:
            print(f"GET /ops/runs failed: {lr.status_code} {lr.text}", file=sys.stderr)
            return 1
        print(f"LIST_RUNS count={len(lr.json())}")

        gr = http.get(f"{args.ops_api_base.rstrip('/')}/ops/runs/{run_id}", headers=headers)
        if gr.status_code != 200:
            print(f"GET /ops/runs/{{id}} failed: {gr.status_code} {gr.text}", file=sys.stderr)
            return 1
        print("GET_RUN_OK", gr.json().get("context_json"))

    print("dev_ops_api_smoke: all steps ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
