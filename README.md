# ZY Smart Serv (v6.1)

Backend services (FastAPI) for WhatsApp Gateway, AI engine, Client API, Billing, Dashboards, SOPs.

**Blueprint implementation checklist (living task list):** [docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md](docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md)

## Local dev (Phase A/B)

1. Copy environment file.
   - `backend/.env.example` → `backend/.env`
2. Create a venv and install deps.
   - `pip install -r backend/requirements.txt`
3. Run migrations (requires `DATABASE_URL` env var set).
   - PowerShell example:
     - `$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"`
     - `alembic -c backend/alembic.ini upgrade head`
4. Run WA Gateway.
   - `uvicorn backend.apps.wa_gateway.main:app --reload --port 8081`

Health:
- `GET /health`
- `GET /ready`

## Automated tests (no database required)

From the **repository root** (with deps installed: `pip install -r backend/requirements.txt`):

```powershell
python -m pytest tests/
```

This runs unit tests for Meta inbound/status payload parsing and a contract test that the synthetic webhook body built by `backend/tools/dev_send_inbound.py` matches what `extract_inbound_messages` expects.

**Optional live gateway roundtrip** (Postgres migrated + `dev_seed` + gateway on port 8081):

```powershell
$env:RUN_WA_GATEWAY_E2E="1"
$env:ZY_E2E_META_PHONE_NUMBER_ID="<same numeric id used in dev_seed>"
python -m pytest tests/test_gateway_e2e_optional.py -v
```

Docker-based Postgres (`testcontainers`) is not wired in this repo yet; use the optional env vars above or the manual checklist below.

### Optional Postgres integration (Chat N — Chat K workers + schema sanity)

Requires **migrations at head** on the database pointed to by `DATABASE_URL`. Prefer a **local disposable** `zysmart` (or equivalent) rather than shared staging: the usage test **temporarily advances** `worker_usage_cursors` to the latest `inbox_messages` row, then **restores** the original cursor after cleanup.

**Credentials:** use the same `DATABASE_URL` that already works for `alembic upgrade head` (README examples often use `postgres` / `postgres`; your install may differ — `FATAL: password authentication failed` means fix the URL, not the tests).

`tests/conftest.py` **omits** this module from the default `python -m pytest tests/` collection unless both `RUN_POSTGRES_INTEGRATION=1` and `DATABASE_URL` are set, so CI and quick local runs do not pick up extra skipped tests.

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"
$env:RUN_POSTGRES_INTEGRATION = "1"
python -m pytest tests\test_postgres_integration_optional.py -v
```

Env: **`RUN_POSTGRES_INTEGRATION`** — set to `1` together with **`DATABASE_URL`** so `tests/conftest.py` collects `tests/test_postgres_integration_optional.py` (default off so CI stays pytest-only without a Postgres service).

## Copy-paste command reference (PowerShell, repo root)

Use **`C:\Users\TV_Station\.cursor\projects\empty-window`** (or your clone path) as the repo root. **Every** command below assumes you already ran:

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window
.\.venv\Scripts\Activate.ps1
```

### A) One-time (or when deps change)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
Copy-Item backend\.env.example .env
Copy-Item backend\.env.example backend\.env
notepad .env
```

Edit **`.env` at repo root** (apps load `env_file=".env"` relative to **current directory** = repo root when you use the commands below). Put at least `DATABASE_URL`, `META_VERIFY_TOKEN`, and any keys you need. Keep **`backend\.env.example`** in Git; **`backend\.env`** is optional if you maintain **root `.env`** only.

### B) Every new terminal session (before Python imports `backend.*`)

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"
```

Load DB from root `.env` **or** set explicitly:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"
```

### C) Migrations (needs Postgres + `DATABASE_URL`)

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"
python -m alembic -c backend\alembic.ini upgrade head
python -m alembic -c backend\alembic.ini current
```

### D) Automated tests (no DB for default suite)

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"
python -m pytest tests\
```

### E) Optional live gateway pytest (needs gateway running on 8081)

**Terminal 1 — leave running:**

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"
python -m uvicorn backend.apps.wa_gateway.main:app --reload --port 8081
```

**Terminal 2:**

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"
$env:RUN_WA_GATEWAY_E2E = "1"
$env:ZY_E2E_META_PHONE_NUMBER_ID = "PASTE_NUMERIC_META_PHONE_NUMBER_ID_FROM_DEV_SEED"
python -m pytest tests\test_gateway_e2e_optional.py -v
```

### F) HTTP health checks (no secrets in URL)

```powershell
Invoke-WebRequest http://127.0.0.1:8081/health -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8081/ready  -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8083/health -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8085/health -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8085/ready  -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8086/health -UseBasicParsing
Invoke-WebRequest http://127.0.0.1:8086/ready  -UseBasicParsing
```

### G) Seed + synthetic inbound + DB peek (gateway on 8081)

Replace `PASTE_META_PHONE_NUMBER_ID` with your real Cloud API **phone_number_id** (digits only string from Meta).

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"
python backend\tools\dev_seed.py --meta-phone-number-id "PASTE_META_PHONE_NUMBER_ID"
python backend\tools\dev_send_inbound.py --meta-phone-number-id "PASTE_META_PHONE_NUMBER_ID" --from +919999999999 --text "smoke"
python backend\tools\dev_check.py
```

### H) Meta webhook verify (optional — only if token matches root `.env`)

Replace `YOUR_META_VERIFY_TOKEN` with the **exact** value of `META_VERIFY_TOKEN` from **repo root** `.env`. Use **single quotes** around the whole URL.

```powershell
Invoke-WebRequest 'http://127.0.0.1:8081/webhooks/meta?hub.mode=subscribe&hub.verify_token=YOUR_META_VERIFY_TOKEN&hub.challenge=test' -UseBasicParsing
```

Expect status **200** and body **`test`**. Skip this if you are not registering the callback in Meta yet.

### I) Full stack dev processes (one terminal each; all need `PYTHONPATH` + `DATABASE_URL`)

**Gateway 8081**

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"
python -m uvicorn backend.apps.wa_gateway.main:app --reload --port 8081
```

**AI 8083**

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"
python -m uvicorn backend.apps.ai_engine.main:app --reload --port 8083
```

**Batch worker**

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"
$env:AI_ENGINE_URL = "http://127.0.0.1:8083"
python backend\workers\batch_processor.py
```

**Outbox sender** (optional until you send outbound; needs `META_ACCESS_TOKEN` for real Meta sends)

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"
python backend\workers\outbox_sender.py
```

**Usage + metrics workers (Chat K)** — after `alembic upgrade head`, keeps `bill_usage_daily` in sync with `inbox_messages` and refreshes rollup tables. Tunables: `USAGE_WORKER_*`, `METRICS_ROLLUP_*` (see `HANDOFF.md` *Usage & metrics workers*).

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"
python backend\workers\usage_increment_worker.py
```

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"
python backend\workers\metrics_rollup_worker.py
```

**client_api 8085**

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"
$env:CLIENT_API_JWT_SECRET = "$(python -c \"import secrets; print(secrets.token_urlsafe(48))\")"
python -m uvicorn backend.apps.client_api.main:app --reload --port 8085
```

**billing_api 8086** (set secrets to match README billing examples when testing webhooks)

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"
$env:BILLING_RAZORPAY_WEBHOOK_SECRET = "devsecret_replace_me"
$env:BILLING_PADDLE_WEBHOOK_SECRET     = "devpaddle_replace_me"
python -m uvicorn backend.apps.billing_api.main:app --reload --port 8086
```

### J) client_api smoke scripts (after G) — replace `PASTE_CLIENT_UUID`

Use the `client_id` UUID printed by `dev_seed.py` (or read from DB).

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH = "$PWD"
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"
python backend\tools\dev_seed_users.py --client-id "PASTE_CLIENT_UUID"
python backend\tools\dev_inbox_smoke.py --listen-seconds 6
```

### K) Map README “10-step smoke” to these blocks

| Step | Use block |
|------|-----------|
| 1 Infrastructure | Postgres up; set `$env:DATABASE_URL` or root `.env` |
| 2 Migrations | **C)** |
| 3 Gateway `/health` | **F)** first line |
| 4 Gateway `/ready` | **F)** second line |
| 5 Config | Edit root `.env` (`APP_ENV`, `META_*`, billing secrets) |
| 6 Meta verify GET | **H)** optional |
| 7 Inbound | **G)** (`dev_send_inbound`) |
| 8 Persistence | **G)** last line (`dev_check`) |
| 9 Workers | **I)** AI + batch (+ outbox if needed) |
| 10 client_api | **I)** client_api + **J)** |
| (Optional) Postgres integration pytest | README subsection *Optional Postgres integration* + same `DATABASE_URL` / `PYTHONPATH` as **C)** |
| (Optional) Flutter `dart analyze` + G/H device smoke | README *Flutter / Chat N — device smoke* |

## Non-dev / staging smoke checklist (10 steps)

For **ready-to-run PowerShell** (env vars + `PYTHONPATH` + block letters **A–K**), see **Copy-paste command reference** above; section **K)** maps these ten steps to those blocks.

Use this after a deploy or before a demo when you want a repeatable pass/fail sequence (not only developer laptops).

1. **Confirm infrastructure**: Postgres reachable; `DATABASE_URL` set in the runtime environment (password URL-encoded if needed); no plaintext secrets in shell history for shared machines.
2. **Migrations at head**: `alembic -c backend/alembic.ini upgrade head` (or your orchestrated equivalent) completes with no pending revisions.
3. **Gateway health**: `GET /health` on the WA gateway returns `200` with body `ok`.
4. **Database readiness**: `GET /ready` on the WA gateway returns `200` (confirms DB ping from the gateway process).
5. **App configuration**: `META_APP_SECRET` / `META_VERIFY_TOKEN` / `META_ACCESS_TOKEN` match the Meta app and environment (staging vs prod); `app_env` is not `dev` unless you intend dev-only headers.
6. **Webhook verify (Meta console)**: `GET /webhooks/meta?hub.mode=subscribe&hub.verify_token=<token>&hub.challenge=test` returns the challenge string when the token matches.
7. **Inbound path**: Send one real or sandbox inbound to the configured number **or** run `python backend/tools/dev_send_inbound.py --meta-phone-number-id <ID> --from +919999999999 --text "smoke"` against the gateway URL; expect HTTP `200` and `{"ok":true,"stored":...}`.
8. **Persistence check**: Run `python backend/tools/dev_check.py` (or SQL) and confirm a new `inbox_messages` row (and chat/batch activity) for that customer/meta message id.
9. **Downstream workers (if enabled)**: With AI engine and `batch_processor` running, wait for debounce window then confirm no unhandled errors in worker logs; if `outbox_sender` and Meta token are enabled, confirm outbound status path with a test send when safe.
10. **Client API slice (if in scope)**: `GET /ready`-style checks for `client_api`, login with a seeded owner, open inbox list for the client, and confirm the new chat appears after step 7.

### Optional extensions (same session; not numbered above)

- **Chat K workers:** start `usage_increment_worker` and/or `metrics_rollup_worker` (README block **I)**) and confirm `bill_usage_daily` / `metrics_*` update after inbound traffic, or run **Optional Postgres integration** pytest when `RUN_POSTGRES_INTEGRATION=1`.
- **ops_api (M9):** README *Client API* → **ops_api (M9) smoke** (`dev_seed_users.py --super-admin-email` + `dev_ops_api_smoke.py`).
- **Flutter (Chat G + Chat H):** run **`dart analyze`** and the **device smoke** checklist below on **Windows** and **Android** before merge when UI changed.

## Non-dev local smoke test (quick path)

Prereq: Postgres running locally with db `zysmart` and user/pass `postgres/postgres`.

1) Set DB env var (PowerShell):

- `$env:DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/zysmart"`

2) Run migrations:

- `alembic -c backend/alembic.ini upgrade head`

3) Seed a test client + WA number mapping (replace the ID with your Meta `phone_number_id`):

- `python backend/tools/dev_seed.py --meta-phone-number-id <META_PHONE_NUMBER_ID>`

4) Start services (3 terminals):

- WA gateway: `uvicorn backend.apps.wa_gateway.main:app --reload --port 8081`
- AI engine: `uvicorn backend.apps.ai_engine.main:app --reload --port 8083`
- Batch worker: `$env:AI_ENGINE_URL="http://127.0.0.1:8083"; python backend/workers/batch_processor.py`

5) Send a test inbound message:

- `python backend/tools/dev_send_inbound.py --meta-phone-number-id <META_PHONE_NUMBER_ID> --from +919999999999 --text "Hi"`

6) Wait ~5 seconds and check DB outputs:

- `python backend/tools/dev_check.py`

## Client API (M3/M4 inbox + assignments + WebSocket)

Auth: HS256 JWT (`Authorization: Bearer <token>`). Roles: `owner`, `agent`, `super_admin`.

Endpoints (base `http://127.0.0.1:8085`):
- `POST /auth/login` — `{ email, password }` → `{ access_token, expires_at, user }`
- `GET  /auth/me`
- `GET  /users?role=agent` — list users in the caller's client
- `GET  /inbox/chats?state=&human_queue=true&assigned=me|unassigned|<user_id>&q=&limit=` — list (`human_queue` = needs-human: `HUMAN_REQ` + `WAITING_OWNER_DATA`; legacy `state=PENDING_AGENT` is accepted as a filter alias for `HUMAN_REQ`)
- `GET  /inbox/chats/{chat_id}` — detail (includes `ai_paused_until`; messages from `inbox_messages` UNION outbound `wa_outbox` rows; plus `pending_outbound` for transparency)
- `POST /inbox/chats/{chat_id}/assign` — `{ user_id, reason?, note? }` (owner / super_admin)
- `POST /inbox/chats/{chat_id}/reassign` — same body; ends any ACTIVE assignment first
- `POST /inbox/chats/{chat_id}/unassign` — `{ reason? }` (agent may only unassign their own chat; sets state `HUMAN_REQ` when released)
- `POST /inbox/chats/{chat_id}/escalate` — `{ to_user_id?, reason? }` (assigns when `to_user_id` set, else sets state=`HUMAN_REQ`)
- `POST /inbox/chats/{chat_id}/resolve` — `{ reason? }` (owner / super_admin; sets `CLOSED`, ends ACTIVE assignment as `RESOLVED`)
- `POST /inbox/chats/{chat_id}/typing` — `{ state: "typing"|"stopped", ttl_seconds?: 5 }`
- `POST /inbox/chats/{chat_id}/reply` — `{ text }` (owner/agent/super_admin; agents must own the chat; extends `ai_paused_until` per `ops_runtime_config`)
- `GET  /inbox/notifications?unread_only=&limit=` — in-app notifications for the signed-in user
- `POST /inbox/notifications/{id}/read` — mark read (idempotent)

WebSocket: `ws://127.0.0.1:8085/ws?token=<JWT>` (super_admin must also pass `&client_id=`). In production use **WSS**, short-lived JWTs, and set **`CLIENT_API_WS_ALLOWED_ORIGINS`** to an explicit comma-separated allowlist (exact `Origin` match). Server pushes:

```
{ "event": "hello" | "message_new" | "assignment_changed" | "typing" | "chat_state_changed" | "notification", "data": {...}, "ts": "<iso>" }
```

Run it:

```powershell
$env:CLIENT_API_JWT_SECRET = "$(python -c \"import secrets; print(secrets.token_urlsafe(48))\")"
python -m uvicorn backend.apps.client_api.main:app --reload --port 8085
```

Smoke (after `dev_seed.py` + an inbound from `dev_send_inbound.py`):

```powershell
python backend/tools/dev_seed_users.py --client-id <CLIENT_ID>
python backend/tools/dev_inbox_smoke.py --listen-seconds 6
```

**ops_api (M9) smoke** — after `alembic upgrade head`, start **client_api** (8085) and **ops_api** (8087) with the same `CLIENT_API_JWT_SECRET`. Seed a `super_admin` on your dev client, then run the httpx script:

```powershell
python backend/tools/dev_seed_users.py --client-id <CLIENT_ID> --super-admin-email admin@example.com --super-admin-password Admin!2026
python backend/tools/dev_ops_api_smoke.py --email admin@example.com --password Admin!2026
```

## Billing (M5)

**App:** `backend/apps/billing_api/main.py` — run on **port 8086** (see HANDOFF *Billing (M5 layout)*). Webhook endpoints:

- `POST http://127.0.0.1:8086/webhooks/razorpay` — header `X-Razorpay-Signature` (hex HMAC-SHA256 of the raw JSON body using `BILLING_RAZORPAY_WEBHOOK_SECRET`).
- `POST http://127.0.0.1:8086/webhooks/paddle` — header `Paddle-Signature` (`ts=...;h1=...` per Paddle Billing notification signing, secret `BILLING_PADDLE_WEBHOOK_SECRET`).

**Prereq:** migrate DB through **`0009_billing_kyc_invoices`** (includes **`bill_invoices`** + **`api_clients`** KYC columns). Set webhook + API secrets in `backend/.env` or `$env:` (see `backend/.env.example`). Subscription payloads must carry your `api_clients.id` as a UUID string: Razorpay `payload.payload.subscription.entity.notes.client_id`; Paddle `data.custom_data.client_id`. Replaying the same provider event id returns `{"status":"duplicate"}` (no double update).

**REST (JWT from `client_api` login — same `CLIENT_API_JWT_SECRET`):**

- `GET http://127.0.0.1:8086/billing/subscription` — `Authorization: Bearer <token>`; optional `?client_id=` for `super_admin`.
- `GET http://127.0.0.1:8086/billing/invoices?limit=50`
- `POST http://127.0.0.1:8086/billing/razorpay/create-checkout` — JSON `{"amount_paise":10000,"currency":"INR","notes":{}}` (requires **`BILLING_RAZORPAY_KEY_ID`** / **`BILLING_RAZORPAY_KEY_SECRET`**).
- `POST http://127.0.0.1:8086/billing/paddle/create-checkout` — JSON `{"items":[{"price_id":"pri_...","quantity":1}],"custom_data":{}}` (requires **`BILLING_PADDLE_API_KEY`**; **`BILLING_PADDLE_ENVIRONMENT=sandbox`** or `production`).
- `POST http://127.0.0.1:8086/billing/kyc/india` — JSON `{"data":{"legal_name":"...","pan":"..."}}` (stores `kyc_india_json`); response **`200`** + `{"ok": true}`.

**`GET /dash/*` (Chat J)** remains read-only analytics on **client_api**; billing writes and subscription truth stay **billing_api + Postgres** (see `routes_dash.py` module docstring).

**Razorpay sandbox — compute signature and POST (PowerShell):**

```powershell
$env:PYTHONPATH = "$PWD"
$env:BILLING_RAZORPAY_WEBHOOK_SECRET = "devsecret_replace_me"
$clientId = "<paste api_clients.id from dev_seed>"
$body = '{"entity":"event","id":"evt_localtest_1","event":"subscription.activated","payload":{"subscription":{"entity":{"id":"sub_localtest_1","status":"active","plan_id":"plan_any","notes":{"client_id":"' + $clientId + '"},"current_end":null}}}}'
$sig = python -c "import hmac,hashlib,os,sys; b=sys.argv[1].encode(); print(hmac.new(os.environ['BILLING_RAZORPAY_WEBHOOK_SECRET'].encode(),b,hashlib.sha256).hexdigest())" $body
curl.exe -sS -X POST "http://127.0.0.1:8086/webhooks/razorpay" -H "Content-Type: application/json" -H "X-Razorpay-Signature: $sig" -d $body
```

Run the same `curl` line again to see `{"status":"duplicate"}`.

**Paddle sandbox — example header (replace body + secrets with a real Paddle test notification):**

```powershell
$env:BILLING_PADDLE_WEBHOOK_SECRET = "pdl_ntfset_..."
$body = '{"event_id":"evt_paddle_test_1","event_type":"subscription.updated","data":{"id":"sub_paddle_1","status":"active","custom_data":{"client_id":"<api_clients.id>"},"items":[{"price":{"id":"pri_123"}}],"current_billing_period":{"ends_at":"2099-01-01T00:00:00Z"}}}'
$ts = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
$utf8 = [System.Text.Encoding]::UTF8
$msg = $utf8.GetBytes("$ts`:") + $utf8.GetBytes($body)
$hmac = [System.Security.Cryptography.HMACSHA256]::new($utf8.GetBytes($env:BILLING_PADDLE_WEBHOOK_SECRET))
$h1 = -join ($hmac.ComputeHash($msg) | ForEach-Object { $_.ToString("x2") })
$hdr = "ts=$ts;h1=$h1"
curl.exe -sS -X POST "http://127.0.0.1:8086/webhooks/paddle" -H "Content-Type: application/json" -H "Paddle-Signature: $hdr" -d $body
```

**Populate `bill_plans` (optional)** so `plan_id` / Paddle price id map to `starter` \| `growth` \| `pro`:

```sql
INSERT INTO bill_plans (provider, external_plan_id, plan_code, display_name)
VALUES ('razorpay','plan_any','starter','Dev placeholder');
```

## Flutter (`flutter_app/`)

Cross-platform shell for **client_api**: `POST /auth/login`, `GET /auth/me`, owner/agent **inbox** (`GET /inbox/chats`, `GET /inbox/chats/{id}`, assign/reply/typing), **WebSocket** `ws://<host>:<port>/ws?token=<JWT>`, and **super_admin** **SOP / Runbook Center** against **`ops_api`** (same JWT as login).

**Super admin — SOP Center (Chat H)** (after **`ops_api`** on **8087** and migrations **`0006_ops_sops`**):

- Tabs: **SOPs** (library, detail + safe Markdown preview, editor with preview tab, versions/diff/restore), **Runs** (filters: `sop_id`, `client_id`, `trigger_type`, **UTC from/to dates**; server max **500** rows — narrow with dates), **Control** (read-only M8 checklist: backend prerequisites per panel), **Dash** (`GET /dash/admin/*`: KPI chips + bar charts + message rollup + raw JSON).
- **Auth errors**: **401** from `ops_api` → app **logs out** (session invalid). **403** → one clear message (**super_admin** required); **no retry loop**.
- **Markdown**: preview uses **CommonMark-only** extensions (raw HTML disabled in the widget). Full HTML-in-markdown sanitization remains a **Stem** topic if product needs it.
- **API bases**: app bar **link** icon — set **`CLIENT_API_BASE_URL`** (8085) and **`OPS_API_BASE_URL`** (8087). Persisted locally next to the existing client_api URL store.
- **Dart-define** (defaults: `http://127.0.0.1:8085` and `http://127.0.0.1:8087`):

```text
--dart-define=CLIENT_API_BASE_URL=http://127.0.0.1:8085 --dart-define=OPS_API_BASE_URL=http://127.0.0.1:8087
```

On **Android emulator**, use **`http://10.0.2.2:8085`** and **`http://10.0.2.2:8087`** for both bases.

**Version history** uses **`GET /ops/sops/{id}/versions`** (immutable bodies); **restore** opens the editor with old Markdown and saves a **new** version via **PUT** (per server contract).

**First time only** (materialize `android/` + `windows/` if missing):

```powershell
cd flutter_app
flutter create . --project-name zy_smart_flutter --org com.zysmart.serv --platforms=android,windows
flutter pub get
```

You need this step before `flutter run -d windows` or the Android build; otherwise Flutter reports **No Windows desktop project configured** (or missing `android/`). See `flutter_app/README.md` for details and git path notes.

**API base URL** defaults to `http://127.0.0.1:8085`. Override at build/run:

```text
--dart-define=CLIENT_API_BASE_URL=http://127.0.0.1:8085
```

**`OPS_API_BASE_URL`** defaults to `http://127.0.0.1:8087` (see super-admin SOP section above).

On the **Android emulator**, the host loopback is `10.0.2.2`, so point the client at `http://10.0.2.2:8085` (dart-define or in-app **API base URL**).

**Flutter Web (dev CORS)**: if the browser blocks calls to `127.0.0.1:8085` / `8087`, set server env to include your web origin, for example:

- `CLIENT_API_CORS_ORIGINS=http://localhost:5555` (match the **exact** origin Chrome shows for `flutter run -d chrome`, including port).
- `OPS_API_CORS_ORIGINS=http://localhost:5555`

Do **not** use `*` for credentialed browser calls with `Authorization: Bearer`. Production must list explicit HTTPS origins.

**`mobile/` parity**: mirror the same Chat H `lib/` tree and `SessionController` / `ClientApiRepository` / `home_shell` wiring from `flutter_app` into `zy_smart_client`; add `flutter_markdown` and `markdown` to `mobile/pubspec.yaml`, then `flutter pub get`.

**Run — Windows desktop:**

```powershell
cd flutter_app
flutter run -d windows --dart-define=CLIENT_API_BASE_URL=http://127.0.0.1:8085 --dart-define=OPS_API_BASE_URL=http://127.0.0.1:8087
```

**Run — Android emulator** (list devices, then pick the emulator id):

```powershell
cd flutter_app
flutter devices
flutter run -d emulator-5554 --dart-define=CLIENT_API_BASE_URL=http://10.0.2.2:8085 --dart-define=OPS_API_BASE_URL=http://10.0.2.2:8087
```

More detail: `flutter_app/README.md`.

### Flutter / Chat N — `dart analyze` and device smoke (Chat G + Chat H)

Run on a **developer machine** (not assumed to pass inside agent sandboxes). Repeat for **`flutter_app/`** and, when you ship `mobile/` parity, **`mobile/`** (`zy_smart_client`).

1. **`flutter pub get`** in the project directory you are validating.
2. **`dart analyze`** — exit code must be **0** (fix or file a Stem ticket before merge if CI adds an analyze gate).
3. **Windows desktop:** `flutter run -d windows` with `--dart-define=CLIENT_API_BASE_URL=...` and `--dart-define=OPS_API_BASE_URL=...` (see Flutter section above; super-admin flows need **8087**).
4. **Android emulator:** `flutter devices` then `flutter run -d <emulator>` using **`http://10.0.2.2:8085`** and **`http://10.0.2.2:8087`** for client_api and ops_api when the stack runs on the host loopback.
5. **Chat G (owner / agent):** login → inbox list/detail → filters / assign or thread actions as applicable → **Dashboard** tab → app bar **Refresh** (`bumpDashGeneration`) → confirm **`/dash/client/*`** JSON loads or documented **404** mock path.
6. **Chat H (`super_admin`):** login with a seeded **`super_admin`** → **SOPs:** create or open SOP → edit/save → **versions / diff / restore** smoke → **Runs:** start a run with sample `context_json` → list/detail → **Dash** tab: expand endpoints — charts + **Raw JSON**; `GET /dash/admin/*` loads or **401** logs out cleanly → **403** shows “needs **super_admin**” without a retry loop when testing a non–super-admin token on a second run (optional).

---

## Sequential follow-through (stem checklist)

Do these in order when hardening the stack after local smoke.

### 1) WhatsApp delivery (`outbox_sender`)

Prereqs: `META_ACCESS_TOKEN`, `META_GRAPH_VERSION`, `DATABASE_URL`, migrations applied, `wa_numbers.meta_phone_number_id` set for the sending line.

1. Start **WA gateway 8081**, **AI 8083**, **`batch_processor`** (`AI_ENGINE_URL`), then **`outbox_sender`** from repo root with `$env:PYTHONPATH="$PWD"`.
2. Create a **`PENDING`** row: synthetic inbound + worker, or **`POST /inbox/chats/{id}/reply`** (agent) so `wa_outbox` has **`AI_REPLY`** or **`AGENT_REPLY`** in **`PENDING`**.
3. Watch **`outbox_sender`** logs: success → row becomes **`SENT`** with **`meta_message_id`**; repeated fatal Meta errors → **`DEAD`** / **`FAILED`** with **`last_error_*`**.
4. Confirm delivery in **Meta** dashboard or the recipient device.
5. SQL spot-check:

```sql
SELECT id, kind, status, meta_message_id, last_error_code, attempt_count
FROM wa_outbox
ORDER BY created_at DESC
LIMIT 10;
```

Status webhooks from Meta update **`wa_status_events`** and **`wa_outbox`** via **`POST /webhooks/meta/status`** on the gateway.

### 2) Quality / reliability (partially implemented in repo)

| Item | Status |
|------|--------|
| **`HANDOFF` / `NEEDS_OWNER_DATA` in `batch_processor`** | Updates **`inbox_chats`** to **`HUMAN_REQ`** / **`WAITING_OWNER_DATA`**, sets **`handoff_reason`**, **`pg_notify('zy_chat_events', json)`**, and inserts **`inbox_notifications`** for owners (best-effort). |
| **LISTEN instead of poller** | **`client_api`** still uses **`DBPoller`** for **`inbox_messages` / `wa_outbox` / `chat_assignments` / `inbox_notifications`**. Watch NOTIFY with **`python backend/tools/dev_listen_chat_events.py`**. Replacing the poller with an in-process LISTEN bridge is a larger follow-up. |
| **Agent reply idempotency** | Optional HTTP header **`Idempotency-Key`**: 1–128 chars `[A-Za-z0-9_-]`. Same key + same user replays return the stored message + outbox id without duplicating sends. |

### 3) Flutter (`flutter_app/` and `mobile/`)

- **`flutter_app/`**: see **Flutter** section above (Windows + Android emulator **`10.0.2.2:8085`**).
- **`mobile/`**: same API base URL rules; run **`flutter pub get`** then **`flutter run -d windows`** or **`flutter run -d <emulator>`** from the **`mobile/`** directory (see `mobile/README.md` if present).

### 4) Release / CI

GitHub Actions **`.github/workflows/ci.yml`** (Ubuntu, Python **3.12**) runs **`python -m pytest tests/ -q`** with workspace **`PYTHONPATH`** on push/PR to **`main`** / **`master`**. No Postgres **service** job in CI yet.

**M10 / Chat M — documentation handoff (done in repo):** **`/ops/releases*`** product scope, **target CI** layout, **manual approval hooks** for sensitive paths, **Chat N** full smoke after **CI workflow topology** changes, **`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`** § M10 + **Meta** cross-rule, **`HANDOFF.md`** — all written for the next implementation pass. **Still not built:** release manager **APIs**, Postgres **service** / integration / contract / E2E **jobs** in **`ci.yml`**; GitHub **Environments** / **CODEOWNERS** are **process** until Stem configures the org.

**Planned (M10 / Chat M — implementation):** a **Postgres `services:`** job (**`alembic upgrade head`** + **`RUN_POSTGRES_INTEGRATION=1`**), additional **contract** jobs if split is needed for runtime, and an optional **`RUN_WA_GATEWAY_E2E=1`** job (secrets off by default on PRs from forks).

**Manual approval (process — configure in GitHub):** changes under **`backend/apps/ai_engine/`**, **`backend/apps/wa_gateway/`**, and **`backend/apps/billing_api/`** should be reviewed by a human before production promotion. Typical levers: **`production` Environment** with **required reviewers**, **`CODEOWNERS`**, and/or **branch protection**. Stem picks which apply to this org.

**After CI workflow topology changes** (new jobs, services, matrix): run the full **Non-dev / staging smoke checklist (10 steps)** in this README (plus documented optional gates — workers, **`dev_ops_api_smoke.py`**, Flutter **`dart analyze` + device smoke** when relevant). **Chat N** owns recording pass/fail for that PR (see **`HANDOFF.md`** **Stem note — Chat N** and **Chat M** paste block).