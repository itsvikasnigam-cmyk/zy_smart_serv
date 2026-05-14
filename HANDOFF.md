# ZY Smart Serv — multi-chat handoff (stem document)

Use this file at the start of **every** Cursor chat (stem or module). Update it when milestones complete.

## Repo & environment

| Item | Value |
|------|--------|
| Root | `C:\Users\TV_Station\.cursor\projects\empty-window` |
| Backend | `backend\` |
| Python venv | `.venv\` (create: `python -m venv .venv`) |
| `PYTHONPATH` | Set to repo root: `$env:PYTHONPATH="$PWD"` (PowerShell, from root) |
| DB | PostgreSQL DB name `zysmart`; URL in `$env:DATABASE_URL` (user sets password; URL-encode `@` in password as `%40`) |

## Product spec (source of truth)

- Business spec: your **v6.0** document (plans, journeys, M1–M7).
- Architecture refinements agreed in chat → **v6.1** (store-first inbound, debounce 3s/10s, outbox, Paddle+Razorpay, India pool + global BYON, dashboards, SOPs, gated releases).
- **Living implementation checklist** (blueprint vs repo, checkboxes, M9 interactive SOP UI, meta “remove when done”): [`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`](docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md).

## What is already implemented (this repo)

- FastAPI **WA Gateway** (`backend/apps/wa_gateway/`): Meta verify, inbound store-first + dedupe `meta_msg_id`, routing by `phone_number_id` → `wa_numbers`, debounce batch rows, status webhook → `wa_status_events` / `wa_outbox` update.
- **AI Engine** (`backend/apps/ai_engine/`): `POST /ai/respond` — deterministic routing (`REPLY` / `HANDOFF` / `NEEDS_OWNER_DATA`) + `ops_runtime_config` keys (`ai.urgent_bypass_substrings`, `ai.needs_owner_data_customer_reply`); external LLM layer still optional / future.
- **Billing (M5)** (`backend/apps/billing_api/`): Alembic `0004_billing` (`bill_plans`, `bill_subscriptions`, `bill_events` with unique `(provider, provider_event_id)`); signed webhooks `POST /webhooks/razorpay` and `POST /webhooks/paddle` (default local **port 8086**); updates `api_clients.billing_provider`, `entitlement_plan`, `billing_plan_code` + upserts `bill_subscriptions`. Linking: Razorpay `payload.payload.subscription.entity.notes.client_id` (UUID string); Paddle `data.custom_data.client_id`. Optional `bill_plans` rows map provider price/plan ids → `plan_code` / `entitlement_plan` via notes `entitlement_plan` / `entitlement`.
- **Workers**: `batch_processor.py` (seal batch → call AI → enqueue `wa_outbox` `AI_REPLY` on `REPLY`; on **`HANDOFF`** / **`NEEDS_OWNER_DATA`** sets `inbox_chats.state='PENDING_AGENT'` + `handoff_reason` + `pg_notify('zy_chat_events', json)` for subscribers). `outbox_sender.py` (Meta send when `META_ACCESS_TOKEN` set). **Chat K — usage + metrics**: Alembic `0005_usage_metrics` (`bill_usage_daily`, `metrics_daily_client`, `metrics_daily_agent`, `metrics_hourly_system`, `worker_usage_cursors`); `usage_increment_worker.py` (cursor over `inbox_messages` → daily counts + soft/hard threshold timestamps from `ops_runtime_config.usage.daily_inbound_limits`); `metrics_rollup_worker.py` (cron-style rollups). Does **not** modify `batch_processor` / `outbox_sender`.
- **client_api (M3/M4 + M8 phase-1 dashboards)** (`backend/apps/client_api/`): JWT login, owner/agent/super_admin RBAC, inbox list/detail, assign/reassign/unassign/escalate, typing presence, agent reply (mirrors `inbox_messages` + enqueues `wa_outbox` `AGENT_REPLY`), optional **`Idempotency-Key`** header on **`POST /inbox/chats/{id}/reply`** for safe client retries (`agent:{chat_id}:{user_id}:{key}`). **Read-only dashboards (Chat J)** under **`/dash/*`** — **`GET /dash/client/overview`**, **`/dash/client/agents`**, **`/dash/client/quality`** (`owner` / `agent` / `super_admin` with `?client_id=` for super_admin); **`GET /dash/admin/overview`**, **`/dash/admin/collections`**, **`/dash/admin/providers/razorpay`**, **`/dash/admin/providers/paddle`**, **`/dash/admin/ops/whatsapp`**, **`/dash/admin/geo`** (and checklist alias **`/dash/admin/admin/geo`**) — **`super_admin` only**. OpenAPI tag **`dash`**. Aggregates use `api_clients`, `inbox_chats`, `wa_numbers`, `wa_outbox`, `bill_*`, `metrics_*` where present; placeholders (e.g. MRR, latency) documented in response models. `/ws` WebSocket + in-process **`DBPoller`** over `inbox_messages`, `wa_outbox`, `chat_assignments`. Dev tool: **`python backend/tools/dev_listen_chat_events.py`** listens on **`zy_chat_events`** NOTIFY payloads. Env: `CLIENT_API_JWT_SECRET`, `CLIENT_API_JWT_TTL_MINUTES`, `CLIENT_API_EVENT_POLL_MS`, `CLIENT_API_CORS_ORIGINS`.
- **Flutter owner/agent (Chat G)** (`flutter_app/` + **`mobile/`**): **Owner/agent only** — inbox + WS + client **`/dash/client/*`**; **no** new super-admin SOP/control-plane (that is **Chat H**). **Nav:** `flutter_app` **Inbox · Dashboard · Account**; `mobile` **Inbox · Dashboard · Settings** (`HomeShell(initialTab)`: **0=Inbox, 1=Dashboard, 2=Settings**). **Login / session:** after **`GET /auth/me`**, unknown roles → clear token + error; **`SessionController.wsLastError`**; WS **try/catch**; disconnect clears WS error; role snackbars (owner/agent/super_admin); WS after login for tenant users; snackbar if WS fails but REST OK; password cleared on success. **Inbox:** filters (All / Mine / Unassigned / Needs agent), phone search, pull-to-refresh, retry, agent hint; **`mobile`**: **`canUseTenantInboxApi`**, **`superAdminClientId`** / **`superClientId`** on list API. **Thread:** assign / reassign / escalate / unassign (owner); assignment banner; **`mobile`** `_cid(session)` on inbox REST; typing/reply gated. **Dashboard:** **`ClientDashboardScreen`** → **`GET /dash/client/overview|agents|quality`**; **401** logout; **404** mock + banner; app bar **Refresh** → **`bumpDashGeneration()`**. **`mobile`** `ClientApiRepository` aligned (`listChats` params, reassign/unassign/escalate, **`dashGet`**). **Docs:** `flutter_app/README.md`, `mobile/README.md` Chat G + URL table. **Smoke:** Stem / Chat N on device.
- **ops_api (M9 SOP Center — Chat I)** (`backend/apps/ops_api/`): Dedicated FastAPI app (default local **port 8087**) for versioned Markdown SOPs and run logs. **Stem choice:** parallel app (not mounted under `client_api`). **Auth:** same HS256 secret as inbox — `Authorization: Bearer <JWT>` where the JWT is from **`POST /auth/login`** on `client_api` for **`super_admin` only** (other roles get 403). **DB (Alembic `0006_ops_sops`):** `ops_sops`, `ops_sop_versions` (immutable body per version), `ops_run_logs` (`context_json` JSONB, optional `client_id` FK to `api_clients`, `trigger_type` default `manual`). **REST (OpenAPI tag `ops`):** `GET/POST /ops/sops`, `GET/PUT /ops/sops/{sop_id}`, **`GET /ops/sops/{sop_id}/versions`** (version bodies for Chat H history/diff/restore), `POST /ops/sops/{sop_id}/run`, `GET /ops/runs` (filters: `client_id`, `sop_id`, `trigger_type`, `from_date`, `to_date`), `GET /ops/runs/{run_id}`. **Chat H JSON contract:** `POST /ops/sops` body `{ title, slug, category?, status?, body_markdown }` (slug `^[a-z0-9][a-z0-9_-]*$`); `PUT /ops/sops/{id}` body `{ title, category?, status, body_markdown }` (always appends next `ops_sop_versions` row); `POST .../run` body `{ context_json: object, trigger_type?: manual|auto|scheduled|other, client_id?: uuid }`; list/detail responses mirror `SopSummaryOut` / `SopDetailOut` / `RunOut` in `backend/apps/ops_api/models.py`. Env: `OPS_API_CORS_ORIGINS` (optional; default `*`), **`CLIENT_API_JWT_SECRET`** (required; shared with `client_api`).
- **Flutter (Chat H — SOP Runbook UI)** (`flutter_app/` + **`mobile/`** parity): Super-admin **`SuperAdminShell`** — tabs **SOPs** · **Runs** · **Control** (read-only M8 placeholders) · **Dash** (`GET /dash/admin/*` on **client_api**); dual bases **`CLIENT_API_BASE_URL`** / **`OPS_API_BASE_URL`** (`dart-define` or in-app link sheet, persisted); `lib/screens/sops/*` + auth helpers (`401` → logout, **`403`** → one-shot “needs **super_admin**”, no retry loop); CommonMark-only Markdown preview (`flutter_markdown` + `markdown`); Android emulator hosts **`10.0.2.2:8085`** / **`:8087`**. Root + per-app READMEs document **Flutter web dev CORS** (`CLIENT_API_CORS_ORIGINS` / `OPS_API_CORS_ORIGINS`, exact origin string).
- **Alembic**: `0001_init_core`, `0002_reliability_queueing`, `0003_wa_trial_map`, `0004_billing`, `0005_usage_metrics`, `0006_ops_sops`; `backend/alembic.ini` uses `%(here)s/migrations`. No migration needed for client_api — schema already has `api_users`, `chat_assignments`, `chat_presence`.
- **Dev helpers**: `backend/tools/dev_seed.py`, `dev_send_inbound.py`, `dev_check.py`, `dev_seed_users.py` (owner/agent), `dev_inbox_smoke.py` (drives the assign flow + watches WS without Flutter), **`dev_ops_api_smoke.py`** (httpx: `client_api` login → **`ops_api`** CRUD + run against live **8085/8087**; requires a **`super_admin`** user — not added by `dev_seed_users.py`; see stem note below).
- **Tests + CI**: `tests/` — `pytest` (payloads, billing signatures, AI contract, **ops_api** OpenAPI/RBAC + mocked DB handlers: `tests/test_ops_api_openapi_rbac.py`, `tests/test_ops_api_handlers_mocked_db.py`, **Chat K** helper tests `tests/test_usage_thresholds.py`, optional live gateway when `RUN_WA_GATEWAY_E2E=1`). GitHub Actions **`.github/workflows/ci.yml`** runs **`python -m pytest tests/`** on push/PR to **`main`** / **`master`**.
- **README**: **Copy-paste PowerShell command reference** (blocks A–K), **10-step staging smoke**, **Sequential follow-through** (WhatsApp delivery, quality notes, Flutter, CI), local dev paths.

## Stem sequencing — next module chats (2026-05-14)

**Single migration / shared-contract owner:** Chat **A** approves order before any overlapping Alembic or JWT/API contract edits land together.

| Order | Chat | Rationale |
|-------|------|-----------|
| 1 | **N** | Keep **`python -m pytest tests/`** green on every merge; extend smoke docs / contract tests as Stem points; no schema ownership. |
| 2 | **B** | **M2** inbound trial/entitlement + **outbound paywall** reads (`bill_usage_daily` + `ops_runtime_config.usage.daily_inbound_limits` — Chat **K** already writes); unblock “silent accept” / `PAYWALL` path before batch changes depend on it. |
| 3 | **C** | **Workers** batch/outbox: A5 pause, HANDOFF/NEEDS_OWNER_DATA alignment with blueprint state names, idempotent Meta sends — coordinate with **B** if enqueue policy and paywall interact. |
| 4 | **F** | **M3/M4** REST/WS gaps (resolve, `ai_paused_until`, WS hardening) — usually no migration conflict with B if B stays in `wa_gateway` + existing tables. |
| 5 | **E** | **M5** checkout/subscription read APIs — separate app; merge after or parallel with **F** if no shared migration (Stem resolves if both touch `api_clients`). |
| 6 | **D** | **M1** external LLM — keep **`POST /ai/respond`** contract stable; land after **C** if batch processor contract tests need to lock first. |
| 7 | **L** | **M6/M7** broadcast + alerts — needs stable outbox/metrics story (**K** tables exist); coordinate **I** for phase-2 SOP auto-trigger later. |
| 8 | **M** | **M10** release APIs + CI Postgres job — after pytest baseline is reliable (**N**). |

**Parallel (non-migration):** **Chat H** follow-ups (M8 interactive control plane, super-admin dashboard charts) and **Chat I** ops extensions — no Alembic unless Stem opens a new revision window.

**Device smoke (cannot run inside Cursor agent reliably):** **G** owner/agent + **H** super-admin on **Windows + Android** — **Stem / Chat N / you** on a dev machine: `flutter pub get`, `dart analyze`, then README / HANDOFF smoke paths (`dev_inbox_smoke.py`, optional `dev_ops_api_smoke.py` with a real **`super_admin`** user).

## Known gaps / next work (pick one module per chat)

1. **M2 Gateway**: ~~trial map + routing~~ **landed** (`0003_wa_trial_map`, dev-only `X-ZY-Client-Id`). Follow-ups: production hardening, seed scripts for trial rows at scale.
2. **M1 AI**: External **Llama / GPT** pipeline + quality gate; keep `/ai/respond` JSON contract stable for `batch_processor`. **`ops_runtime_config`** keys already read for urgent bypass + NEEDS_OWNER_DATA copy.
3. **M4 Inbox / client_api**: ~~REST + WS + agent reply~~ **landed**. Follow-ups: **in-process `LISTEN zy_chat_events`** (or bridge) to **reduce / replace `DBPoller`** latency; per-chat pagination cursors; WS auth hardening for prod.
4. **M5 Billing**: **landed** (`0004_billing`, `billing_api`). Follow-ups: checkout/session APIs; more webhook event types; operational dashboards.
5. **Flutter**: ~~`flutter_app/` + `mobile/` shells~~ **Chat G landed** (owner/agent inbox + WS + client **`/dash/client/*`**); **Chat H** super-admin SOP landed. Follow-ups: device smoke (Stem/Chat N), deep links, polish.
6. **M10 Release**: **Basic CI** (pytest only) in `.github/workflows/ci.yml`. Follow-ups: Postgres **service** job + optional `RUN_WA_GATEWAY_E2E`, staging DB, deploy checklist automation.
7. **M9 (post–Chat I — for Chat A)**: **Interactive SOP UI landed** in **`flutter_app/`** and **`mobile/`** (library/detail/editor/versions+diff+restore/runs vs **`ops_api`**; M8 read-only control plane; Chat J dash reader). **Stem follow-ups:** (a) add **`super_admin`** to dev seed path (today: manual DB row or one-off insert; `dev_ops_api_smoke.py` needs it); (b) optional **Postgres-backed** pytest or CI job for `ops_api` SQL paths; (c) reconcile external blueprint DDL names vs repo if v6.x differs; (d) **`GET /ops/runs` hard cap 500** — raise/paginate if product needs more; (e) ~~**`mobile/`** parity~~ **done** (synced with `flutter_app` Chat H tree; run `flutter pub get` + `dart analyze` + **Windows + Android** smoke locally); (f) phase-2 **auto-trigger** runs + day-1 SOP seed content per checklist.
8. **Chat K tests**: **`tests/test_usage_thresholds.py`** covers **`usage_metrics_common`** helpers (no DB). **Still open:** optional **integration** pytest (or CI job) for **`usage_increment_worker` / `metrics_rollup_worker`** SQL paths against Postgres — **Chat N** or **K** extension with Stem approval.

## Stem note — Chat I extras (Chat A analysis)

Work **beyond** the original Chat I paste block (document here so Stem sequences merges and assigns follow-ups):

| Item | Detail |
|------|--------|
| **`ops_sop_versions` table** | Checklist text named `ops_sops` + `ops_run_logs` only; implementation added **`ops_sop_versions`** for immutable Markdown per version (PUT always appends). If external blueprint DDL used a single-table design, align or document deviation. |
| **`backend/tools/dev_ops_api_smoke.py`** | Live **httpx** smoke: `POST /auth/login` on **client_api** → bearer calls on **ops_api** (create SOP, GET, PUT, POST run, list/get runs). **Does not create users** — needs an existing **`super_admin`** in `api_users`. |
| **Automated tests** | `tests/test_ops_api_openapi_rbac.py` (OpenAPI paths + 403 for owner/agent); `tests/test_ops_api_handlers_mocked_db.py` (mocked `engine`, no Postgres). **Verified green** on Windows / Python 3.13 (7 tests). |
| **Shared config** | `backend/shared/config.py`: **`ops_api_cors_origins`** (env **`OPS_API_CORS_ORIGINS`**); `backend/.env.example` updated. |
| **Not done (intentional)** | No **`super_admin`** in `dev_seed_users.py`; no Postgres service job in CI for `ops_api`; no README “10-step” line-item unless Stem adds it. |

**Suggested Stem actions:** extend `dev_seed_users.py` (or new tool) with optional `--super-admin-email`; add README one-liner for `dev_ops_api_smoke.py`; schedule Chat H against `http://127.0.0.1:8087` OpenAPI.

## Stem note — Chat H wrap-up (main stem / Chat A)

Use this block to sequence verification, checklist ticks, and any contract decisions.

| Topic | Status / note |
|------|----------------|
| **§ M9 interactive UI** (`flutter_app/`) | Shipped: SOP library (search, category, status), detail + **CommonMark-only** Markdown preview, create/edit (POST/PUT, client-side slug `^[a-z0-9][a-z0-9_-]*$`), **version list + line diff + restore-via-editor**, start run (`context_json`: key/value + raw JSON, validate before POST), run list (filters + **500-row** server cap UX + date filters) + run detail. |
| **§ M8 control plane (Flutter)** | **Read-only** cards only (“Stem: needs API”) — no invented POSTs to `ops_runtime_config`. |
| **§ Chat J (`/dash/admin/*`)** | **SuperAdminShell → Dash** tab: lazy-load JSON per endpoint; empty metrics OK; **`401`** on `client_api` → logout. |
| **`mobile/`** | **Parity with `flutter_app` Chat H** (same `lib/` additions, `SessionController` + `ClientApiRepository.dashGet`, `SuperAdminShell`, removed legacy **`SuperAdminOpsScreen`**). **`mobile/README.md`** updated (dual bases, CORS, run commands). |
| **Auth / errors** | Every **`ops_api`** call: `Authorization: Bearer <access_token>`. **`401`** → return to login; **`403`** → clear “needs **super_admin**” (no retry loop). Tokens not logged. |
| **Backend contract** | **Chat A (Stem) — confirmed:** `GET /ops/sops/{sop_id}/versions` is **canonical `ops_api`** (Chat **I**, not H). Chat H only consumes it. **No revert** and no duplicate contract. If the external blueprint PDF omits this path, add it there as an amendment. |
| **Smoke acceptance** | Intended path: **super_admin** login → create SOP → detail → edit/save → start run with sample `context_json` → list runs → open run detail on **Windows + Android**. **Not re-run inside Cursor agent shell** in the last pass — **Stem / Chat N / you on a dev machine** should run `flutter pub get`, `dart analyze`, and this smoke after pulling. |
| **Checklist** | `docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md` § M9 reflects shipped **Flutter + ops_api**; Stem owns ticking when merging. **Chat N** can add the same flow to automated smoke docs if desired. |

## How to run (minimal)

From repo root, venv activated:

```powershell
$env:PYTHONPATH="$PWD"
$env:DATABASE_URL="postgresql+psycopg://USER:PASSWORD@localhost:5432/zysmart"
python -m alembic -c backend\alembic.ini upgrade head
```

Seed (real Meta `phone_number_id` from Cloud API — **not** the literal placeholder string):

```powershell
python backend\tools\dev_seed.py --meta-phone-number-id "NUMERIC_ID_FROM_META"
```

Services:

```powershell
python -m uvicorn backend.apps.wa_gateway.main:app --reload --port 8081
python -m uvicorn backend.apps.ai_engine.main:app --reload --port 8083
$env:AI_ENGINE_URL="http://127.0.0.1:8083"
python backend\workers\batch_processor.py
python backend\workers\outbox_sender.py

# usage + metrics (Chat K): bill_usage_daily + rollups (optional alongside batch_processor)
python backend\workers\usage_increment_worker.py
python backend\workers\metrics_rollup_worker.py

# client_api (M3/M4): inbox + assignments + WS
$env:CLIENT_API_JWT_SECRET="$(python -c "import secrets; print(secrets.token_urlsafe(48))")"
python -m uvicorn backend.apps.client_api.main:app --reload --port 8085

# billing_api (M5): Razorpay + Paddle webhooks (requires secrets from provider dashboards)
$env:BILLING_RAZORPAY_WEBHOOK_SECRET="<Razorpay webhook signing secret>"
$env:BILLING_PADDLE_WEBHOOK_SECRET="<Paddle notification destination secret>"
python -m uvicorn backend.apps.billing_api.main:app --reload --port 8086

# ops_api (M9): SOP / Runbook — reuse same CLIENT_API_JWT_SECRET as client_api above
python -m uvicorn backend.apps.ops_api.main:app --reload --port 8087
```

Meta env (`.env` or `$env:`): `META_ACCESS_TOKEN`, `META_APP_SECRET`, `META_VERIFY_TOKEN`, `META_GRAPH_VERSION` (default v22.0). Billing env: `BILLING_RAZORPAY_WEBHOOK_SECRET`, `BILLING_PADDLE_WEBHOOK_SECRET` (see `backend/.env.example`). **ops_api** shares **`CLIENT_API_JWT_SECRET`** with client_api; optional **`OPS_API_CORS_ORIGINS`** (default `*`).

client_api smoke (drives the assign flow without Flutter):

```powershell
# 1) seed a client + wa_number once (prints CLIENT_ID)
python backend\tools\dev_seed.py --meta-phone-number-id "NUMERIC_ID_FROM_META"
# 2) seed an owner + agent user for that CLIENT_ID
python backend\tools\dev_seed_users.py --client-id <CLIENT_ID>
# 3) send a synthetic inbound to create a chat
python backend\tools\dev_send_inbound.py --meta-phone-number-id "NUMERIC_ID_FROM_META" --from +911234567890 --text "hello"
# 4) drive login → assign → typing → reply → reassign → unassign + watch /ws
python backend\tools\dev_inbox_smoke.py --listen-seconds 6
```

**ops_api smoke** (after `0006_ops_sops`, **client_api** + **ops_api** running, same `CLIENT_API_JWT_SECRET`, user must be **`super_admin`**):

```powershell
python backend\tools\dev_ops_api_smoke.py --email YOUR_SUPER_ADMIN_EMAIL --password YOUR_PASSWORD
# optional: --client-id <api_clients.uuid>  (must exist)
```

## Usage & metrics workers (Chat K — M2 paywall reads)

**Run** (after `alembic upgrade head`, same `$env:PYTHONPATH` / `$env:DATABASE_URL` as other workers):

```powershell
python backend\workers\usage_increment_worker.py
python backend\workers\metrics_rollup_worker.py
```

**Env (optional overrides)** — loaded via `backend.shared.config.Settings` / root `.env` (same pattern as other apps):

| Env var | Default | Purpose |
|---------|---------|---------|
| `USAGE_WORKER_BATCH_SIZE` | `500` | Max `inbox_messages` rows consumed per usage tick |
| `USAGE_WORKER_SLEEP_SECONDS` | `2` | Sleep between ticks when idle |
| `METRICS_ROLLUP_SLEEP_SECONDS` | `300` | Sleep between full rollup cycles |
| `METRICS_ROLLUP_LOOKBACK_DAYS` | `3` | UTC calendar days recomputed each cycle (`metrics_daily_*`) |
| `METRICS_ROLLUP_HOURLY_LOOKBACK` | `48` | Recent UTC hour buckets refreshed in `metrics_hourly_system` |

**M2 gateway (Chat B) — how to read usage (no Python import from workers):**

1. **Per-client inbound today (UTC calendar day)** — join `api_clients` to today’s `bill_usage_daily` row (created/updated by `usage_increment_worker`):

```sql
SELECT
  c.id AS client_id,
  c.entitlement_plan,
  COALESCE(u.inbound_customer_messages, 0) AS inbound_customer_messages_today_utc,
  u.soft_threshold_crossed_at,
  u.hard_threshold_crossed_at
FROM api_clients c
LEFT JOIN bill_usage_daily u
  ON u.client_id = c.id
 AND u.usage_date = (timezone('utc', now()))::date
WHERE c.id = :client_id;
```

2. **Limits** — read JSON from `ops_runtime_config` where `key = 'usage.daily_inbound_limits'`. Object keys match `api_clients.entitlement_plan` (`trial`, `starter`, `growth`, `pro`, `churned`). Each plan has integer `soft_warn` and `hard_block` thresholds on **inbound customer messages** for that UTC day. Optional fallback key `_default` if a plan is missing.

3. **Paywall suggestion (Stem / Chat B):** if `inbound_customer_messages_today_utc >= hard_block` (from the JSON for that plan), treat as **hard usage block** for AI enqueue / normal accept (future: `PAYWALL` outbox or template path). If only `>= soft_warn`, emit **owner warn** / dashboard signal only; `soft_threshold_crossed_at` / `hard_threshold_crossed_at` on `bill_usage_daily` record first crossing for auditing.

**Coordinate:** Chat **E** owns subscription truth on `api_clients`; Chat **B** adds gateway checks once Stem orders merge.

## Billing (M5 layout)

**Choice:** dedicated FastAPI app `backend/apps/billing_api/` (default **port 8086**), parallel to `client_api` (8085), so provider webhook signing and raw-body verification stay separate from Meta WA webhooks and JWT APIs.

**Webhook URLs** (no version prefix; configure these in Razorpay / Paddle dashboards for your deployed host):

| Provider | Method | Path |
|----------|--------|------|
| Razorpay | `POST` | `/webhooks/razorpay` |
| Paddle Billing | `POST` | `/webhooks/paddle` |

**Linking to `api_clients`:** Razorpay subscription payloads must include `notes.client_id` (UUID string). Paddle subscription payloads must include `custom_data.client_id`. Optional `bill_plans` rows map `external_plan_id` → `plan_code`; otherwise set `notes.entitlement_plan` / `custom_data.entitlement_plan` to `trial` \| `starter` \| `growth` \| `pro` \| `churned` when needed.

**Idempotency:** `bill_events` unique `(provider, provider_event_id)`; duplicate deliveries return JSON `{"status":"duplicate"}` and do not re-apply `api_clients` updates.

**Manual / sandbox calls:** README section *Billing (M5)* — PowerShell + `curl.exe` examples with a small Python helper to compute `X-Razorpay-Signature`.

## Multi-chat workflow

| Chat | Role | Scope (primary paths) | Starts with |
|------|------|----------------------|-------------|
| **A — Stem** | Integration lead; sequencing; merge gates; **full control** | No large feature work unless unblocking; owns [`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`](docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md) check-offs when merging | This file + git status + checklist |
| **B** | M2 gateway | `backend/apps/wa_gateway/`, gateway migrations | This file + checklist § M2 |
| **C** | Workers (batch + outbox) | `backend/workers/batch_processor.py`, `outbox_sender.py`, worker config | This file + checklist § Workers (batch/outbox rows) |
| **D** | M1 AI | `backend/apps/ai_engine/` | This file + checklist § M1 |
| **E** | M5 billing | `backend/apps/billing_api/`, billing migrations | This file + checklist § M5 |
| **F** | M3/M4 client_api | `backend/apps/client_api/` (REST + WS) | This file + checklist § M3 + § M4 |
| **G** | Flutter **client** — **landed** | `flutter_app/` + `mobile/` owner/agent inbox + WS + **`/dash/client/*`**; no SOP/control-plane | This file + checklist § Chat G Flutter + § M8 client dashboard line |
| **H** | Flutter **super-admin** — **landed** | `flutter_app/` + `mobile/` SOP Runbook, read-only M8, admin dash; **device smoke** = Stem / Chat N / you | This file + checklist § M8 + § M9 |
| **I** | Backend **SOP Center** — **landed** | `backend/apps/ops_api/`, Alembic `0006_ops_sops`, `GET/POST /ops/sops`, `GET/PUT /ops/sops/{id}`, `POST /ops/sops/{id}/run`, `GET /ops/runs`, `GET /ops/runs/{run_id}` (super_admin JWT from `client_api`) | This file + checklist § M9 APIs |
| **J** | Backend **dashboard APIs** — **landed** | `backend/apps/client_api/routes_dash.py` (+ dash `models.py`); prefix `/dash` | This file + checklist § M8 APIs |
| **K** | Workers **usage + metrics** — **landed** | `0005_usage_metrics`, `usage_increment_worker.py`, `metrics_rollup_worker.py` | This file + checklist § Workers (usage/metrics) |
| **L** | M6 + M7 | Broadcast (templates), alerts/aggregates hooks | This file + checklist § M6 + § M7 |
| **M** | M10 release + CI | Release register/promote/rollback, CI expansion, test gates | This file + checklist § M10 + meta |
| **N** | QA / staging | Pytest, smoke checklists, staging verification | This file + `tests/` + README smoke |

**Rules**

1. **Chat A (Stem)** assigns order when migrations or shared contracts touch multiple chats; module chats do **not** merge conflicting schema changes without A’s sequencing.
2. Each module chat pastes **this file** (`@HANDOFF.md`) first, then **only** the paths in its paste block.
3. After a module chat finishes, **Stem** integrates: migration order, env vars, smoke, checklist `[x]` updates in [`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`](docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md).

**First line for every new chat (so the agent loads context):**

```text
@HANDOFF.md Read this first, then follow the task below. Repo root: C:\Users\TV_Station\.cursor\projects\empty-window
```

(Use Cursor’s @ mention on `HANDOFF.md` in the repo root.)

## Paste blocks for new Cursor chats (copy each into its own chat)

Use **one block per chat**. Always start with the **First line** above, then paste the block.

**Blueprint checklist:** [`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`](docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md) — Stem (Chat A) updates checkboxes when merging; module chats reference their section(s).

### Chat A — Stem (integration + sequencing — **full control**)

```text
@HANDOFF.md Read this first. Repo root: C:\Users\TV_Station\.cursor\projects\empty-window
@docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md Read the checklist; you keep it in sync when merging.

You are Chat A — the stem chat. You have full control of ordering, merge gates, and conflict resolution.

Do:
- Assign work to Chats B–F and G–N; resolve overlaps (e.g. Chat C vs Chat K on batch_processor — split: C = seal/AI/outbox behavior; K = new usage/metrics workers only unless you explicitly assign A5 to C).
- Reconcile HANDOFF.md + checklist with git reality after each merge.
- Define the next 1–3 vertical slices; acceptance criteria per slice; which chat owns each.
- Integrate after module chats: migration order, env vars, README/HANDOFF notes, smoke pass.

Do not (unless unblocking): large greenfield features; let the scoped chats implement.

Constraints: Windows + Postgres + FastAPI; $env:PYTHONPATH="$PWD" from repo root; do not commit `.env`.
```

### Chat B — M2 WhatsApp Gateway (routing, trial, webhooks)

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M2.
Then read and modify only:
- backend/apps/wa_gateway/main.py
- backend/apps/wa_gateway/meta_payload.py
- backend/apps/wa_gateway/status_payload.py
- backend/migrations/versions/ (new migration if needed)

Task:
1) Add wa_trial_map (and routing): inbound must resolve client_id from trial shared number OR wa_numbers for prod/BYON.
2) Remove or narrow dev-only X-ZY-Client-Id once routing works.
3) Audit all SQL text() for invalid :param::uuid patterns; use CAST(:param AS uuid) or bound UUIDs.
4) Ensure store-first + meta_msg_id dedupe unchanged.

Acceptance:
- Synthetic webhook routes without X-ZY-Client-Id for both trial and mapped prod number.
- Status webhook still updates wa_outbox + wa_status_events.

Give exact migration + code changes; list manual test commands using backend/tools/dev_send_inbound.py variants if needed.
```

### Chat C — Workers (batch + outbox reliability)

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § Workers (batch_processor, outbox_sender).
Then read and modify only:
- backend/workers/batch_processor.py
- backend/workers/outbox_sender.py
- backend/shared/config.py (only if new env keys)

Task:
1) Batch text must be scoped to the sealed batch window (opened_at..sealed_at), not “last 5 minutes”.
2) Outbox sender: robust Meta errors, max attempts → DEAD, idempotent sends.
3) Document required env: META_ACCESS_TOKEN, META_GRAPH_VERSION.

Acceptance:
- Rapid multi-message → single outbox row per batch_id.
- Kill worker mid-send → retry safe, no duplicate customer messages.

Give PowerShell commands to run workers + dev_check.py.
```

### Chat D — M1 AI Engine (replace stub)

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M1.
Then read and modify only:
- backend/apps/ai_engine/main.py
- (new) backend/apps/ai_engine/* helpers as needed

Task:
Implement POST /ai/respond contract: REPLY | HANDOFF | NEEDS_OWNER_DATA; fixed customer string for NEEDS_OWNER_DATA; urgent bypass list from ops_runtime_config; language field.

Acceptance:
- JSON schema stable for batch_processor.
- Add or extend tests for routing_intent + NEEDS_OWNER_DATA if pytest exists.

Do not touch wa_gateway unless the request/response contract must change—then document the contract change in HANDOFF.md.
```

### Chat E — M5 Billing (Razorpay India + Paddle global)

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M5.
Implement billing in backend (new app or extend existing layout—pick one, document in HANDOFF).

Task:
1) bill_plans / bill_subscriptions / bill_events (migrations + models).
2) Webhooks: /webhooks/razorpay and /webhooks/paddle (signature verify).
3) Map webhook → api_clients.entitlement_plan + billing_provider.

Acceptance:
- Idempotent webhook processing (provider_event_id unique).
- No secrets in code; backend/.env.example updated.

Give PowerShell or curl examples for sandbox webhook testing.
```

### Chat F — M3/M4 Client API + Inbox (REST + WS skeleton)

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M3 + § M4.
Create new FastAPI app OR extend repo layout—follow existing patterns.

Task:
1) JWT auth skeleton (owner/agent/super_admin).
2) Endpoints: inbox list/detail, assign/reassign/unassign/escalate, typing.
3) WebSocket /ws with events: message_new, assignment_changed, typing, chat_state_changed.

Acceptance:
- A small httpx script or documented Postman collection can drive assign flow without Flutter.

Do not implement full Flutter in this chat.
```

### Chat G — Flutter **client** *(landed — owner/agent; device smoke: Stem / Chat N / you)*

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M4 (inbox UX) + § M8 client dashboard.

Scope: flutter_app/ and mobile/ — **owner + agent only** (no super-admin heavy UI here).

Task:
1) Harden login + role nav for owner vs agent; inbox list/detail + WS (REST from client_api Chat F).
2) Client dashboard **shells** wired to Chat J APIs when ready (stub with mock data until `/dash/client/*` exists).
3) Document ANDROID_EMULATOR / Windows base URLs (e.g. CLIENT_API_BASE_URL).

Acceptance:
- Runs on Android + Windows desktop; README or flutter_app/README.md build/run commands updated.
- Coordinate with Chat A before adding deps that affect CI.

Do not: super-admin control plane or SOP editor — that is Chat H.
```

### Chat H — Flutter **super-admin** *(M9/M8 interactive landed — smoke on device: Stem / Chat N / you)*

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M8 (control plane) + § M9 (interactive SOP UI).

Scope: flutter_app/ (super-admin routes) — Android + Windows desktop targets.

Task:
1) Control plane: runtime config editor (validate keys, audit/revert UX; SOP REST is **`ops_api`** `GET/PUT /ops/sops*` — other ops keys TBD), pricing/debounce/urgent/fallback panels per checklist.
2) SOP Runbook Center: library, Markdown editor + preview, version history/diff, start run + run log viewer; deep links reserved for Chat L auto-trigger later.
3) Super-admin dashboards consuming Chat J `/dash/admin/*` when available.

Acceptance:
- Clear separation from Chat G (no owner/agent inbox logic mixed into super-admin root).
- Works against **`ops_api`** (`http://127.0.0.1:8087`) for SOP/run flows when configured; list TODOs for Stem for gaps.

Do not: wa_gateway or workers — backend stays in B/C/I/J/K.
```

**Status (2026-05-13):** **SOP Runbook** flows (library, detail+Markdown, editor, version history+diff+restore, start run, run list/detail) are implemented in **`flutter_app/`** against **`ops_api`**. Items **1** (full runtime config / pricing panels) and **3** (dashboards) in the paste block above remain **follow-ups** for Stem / future chats.

### Chat I — Backend **SOP Center** *(landed — extend only with Chat A)*

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M9 (Data & APIs).

Stem decision (documented in HANDOFF “What is implemented”): **dedicated FastAPI app** `backend/apps/ops_api/` (port **8087**), not routes under client_api.

Landed scope:
- Alembic `0006_ops_sops`: `ops_sops`, `ops_sop_versions`, `ops_run_logs` + indexes.
- REST + super_admin-only JWT (same secret as client_api `POST /auth/login`).
- Pytest: `tests/test_ops_api_openapi_rbac.py`, `tests/test_ops_api_handlers_mocked_db.py`.
- **Additional (stem doc):** `backend/tools/dev_ops_api_smoke.py` — live httpx smoke; see **Stem note — Chat I extras** in HANDOFF.

Extend with Chat A: new event types, SOP export, stricter trigger_type enums, or merging into a single gateway if ops ever needs owner/agent reads.
```

### Chat J — Backend **dashboard APIs** *(landed — extend only with Chat A)*

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M8 APIs.

Task:
Implement read APIs: GET /dash/client/overview|agents|quality and GET /dash/admin/overview|collections|providers/razorpay|providers/paddle|ops/whatsapp|admin/geo (phase 1 aggregates OK with placeholders where metrics tables missing).

Scope: Prefer new router module under client_api or parallel app — Stem picks; wire to DB views/tables as they exist; stub zeros until Chat K metrics job exists.

Acceptance:
- OpenAPI visible; super_admin vs owner scoping enforced; document in HANDOFF.

Coordinate: Chats G and H consume these endpoints.
```

### Chat K — Workers **usage gate + metrics rollup** *(landed 2026-05-13 — extend only with Chat A)*

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § Workers (bill_usage_daily, metrics_daily_*).

Task:
1) Migrations for bill_usage_daily, metrics_daily_client, metrics_daily_agent, metrics_hourly_system (if not present).
2) Worker process(es): usage increment + soft/hard thresholds; metrics rollup cron-style loop.
3) Do not change batch_processor/outbox_sender unless Stem assigns overlap (default: coordinate with Chat C — K adds new files only).

Acceptance:
- Document env vars + how M2 paywall will read usage (interface for future Chat B work).

Coordinate: Chat E billing; Chat B gateway paywall hooks — Stem orders merges.
```

### Chat L — **M6 broadcast + M7 alerts** (backend)

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M6 + § M7.

Task:
- M6: template-only broadcast pipeline; plan gating (trial/starter block); opt-in model — minimal vertical slice first.
- M7: alert hooks (e.g. outbox DEAD spike, webhook failures) — can start with logging + DB rows before paging.

Acceptance:
- Stem-approved scope document in HANDOFF “Known gaps” or checklist notes; no silent production sends.

Coordinate: Chat I for auto-opening SOP runs from alerts (phase 2).
```

### Chat M — **M10 release manager + CI expansion**

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M10 + checklist meta task (do not delete checklist until Stem says so).

Task:
- Internal APIs: register build + test hash, promote, rollback (admin-gated); audit fields.
- CI: Postgres service job, optional gateway E2E, artifact policy — incremental PRs.

Acceptance:
- Document promotion flow in README; Chat N runs full smoke after CI changes.

Coordinate: Chat A owns whether checklist file removal criteria are met.
```

### Chat N — **QA / staging gates**

```text
@HANDOFF.md Read first. tests/ + README (smoke, automated tests).

Task:
1) Extend pytest/contract tests as Stem requests per slice (debounce, urgent, billing, dash APIs).
2) Keep README **10-step staging smoke** accurate; optional RUN_WA_GATEWAY_E2E docs.

Acceptance:
- `python -m pytest tests/` passes locally; document any new env vars.

This chat does not own feature implementation — verification + tests + smoke lists only unless Stem assigns a small fix.
```

**Status:** `python -m pytest tests/` from repo root (see README **Automated tests**). Optional live gateway: `RUN_WA_GATEWAY_E2E=1` + `ZY_E2E_META_PHONE_NUMBER_ID`. Full **10-step staging smoke** checklist: README section *Non-dev / staging smoke checklist (10 steps)*.

## Testing (quick reference)

| What | Command / location |
|------|---------------------|
| Unit + contract tests | From repo root: `python -m pytest tests/` |
| **ops_api (M9)** | `python -m pytest tests/test_ops_api_openapi_rbac.py tests/test_ops_api_handlers_mocked_db.py -v` (mocked DB); live stack: `python backend/tools/dev_ops_api_smoke.py --email … --password …` |
| Optional HTTP → gateway | `RUN_WA_GATEWAY_E2E=1`, `ZY_E2E_META_PHONE_NUMBER_ID`, `tests/test_gateway_e2e_optional.py` (see README) |
| Non-dev smoke (10 steps) | README → *Non-dev / staging smoke checklist* |

## Meta / WhatsApp (current decision)

- **Dev:** Meta-provided **+1 test number** + `phone_number_id` + tokens — OK; do **not** use personal WhatsApp as the WABA number.
- **Production India:** ZY SIM pool; **Global:** BYON.

## Security

- Never commit `.env` or paste long-lived tokens in chat. Rotate if exposed.

## Next chat — paste this (after `@HANDOFF.md` first line)

```text
Repo state (2026-05-12): Local smoke steps 7–10 verified (gateway + AI + batch_processor + client_api + dev_inbox_smoke). WhatsApp **AI_REPLY** path confirmed when AI on 8083 + `AI_ENGINE_URL` set on batch_processor.

Recently landed in tree (commit if not yet on remote): `batch_processor` **HANDOFF / NEEDS_OWNER_DATA** → `inbox_chats` **PENDING_AGENT** + **`pg_notify('zy_chat_events', json)`**; **`POST /inbox/chats/{id}/reply`** optional **`Idempotency-Key`** header; **`backend/tools/dev_listen_chat_events.py`**; **README** “Sequential follow-through” + copy-paste blocks; **`.github/workflows/ci.yml`** (pytest).

Your mission: <one sentence — e.g. “Replace DBPoller with LISTEN bridge” OR “Meta outbox_sender E2E in staging” OR “Flutter polish on Android”>.

Constraints: Windows + Postgres + FastAPI; repo root `C:\Users\TV_Station\.cursor\projects\empty-window`; `$env:PYTHONPATH="$PWD"` for all Python; do not commit `.env`.
```

## Last updated

- 2026-05-14 — **Integrated landing commit (local `master`):** **`2b51db3`** — `feat: dashboards, ops_api SOP center, usage/metrics workers, Flutter G/H parity` (79 files). **`git push`** requires a remote: `git remote add origin <url>` then `git push -u origin master` (or your default branch name).
- 2026-05-14 — **Chat A (Stem) — sequencing + verification note**: New **`Stem sequencing — next module chats (2026-05-14)`** (order **N → B → C → F → E → D → L → M** + device smoke assignment); **Known gaps** item **8** (Chat **K**: helper pytest **landed** in `test_usage_thresholds.py`; **Postgres integration** for workers still optional). **Pytest (verified locally, same day):** from repo root with **`$env:PYTHONPATH="$PWD"`** — **`python -m pytest tests/`** → **72 passed**, **1 skipped** (optional gateway E2E), **1** Starlette `multipart` PendingDeprecationWarning — Windows / Python **3.13.12**. **Still run before push:** Flutter **`dart analyze`** + **G/H** device smoke on **Windows + Android**; `git push` if you use a remote.
- 2026-05-13 — **Chat G handoff (Stem)**: `HANDOFF` “What is implemented” **Flutter owner/agent (Chat G)** bullet; multi-chat row **G landed**; **Chat G** paste heading; **Known gaps** §5; **`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`** — parallel **§ M4/M8 client UI** row, new **§ Owner/agent Flutter UI (Chat G)** `[x]` block, § M8 **Client dashboard (Flutter)** line ticked for Chat G v1.
- 2026-05-13 — **Chat A (Stem) — `GET /ops/sops/{id}/versions` policy:** Confirmed **canonical Chat I**; Chat H wrap-up table row updated; checklist § M9 intro + Data & APIs (`POST …/run` line restored) + parallel **§ M9** row; **Chat H** paste heading = landed + device smoke note.
- 2026-05-13 — **Chat H HANDOFF for stem**: New section **Stem note — Chat H wrap-up (main stem / Chat A)** (M9/M8/Dash scope, `mobile/` parity done, auth/error rules, **`GET …/versions`** = **Stem-confirmed** Chat I contract, smoke = manual on device). **“What is implemented”** Flutter bullet refreshed (four tabs, CORS, both apps). **Known gaps** §7: **`mobile/`** parity marked **done**; stem still owns seed user, CI Postgres, runs pagination, phase-2 auto-trigger, day-1 SOP content.
- 2026-05-13 — **Chat H (M9 interactive SOP UI)**: `flutter_app` super_admin **SOP Runbook** — `SuperAdminShell`, `OPS_API_BASE_URL` + persisted URL sheet, `lib/screens/sops/*` (library, detail+Markdown, editor POST/PUT, versions+diff+restore, start run, run list/detail). **ops_api:** `GET /ops/sops/{sop_id}/versions` + `SopVersionOut`. Checklist § M9 interactive bullets updated `[x]` (except phase-2 auto-trigger + day-1 content + optional PDF).
- 2026-05-12 — **Chat I done** (stem bookkeeping): `docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md` parallel-ownership row **Chat I landed**; M9 intro text updated (**backend landed**, UI = Chat H). Implementation already logged on 2026-05-13 below.
- 2026-05-13 — **Chat I extras for Stem (HANDOFF)**: New section **Stem note — Chat I extras (Chat A analysis)** (`ops_sop_versions` vs checklist wording, `dev_ops_api_smoke.py`, pytest file names + Windows/py3.13 green run, `ops_api_cors_origins`, suggested Stem actions); **Known gaps** item **7** (M9 post–Chat I); **Dev helpers** + **Tests + CI** + **Testing** table + **ops_api smoke** PowerShell under client_api smoke; Chat I paste block points to stem note.
- 2026-05-13 — **Chat I (M9 Data & APIs)**: New FastAPI **`backend/apps/ops_api/`** (port **8087**); Alembic **`0006_ops_sops`** (`ops_sops`, `ops_sop_versions`, `ops_run_logs`); REST under **`/ops/*`** with **`super_admin`** JWT from `client_api`; `OPS_API_CORS_ORIGINS` + shared **`CLIENT_API_JWT_SECRET`** in `backend/.env.example`; pytest **`tests/test_ops_api_*.py`**; checklist § M9 **Data & APIs** marked done.
- 2026-05-12 — **Chat J done** (stem bookkeeping): `docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md` § M8 **APIs** marked `[x]`; parallel-ownership row **Chat J landed**; HANDOFF multi-chat table + **Chat J** paste heading marked landed. Implementation already noted on 2026-05-13 below.
- 2026-05-13 — **M8 dashboard read APIs (Chat J)** in `client_api`: `routes_dash.py` + response models; `GET /dash/client/*` and `GET /dash/admin/*` (see “What is implemented” for paths and RBAC).
- 2026-05-12 — **Chat K done** (stem bookkeeping): `docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md` — § Workers items for usage gate + metrics rollup marked `[x]`; parallel-ownership row shows **Chat K landed**. Paywall **enforcement** in M2/batch paths remains **Chat B / Chat C** (see checklist notes on those lines).
- 2026-05-12 — **Multi-chat model**: table A–N; Chat A stem **full control** + `@docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`; paste blocks **G–M** (Flutter split, SOP backend, dash APIs, usage/metrics workers, M6/M7, M10); **Chat N** = QA/smoke; B–F link to checklist sections.
- 2026-05-12 — **Stem wrap-up**: `batch_processor` HANDOFF/NEEDS_OWNER_DATA + **`pg_notify('zy_chat_events')`**; client_api **`Idempotency-Key`** on agent reply; **`dev_listen_chat_events.py`**; README **Sequential follow-through** + CI note; **`.github/workflows/ci.yml`**; HANDOFF gaps refreshed; **Next chat** paste block above.
- 2026-05-13 — **M5 billing**: Alembic `0004_billing` (`bill_plans`, `bill_subscriptions`, `bill_events`); FastAPI `billing_api` on port **8086** with signed `POST /webhooks/razorpay` and `POST /webhooks/paddle`; `BILLING_*` env keys in `backend/.env.example`; README billing curl/PowerShell; HANDOFF **Billing (M5 layout)** subsection.
- 2026-05-13 — **Chat K usage/metrics** (implementation): Alembic `0005_usage_metrics` + `usage_increment_worker.py` + `metrics_rollup_worker.py`; HANDOFF **Usage & metrics workers**; `backend/.env.example` + `Settings` knobs.
- 2026-05-13 — **Flutter `flutter_app/`**: scaffold + client_api login/inbox/WS shell + super_admin stub; README Flutter section; HANDOFF **Chat G / Chat H** paste blocks split client vs super-admin.
- 2026-05-13 — **M10-lite testing**: `tests/` pytest …; HANDOFF **Chat N** owns QA/smoke (replaces prior Chat H testing-only block).
- 2026-05-12 — multi-chat stem; added **Paste blocks for new Cursor chats** (Chats A–H).
- 2026-05-12 — M1: documented `ops_runtime_config` keys `ai.urgent_bypass_substrings` and `ai.needs_owner_data_customer_reply` in gap list.
- 2026-05-12 — **M3/M4 client_api landed**: JWT login, RBAC, inbox list/detail, assign/reassign/unassign/escalate, typing, agent reply (mirrors `inbox_messages` + outbox `AGENT_REPLY`), `/ws` with `message_new` / `assignment_changed` / `typing` / `chat_state_changed`. Cross-process events via in-process `DBPoller` over `inbox_messages` / `wa_outbox` / `chat_assignments`. New env keys; new dev tools `dev_seed_users.py` + `dev_inbox_smoke.py`.
