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

## What is already implemented (this repo)

- FastAPI **WA Gateway** (`backend/apps/wa_gateway/`): Meta verify, inbound store-first + dedupe `meta_msg_id`, routing by `phone_number_id` → `wa_numbers`, debounce batch rows, status webhook → `wa_status_events` / `wa_outbox` update.
- **AI Engine stub** (`backend/apps/ai_engine/`): `POST /ai/respond`.
- **Billing (M5)** (`backend/apps/billing_api/`): Alembic `0004_billing` (`bill_plans`, `bill_subscriptions`, `bill_events` with unique `(provider, provider_event_id)`); signed webhooks `POST /webhooks/razorpay` and `POST /webhooks/paddle` (default local **port 8086**); updates `api_clients.billing_provider`, `entitlement_plan`, `billing_plan_code` + upserts `bill_subscriptions`. Linking: Razorpay `payload.payload.subscription.entity.notes.client_id` (UUID string); Paddle `data.custom_data.client_id`. Optional `bill_plans` rows map provider price/plan ids → `plan_code` / `entitlement_plan` via notes `entitlement_plan` / `entitlement`.
- **Workers**: `batch_processor.py` (seal batch → call AI → enqueue `wa_outbox`), `outbox_sender.py` (Meta send when `META_ACCESS_TOKEN` set).
- **client_api (M3/M4)** (`backend/apps/client_api/`): JWT login, owner/agent/super_admin RBAC, inbox list/detail, assign/reassign/unassign/escalate, typing presence, agent reply (mirrors `inbox_messages` + enqueues `wa_outbox` `AGENT_REPLY`), `/ws` WebSocket emitting `message_new`, `assignment_changed`, `typing`, `chat_state_changed`. Cross-process events (gateway/batch_processor → WS) are fanned out by an in-process `DBPoller` over `inbox_messages`, `wa_outbox`, and `chat_assignments`. New env: `CLIENT_API_JWT_SECRET`, `CLIENT_API_JWT_TTL_MINUTES`, `CLIENT_API_EVENT_POLL_MS`, `CLIENT_API_CORS_ORIGINS`.
- **Alembic**: `0001_init_core`, `0002_reliability_queueing`, `0003_wa_trial_map`, `0004_billing`; `backend/alembic.ini` uses `%(here)s/migrations`. No migration needed for client_api — schema already has `api_users`, `chat_assignments`, `chat_presence`.
- **Dev helpers**: `backend/tools/dev_seed.py`, `dev_send_inbound.py`, `dev_check.py`, `dev_seed_users.py` (owner/agent), `dev_inbox_smoke.py` (drives the assign flow + watches WS without Flutter).
- **Tests**: `tests/` — `pytest` for `meta_payload` / `status_payload` extractors, dev inbound JSON contract; optional live gateway POST when `RUN_WA_GATEWAY_E2E=1` (see `tests/test_gateway_e2e_optional.py` and README).
- **README**: local smoke steps, **10-step non-dev / staging smoke checklist**, automated test command.

## Known gaps / next work (pick one module per chat)

1. **M2 Gateway**: `wa_trial_map`; tighten SQL casts in gateway (`::uuid` vs SQLAlchemy binds); optional `X-ZY-Client-Id` removal once trial map exists.
2. **M1 AI**: Replace stub with Llama + quality gate + GPT-4 judge/fallback; `NEEDS_OWNER_DATA` + fixed customer string; urgent bypass. **`ops_runtime_config` (read by `/ai/respond`):** `ai.urgent_bypass_substrings` (JSON array of substrings → urgent REPLY path) and `ai.needs_owner_data_customer_reply` (optional string override for the fixed NEEDS_OWNER_DATA customer line). When the batch processor handles `HANDOFF` action, it should set `inbox_chats.state='PENDING_AGENT'` and (ideally) `NOTIFY 'chat_events'` so `client_api` can emit `chat_state_changed` without polling.
3. **M4 Inbox**: ~~assignment/reassignment APIs + WS events; agent reply path → outbox `AGENT_REPLY`~~ — **landed (client_api).** Follow-ups: swap `DBPoller` for Postgres `LISTEN/NOTIFY`; per-chat pagination cursors; idempotency-key header for `POST /inbox/chats/{id}/reply` (today the key is derived from generated `inbox_messages.id`, so retries from the client create a second logical message).
4. **M5 Billing**: ~~core tables + webhooks~~ **landed** (`0004_billing`, `billing_api`). Follow-ups: checkout/session creation APIs; populate `bill_plans` for your Razorpay `plan_id` / Paddle price ids; Paddle `transaction.*` handling; Razorpay non-subscription payment events if needed.
5. **Flutter**: `flutter_app/` — login, owner/agent inbox shell (REST + `/ws`), super_admin control-plane placeholder; README **Flutter** + `flutter_app/README.md`.
6. **M10 Release**: staging DB + automated smoke script + checklist. *(Minimal pytest + README/HANDOFF smoke checklist landed; extend with testcontainers or CI job as needed.)*

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

# client_api (M3/M4): inbox + assignments + WS
$env:CLIENT_API_JWT_SECRET="$(python -c "import secrets; print(secrets.token_urlsafe(48))")"
python -m uvicorn backend.apps.client_api.main:app --reload --port 8085

# billing_api (M5): Razorpay + Paddle webhooks (requires secrets from provider dashboards)
$env:BILLING_RAZORPAY_WEBHOOK_SECRET="<Razorpay webhook signing secret>"
$env:BILLING_PADDLE_WEBHOOK_SECRET="<Paddle notification destination secret>"
python -m uvicorn backend.apps.billing_api.main:app --reload --port 8086
```

Meta env (`.env` or `$env:`): `META_ACCESS_TOKEN`, `META_APP_SECRET`, `META_VERIFY_TOKEN`, `META_GRAPH_VERSION` (default v22.0). Billing env: `BILLING_RAZORPAY_WEBHOOK_SECRET`, `BILLING_PADDLE_WEBHOOK_SECRET` (see `backend/.env.example`).

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

| Chat role | Scope | Starts with |
|-----------|--------|-------------|
| **Stem** | Ordering, integration, release gates, conflicts | This file + git status |
| **M2** | Webhooks, routing, outbox, Meta | This file + `backend/apps/wa_gateway/` |
| **M1** | AI pipeline only | This file + `backend/apps/ai_engine/` |
| **M4** | Inbox, assignments, WS | This file + future `client_api` / inbox modules |
| **M5** | Billing | This file + `backend/migrations/versions/` + `backend/apps/billing_api/` |
| **Flutter** | UI only | This file + `flutter_app/` |

**Rule:** Each module chat pastes **this file** (or `@HANDOFF.md`) first, then only the files for that module. Stem merges when acceptance criteria met.

**First line for every new chat (so the agent loads context):**

```text
@HANDOFF.md Read this first, then follow the task below. Repo root: C:\Users\TV_Station\.cursor\projects\empty-window
```

(Use Cursor’s @ mention on `HANDOFF.md` in the repo root.)

## Paste blocks for new Cursor chats (copy each into its own chat)

Use **one block per chat**. Always start with the **First line** above, then paste the block.

### Chat A — Stem (integration + sequencing)

```text
@HANDOFF.md Read this first. Repo root: C:\Users\TV_Station\.cursor\projects\empty-window

You are the stem chat. Do not implement large features yourself unless unblocking.

Tasks:
1) Reconcile HANDOFF.md with git reality (list what changed vs doc).
2) Define the next 3 vertical slices in order (each shippable + testable).
3) For each slice, write acceptance criteria and which module chat owns it.
4) After module chats finish, you integrate: migrations order, env vars, one end-to-end smoke checklist.

Constraints: Windows + Postgres + FastAPI; keep Flutter out of backend-only slices.
```

### Chat B — M2 WhatsApp Gateway (routing, trial, webhooks)

```text
@HANDOFF.md Read first. Then read and modify only:
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
@HANDOFF.md Read first. Then read and modify only:
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
@HANDOFF.md Read first. Then read and modify only:
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
@HANDOFF.md Read first. Implement billing in backend (new app or extend existing layout—pick one, document in HANDOFF).

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
@HANDOFF.md Read first. Create new FastAPI app OR extend repo layout—follow existing patterns.

Task:
1) JWT auth skeleton (owner/agent/super_admin).
2) Endpoints: inbox list/detail, assign/reassign/unassign/escalate, typing.
3) WebSocket /ws with events: message_new, assignment_changed, typing, chat_state_changed.

Acceptance:
- A small httpx script or documented Postman collection can drive assign flow without Flutter.

Do not implement full Flutter in this chat.
```

### Chat G — Flutter (client + super-admin shells)

```text
@HANDOFF.md Read first. Flutter app lives under flutter_app/ (package zy_smart_flutter).

Task:
1) Login + role-based navigation (owner vs super_admin).
2) Inbox screen consuming REST + WS from Chat F.
3) Super-admin “control plane” placeholder for ops_runtime_config.

Acceptance:
- Runs on Android + Windows desktop; document build commands.
- Backend base URL configurable for dev (client_api default http://127.0.0.1:8085; use dart-define CLIENT_API_BASE_URL).
```

### Chat H — Testing / staging gate (M10-lite)

```text
@HANDOFF.md Read first.

Task:
1) Add minimal pytest (or scripts) for meta_payload + status_payload parsing; optional gateway smoke.
2) Add a 10-step non-dev smoke checklist (README or under this doc).

Acceptance:
- One command runs the automated tests locally (document which).
```

**Status:** `python -m pytest tests/` from repo root (see README **Automated tests**). Optional live gateway: `RUN_WA_GATEWAY_E2E=1` + `ZY_E2E_META_PHONE_NUMBER_ID`. Full **10-step staging smoke** checklist: README section *Non-dev / staging smoke checklist (10 steps)*.

## Testing (quick reference)

| What | Command / location |
|------|---------------------|
| Unit + contract tests | From repo root: `python -m pytest tests/` |
| Optional HTTP → gateway | `RUN_WA_GATEWAY_E2E=1`, `ZY_E2E_META_PHONE_NUMBER_ID`, `tests/test_gateway_e2e_optional.py` (see README) |
| Non-dev smoke (10 steps) | README → *Non-dev / staging smoke checklist* |

## Meta / WhatsApp (current decision)

- **Dev:** Meta-provided **+1 test number** + `phone_number_id` + tokens — OK; do **not** use personal WhatsApp as the WABA number.
- **Production India:** ZY SIM pool; **Global:** BYON.

## Security

- Never commit `.env` or paste long-lived tokens in chat. Rotate if exposed.

## Last updated

- 2026-05-13 — **M5 billing**: Alembic `0004_billing` (`bill_plans`, `bill_subscriptions`, `bill_events`); FastAPI `billing_api` on port **8086** with signed `POST /webhooks/razorpay` and `POST /webhooks/paddle`; `BILLING_*` env keys in `backend/.env.example`; README billing curl/PowerShell; HANDOFF **Billing (M5 layout)** subsection.
- 2026-05-13 — **Flutter `flutter_app/`**: scaffold + client_api login/inbox/WS shell + super_admin stub; README Flutter section; Chat G block points at `flutter_app/`.
- 2026-05-13 — **M10-lite testing**: `tests/` pytest (meta/status extract, dev inbound contract, optional gateway e2e); README **10-step staging smoke** + automated test section; `backend/tools/__init__.py` for imports; `build_meta_inbound_webhook_payload` in `dev_send_inbound.py`.
- 2026-05-12 — multi-chat stem; added **Paste blocks for new Cursor chats** (Chats A–H).
- 2026-05-12 — M1: documented `ops_runtime_config` keys `ai.urgent_bypass_substrings` and `ai.needs_owner_data_customer_reply` in gap list.
- 2026-05-12 — **M3/M4 client_api landed**: JWT login, RBAC, inbox list/detail, assign/reassign/unassign/escalate, typing, agent reply (mirrors `inbox_messages` + outbox `AGENT_REPLY`), `/ws` with `message_new` / `assignment_changed` / `typing` / `chat_state_changed`. Cross-process events via in-process `DBPoller` over `inbox_messages` / `wa_outbox` / `chat_assignments`. New env keys; new dev tools `dev_seed_users.py` + `dev_inbox_smoke.py`.
