# ZY Smart Serv (v6.1)

Backend services (FastAPI) for WhatsApp Gateway, AI engine, Client API, Billing, Dashboards, SOPs.

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

## Non-dev / staging smoke checklist (10 steps)

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
- `GET  /inbox/chats?state=&assigned=me|unassigned|<user_id>&q=&limit=` — list
- `GET  /inbox/chats/{chat_id}` — detail (messages from `inbox_messages` UNION outbound `wa_outbox` rows; plus `pending_outbound` for transparency)
- `POST /inbox/chats/{chat_id}/assign` — `{ user_id, reason?, note? }` (owner / super_admin)
- `POST /inbox/chats/{chat_id}/reassign` — same body; ends any ACTIVE assignment first
- `POST /inbox/chats/{chat_id}/unassign` — `{ reason? }` (agent may only unassign their own chat)
- `POST /inbox/chats/{chat_id}/escalate` — `{ to_user_id?, reason? }` (assigns when `to_user_id` set, else sets state=`PENDING_AGENT`)
- `POST /inbox/chats/{chat_id}/typing` — `{ state: "typing"|"stopped", ttl_seconds?: 5 }`
- `POST /inbox/chats/{chat_id}/reply` — `{ text }` (owner/agent/super_admin; agents must own the chat)

WebSocket: `ws://127.0.0.1:8085/ws?token=<JWT>` (super_admin must also pass `&client_id=`). Server pushes:

```
{ "event": "hello" | "message_new" | "assignment_changed" | "typing" | "chat_state_changed", "data": {...}, "ts": "<iso>" }
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

## Billing (M5)

**App:** `backend/apps/billing_api/main.py` — run on **port 8086** (see HANDOFF *Billing (M5 layout)*). Webhook endpoints:

- `POST http://127.0.0.1:8086/webhooks/razorpay` — header `X-Razorpay-Signature` (hex HMAC-SHA256 of the raw JSON body using `BILLING_RAZORPAY_WEBHOOK_SECRET`).
- `POST http://127.0.0.1:8086/webhooks/paddle` — header `Paddle-Signature` (`ts=...;h1=...` per Paddle Billing notification signing, secret `BILLING_PADDLE_WEBHOOK_SECRET`).

**Prereq:** migrate DB (`0004_billing`), set webhook secrets in `backend/.env` or `$env:` (see `backend/.env.example`). Subscription payloads must carry your `api_clients.id` as a UUID string: Razorpay `payload.payload.subscription.entity.notes.client_id`; Paddle `data.custom_data.client_id`. Replaying the same provider event id returns `{"status":"duplicate"}` (no double update).

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

Cross-platform shell for **client_api**: `POST /auth/login`, `GET /auth/me`, owner/agent **inbox** (`GET /inbox/chats`, `GET /inbox/chats/{id}`, assign/reply/typing), **WebSocket** `ws://<host>:<port>/ws?token=<JWT>`, and a **super_admin** control-plane placeholder (static copy until a real admin API exists).

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

On the **Android emulator**, the host loopback is `10.0.2.2`, so point the client at `http://10.0.2.2:8085` (dart-define or in-app **API base URL**).

**Run — Windows desktop:**

```powershell
cd flutter_app
flutter run -d windows --dart-define=CLIENT_API_BASE_URL=http://127.0.0.1:8085
```

**Run — Android emulator** (list devices, then pick the emulator id):

```powershell
cd flutter_app
flutter devices
flutter run -d emulator-5554 --dart-define=CLIENT_API_BASE_URL=http://10.0.2.2:8085
```

More detail: `flutter_app/README.md`.

