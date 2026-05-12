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
- **Workers**: `batch_processor.py` (seal batch → call AI → enqueue `wa_outbox`), `outbox_sender.py` (Meta send when `META_ACCESS_TOKEN` set).
- **Alembic**: `0001_init_core`, `0002_reliability_queueing`; `backend/alembic.ini` uses `%(here)s/migrations`.
- **Dev helpers**: `backend/tools/dev_seed.py`, `dev_send_inbound.py`, `dev_check.py`.
- **README**: local smoke steps.

## Known gaps / next work (pick one module per chat)

1. **M2 Gateway**: `wa_trial_map`; tighten SQL casts in gateway (`::uuid` vs SQLAlchemy binds); optional `X-ZY-Client-Id` removal once trial map exists.
2. **M1 AI**: Replace stub with Llama + quality gate + GPT-4 judge/fallback; `NEEDS_OWNER_DATA` + fixed customer string; urgent bypass.
3. **M4 Inbox**: assignment/reassignment APIs + WS events; agent reply path → outbox `AGENT_REPLY`.
4. **M5 Billing**: Razorpay + Paddle webhooks; `bill_plans` / `bill_subscriptions` tables if not fully migrated.
5. **Flutter**: client + super-admin shells; consume APIs above.
6. **M10 Release**: staging DB + automated smoke script + checklist.

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
```

Meta env (`.env` or `$env:`): `META_ACCESS_TOKEN`, `META_APP_SECRET`, `META_VERIFY_TOKEN`, `META_GRAPH_VERSION` (default v22.0).

## Multi-chat workflow

| Chat role | Scope | Starts with |
|-----------|--------|-------------|
| **Stem** | Ordering, integration, release gates, conflicts | This file + git status |
| **M2** | Webhooks, routing, outbox, Meta | This file + `backend/apps/wa_gateway/` |
| **M1** | AI pipeline only | This file + `backend/apps/ai_engine/` |
| **M4** | Inbox, assignments, WS | This file + future `client_api` / inbox modules |
| **M5** | Billing | This file + migrations + webhook routes |
| **Flutter** | UI only | API contract from stem or OpenAPI |

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
@HANDOFF.md Read first. Flutter project location TBD—if missing, scaffold under flutter_app/ or mobile/ at repo root.

Task:
1) Login + role-based navigation (owner vs super_admin).
2) Inbox screen consuming REST + WS from Chat F.
3) Super-admin “control plane” placeholder for ops_runtime_config.

Acceptance:
- Runs on Android + Windows desktop; document build commands.
- Backend base URL configurable for dev (e.g. http://127.0.0.1:8081).
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

## Meta / WhatsApp (current decision)

- **Dev:** Meta-provided **+1 test number** + `phone_number_id` + tokens — OK; do **not** use personal WhatsApp as the WABA number.
- **Production India:** ZY SIM pool; **Global:** BYON.

## Security

- Never commit `.env` or paste long-lived tokens in chat. Rotate if exposed.

## Last updated

- 2026-05-12 — multi-chat stem; added **Paste blocks for new Cursor chats** (Chats A–H).
