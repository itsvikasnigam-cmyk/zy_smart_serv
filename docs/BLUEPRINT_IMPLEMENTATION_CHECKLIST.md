# Blueprint implementation checklist (v6.0 / v6.1)

Living checklist vs the **Whatsapp Manager Blueprint** (product definition, architecture, DDL, API list, acceptance tests). Check items off as you ship; keep this file until the **meta task** at the end says otherwise.

**Related:** `HANDOFF.md` (stem context — start with **Stem compressed context** table for multi-chat session summary), `README.md` (runbooks + smoke).

## Parallel chat ownership (HANDOFF paste blocks)

| Checklist area | Owns implementation | Notes |
|----------------|--------------------|--------|
| § M2 gateway | **Chat B** — **slice landed** (paywall, trial/churned, urgent/adaptive, **`PAYWALL`** outbox, **`0007`** meta errors, header flag) | Chat **K** supplies **`bill_usage_daily`** + limits JSON; **follow-ups:** load/staging proof; **Chat C** second-line gate for stale **OPEN** batches (**landed** — Known gaps §1) |
| § Workers (batch/outbox) | **Chat C** | **Reliability + blueprint states landed** (A5 skip; `HUMAN_REQ` / `WAITING_OWNER_DATA` + owner notifications; **U2** strict urgent → **HANDOFF** / **HUMAN_REQ**; NEEDS_OWNER customer **`wa_outbox`** aligned with **`ai_engine`** copy; second-line paywall before **`/ai/respond`**). **Still open:** **DEAD** surfacing / spike alerts (**Chat L** **`ops_alert_events`**); owner UI / paging |
| § Workers (usage/metrics tables + jobs) | **Chat K** — **landed** (`0005_usage_metrics`, `usage_increment_worker.py`, `metrics_rollup_worker.py`, `usage_metrics_common.py`) | **Enforcing** paywall / blocking enqueue remains **Chat B** (M2) + **Chat C** (batch) per HANDOFF. **Tests:** `tests/test_usage_thresholds.py` (no-DB helpers); **Postgres harness** `tests/test_postgres_integration_optional.py` when `RUN_POSTGRES_INTEGRATION=1` + `DATABASE_URL` + migrations at head (default pytest omits via `conftest.py`). **CI Postgres service job** = **Chat M** / Stem. **Session (2026-05-17):** Chat K chat **closed** on this baseline — new rollup keys / schema = future Stem-gated PRs. |
| § M1 AI | **Chat D** — **slice landed** (`/ai/respond` contract; deterministic + optional **OpenAI-compatible LLM** gated by **`AI_LLM_API_KEY`** + **`ai.fallback.*`**; Hinglish `language`; local + judge **quality gate**; **golden** fixtures). **Follow-ups:** full input bundle; per-client budget/rate; optional OpenAPI snapshot tests (**Chat N**) |
| § M5 billing + KYC + checkout | **Chat E** — **slice landed + pytest-green** (webhooks + **`POST /billing/*` checkout**, **`GET /billing/subscription|invoices`**, **`POST /billing/kyc/india`**, **`0009`**, extended events, **gateway DB-only** gating) | **Not** full blueprint **§ M5** — **Still open** in checklist (KYC **verify**, control-plane **pricing** UX, disputes/chargebacks, **`/dash/admin/*`** billing aggregates = **Chat J** read-only); see HANDOFF **Stem note — Chat E** |
| § M3 + § M4 REST/WS | **Chat F** — **blueprint inbox slice landed** (`0008`, resolve, notifications, WS `notification` + prod WS env, Flutter parity) | **M3** signup/OTP/team/catalog **deferred** pending product (see checklist § M3) |
| § M4/M8 client UI | **Chat G** — **landed** (`flutter_app` + `mobile`: **tenant** owner/agent **`HomeShell`** — inbox, WS, **`GET /dash/client/*`**, blueprint filters + resolve). **`super_admin`** → **`SuperAdminShell`** (SOPs / Runs / Control / admin dash) = **Chat H** in the same tree | Checklist **§ Owner/agent Flutter (Chat G)** — **all `[x]`** (slice **complete**). **Device smoke** = **Stem / Chat N / you** (README + HANDOFF **Chat N**), not a row in § Chat G. **Richer tenant charts / `/dash/client/*` evolution** → **§ M8 — Phase-2 — `/dash/*` (Chat J)**; **deep links** → **Chat L** / Stem |
| § M8 control plane + § M9 UI | **Chat H** — **landed** (`flutter_app` / `mobile`: SOP library…runs, **Control** coordination copy, **`GET /dash/admin/*`** bar/stack/KPI charts + Raw JSON — **no** new backend) | **`ops_api`** + **`client_api` `/dash/admin/*`**; **M8** interactive editors **blocked** until admin write APIs; device **smoke** = you / Chat N |
| § M9 APIs + schema | **Chat I** — **v1 landed** (`backend/apps/ops_api/`, `0006_ops_sops`, `dev_ops_api_smoke.py`, `tests/test_ops_api_*.py`) | **`GET /ops/sops/{id}/versions`** canonical on **`ops_api`**. **§ M9 interactive UI** = **Chat H**. **Extensions (open):** checklist **§ M9 — Still open (ops_api)** — pagination, export, enums, auto-trigger — **Stem + Chat A** contract before merge. |
| § M8 dashboard REST | **Chat J** — **phase-1 landed** (`routes_dash.py`, dash models; **§ M8 — APIs (backend)**). **Phase-2:** checklist **§ M8 — Phase-2 — `/dash/*`** (placeholders → real aggregates; new routes / contract changes + RBAC in **HANDOFF** + § M8 APIs + **`tests/test_dash_*.py`**) | **M8 interactive control plane** UI = **Chat H**. **Overlap:** revenue / MRR-style **`/dash/admin/*`** tiles with **§ M5 — Still open** until billing SQL is defined (**Chat E** + **Stem**). |
| § M6 + § M7 | **Chat L** — **backend slice landed** (`0010_m6_m7_broadcast_alerts`, campaign worker, alert eval, **`ops_alert_events`**, billing failure sink) | **Still open:** product REST/UI for opt-in + campaigns, pager channels, ban/GPU/SLA hooks, **`/dash/admin`** alert tiles; **M9 phase-2** SOP auto-trigger with **Chat I** (see HANDOFF).
| § M10 + CI | **Chat M** | **Doc handoff (done):** scope, target CI, approval hooks, **Chat N** after CI topology changes, checklist § M10 + **Meta**, **HANDOFF**, **README §4**. **Engineering (open):** **`/ops/releases*`** APIs; Postgres **service** + integration/contract/E2E in **`ci.yml`**; org **Environments** / **CODEOWNERS** = process until Stem configures. |
| Tests + smoke | **Chat N** | Default **`pytest`** + README gates; optional Postgres / device smoke **documented** — **green optional runs** and **manual Flutter smoke** are **Stem / you** when relevant, not implied by “Chat N done” (see HANDOFF **Stem note — Chat N (scope vs evidence)**). |
| Ordering, merges, checklist `[x]` | **Chat A** | This chat |

---

## How to use

- Use `- [ ]` / `- [x]` in Markdown (or your editor’s task list).
- Prefer **one PR per section** (or smaller) so the list stays honest.
- When an item is **obsolete** (spec changed), edit the line instead of leaving a lie.

---

## M2 — WhatsApp gateway & outbound loop

- [x] Inbound: signature verify → parse → **single DB transaction** per blueprint (store-first, dedupe `meta_msg_id`) — verify edge cases under load.
- [x] **Never** call AI inside webhook handler (regression guard / comment / test).
- [x] Debounce: baseline **3s / 10s cap** driven by `ops_runtime_config` — audited in staging.
- [x] **Adaptive debounce** (`debounce.adaptive.enabled`, `debounce.adaptive.two_msgs_within_sec`): extend batch window when burst arrives (blueprint **A3**).
- [x] **Urgent path at gateway** (**U1**): skip debounce when urgent keyword/intent matched (or equivalent: seal immediately) — align with blueprint (**U2** routing intent).
- [x] Optional: `POST /webhooks/meta/errors` (Meta errors) if product needs it.
- [x] **Trial / entitlement gate** on inbound: expired trial → inbound gets **“service inactive”** (per SOP); no silent accept.
- [x] **Outbound paywall**: blocked client → `PAYWALL` (or policy) instead of normal AI/agent enqueue when limits/trial demand it.

---

## Workers & reliability

**Chat C goal (delivery + blueprint alignment):** **Delivery correctness** — idempotent sends, backoff, **DEAD**, crash-safe retries; **batch** behavior per blueprint **A5**; **HANDOFF** / **NEEDS_OWNER_DATA** / urgent **U2** outcomes vs today’s **`PENDING_AGENT` + `pg_notify`** — align **state names and side effects** with this checklist and `HANDOFF.md`; batch text scoped to the **sealed** window (**`opened_at`…`sealed_at`**), not loose rolling time windows. **Coordinate** with **Chat B** if enqueue vs paywall interacts; **do not** expand into **Chat K** worker files unless **Stem** assigns overlap.

- [x] **Batch processor (A5)**: if chat is **`AGENT_ACTIVE`** or **`ai_paused_until > now()`**, still seal batches but **do not** call AI / enqueue `AI_REPLY`.
- [x] **Batch processor — HANDOFF**: set **`HUMAN_REQ`**, **owner notifications** via `inbox_notifications` (best-effort), `pg_notify` payload uses blueprint state names.
- [x] **Batch processor — NEEDS_OWNER_DATA**: set **`WAITING_OWNER_DATA`**, owner notifications + customer **`wa_outbox`** **`AI_REPLY`** using **`ai.needs_owner_data_customer_reply`** / same fixed default as **`ai_engine`** (`NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED`).
- [x] **Urgent bypass outcome** (**U2** — batch path): **`intent`** / **`routing_intent`** **`urgent`** + **`REPLY`** from **`/ai/respond`** is normalized to **`HANDOFF`** (`urgent_time_sensitive_u2`) so the worker sets **`HUMAN_REQ`** + owner alerts — **no** generic urgent **`REPLY`** line to the customer. (**U1** skip-debounce remains **Chat B** gateway.)
- [x] **Batch processor (Chat C — reliability slice)**: inbound batch text scoped to **`opened_at`…`sealed_at`** (not a rolling “last N minutes” window); `AI_REPLY` outbox enqueue still **`ON CONFLICT (idempotency_key)`** per batch.
- [x] **Outbox sender (Chat C — reliability slice)**: lease-based **`SENDING`** claim; retry/backoff; **`DEAD`** after max attempts; Meta error split (retry vs fatal); **`SENT`** only from **`SENDING`** (success idempotency). **Still open:** owner/dashboard surfacing of **DEAD** rows (**§ M7** / alerts — Chat **L** or stem); **duplicate customer message** window if process dies after Meta **200** and before DB commit remains a known Graph limitation (mitigate with lease + fast commit).
- [x] **Worker: usage + plan gate** (`bill_usage_daily`, soft warn / hard block at thresholds) — **Chat K**: `usage_increment_worker.py` + `ops_runtime_config.usage.daily_inbound_limits`; **hard_block** inbound blocking + **`PAYWALL`** enqueue is **§ M2 / Chat B** (gateway skips **OPEN** batch); **Chat C** second-line **`PAYWALL`** + skip **`/ai/respond`** before seal completes AI path for **legacy OPEN** batches (entitlement / usage / trial) — **`batch_processor.py`**.
- [x] **Worker: metrics rollup** → `metrics_daily_client`, `metrics_daily_agent`, `metrics_hourly_system` (tables + jobs) — **Chat K**: `metrics_rollup_worker.py` + migration `0005_usage_metrics`.
- [x] **Optional:** Postgres-backed pytest for **Chat K** worker SQL paths (`usage_increment_worker`, `metrics_rollup_worker`) — harness `tests/test_postgres_integration_optional.py` when `RUN_POSTGRES_INTEGRATION=1` + `DATABASE_URL` + migrations at head (includes `metrics_hourly_system` bucket + public table checks); no-DB helpers in `tests/test_usage_thresholds.py`. **CI Postgres service job** for this suite remains **Chat M** / Stem (default CI stays pytest-only).

---

## M1 — AI engine

### Landed (Chat D — routing + optional LLM)

- [x] **`POST /ai/respond`** stable JSON for **`batch_processor`**: `action` ∈ `REPLY` \| `HANDOFF` \| `NEEDS_OWNER_DATA`; `reply_text`, `intent`, **`routing_intent`**, `confidence`, **`language`** (`en` \| `hi` \| **`hinglish`** \| `auto`), `handoff_reason`, `missing_fields`, `risk_reason` (Pydantic `extra="forbid"` on request/response). **Chat C coordination:** HANDOFF **M1 — `POST /ai/respond` contract** — any new required field needs worker + Stem approval. **Chat D:** M1 / LLM work stays under **`ai_engine/`**; **Chat C** owns **`batch_processor.py`** policy (U2, paywall second-line, NEEDS_OWNER outbox) without changing the **five-field** request JSON.
- [x] **NEEDS_OWNER_DATA:** fixed customer-visible string in code + optional override via **`ops_runtime_config`** **`ai.needs_owner_data_customer_reply`** (JSON string).
- [x] **Urgent bypass (AI path):** **`ai.urgent_bypass_substrings`** (JSON array) → **`REPLY`** / **`routing_intent`** **`urgent`** (after human-request check); aligns with gateway **U1** key family (**Chat B** owns skip-debounce on inbound).
- [x] **Optional external LLM:** OpenAI-compatible **`POST …/chat/completions`**; env **`AI_LLM_BASE_URL`**, **`AI_LLM_API_KEY`**, **`AI_LLM_PRIMARY_MODEL`**, **`AI_LLM_JUDGE_MODEL`** (`backend/shared/config.py`); spend allowed only when **`ops_runtime_config`** **`ai.fallback.enabled`** is true plus token caps **`ai.fallback.max_primary_tokens`** / **`ai.fallback.max_judge_tokens`**; optional judge **`ai.fallback.use_judge`** + **`ai.fallback.quality_threshold`**. **General path only**; failures → deterministic **REPLY** (no engine-induced **HANDOFF**).
- [x] **Quality gate:** local heuristics (`quality_gate.py`) + optional judge JSON (`llm_client.parse_judge_json`).
- [x] **Helpers** `respond_logic`, `runtime_config`, `llm_client`, `quality_gate`, `llm_pipeline`; **tests** `tests/test_ai_respond_logic.py`, `tests/test_ai_engine_api.py`, **`tests/test_llm_pipeline.py`**, **`tests/test_ai_respond_golden.py`**, **`tests/golden/ai_respond/`**; **`pytest`** + **`pytest.ini`**.

### Still open (blueprint remainder)

- [ ] Full **input** contract: history, personas, catalog, rules (as blueprint lists) — wire or stub explicitly.
- [ ] **Multilingual** nuance: Romanized Hindi-only messages still tagged **`en`** (prompt asks model to match customer); richer locale detection if product requires.
- [ ] **Cost controls beyond token caps:** per-client daily ceilings, structured usage metering to **`bill_usage_daily`** or provider dashboard discipline (**Stem** / **Chat N** harness).
- [ ] Optional: **OpenAPI** snapshot / CI contract test for **`/ai/respond`** (**Chat N**).

---

## M3 — Client API (auth, onboarding, catalog)

**Status (2026-05-14):** Signup / OTP / team / catalog REST are **deferred pending product confirmation** — this repo ships **email/password login** (`POST /auth/login`, `GET /auth/me`) only until Stem re-opens M3 scope.

- [ ] `POST /signup` (trial, `trial_end`, default personas).
- [ ] OTP auth (`POST /auth/otp/start`, `POST /auth/otp/verify`) if product requires it (else document “email/password only” deviation).
- [ ] `GET /me` — align path with blueprint (`GET /me` vs `/auth/me`) or document mapping.
- [ ] Team: `POST/GET /team/users`, `PUT /team/users/{id}`, `PUT /team/agents/{id}/profile` (**`agent_profiles`** backed).
- [ ] Client: `PUT /client/profile`, `PUT /client/persona`.
- [ ] Catalog: `POST/GET/PUT/DELETE /catalog/items`, optional `POST /catalog/import` (CSV).

---

## M4 — Team inbox (state machine & productivity)

- [x] Align **`inbox_chats.state`** with blueprint: **`AI_ACTIVE`**, **`HUMAN_REQ`**, **`AGENT_ACTIVE`**, **`CLOSED`**, **`WAITING_OWNER_DATA`** (Alembic **`0008_inbox_blueprint_states`** migrates legacy `PENDING_AGENT` / `RESOLVED` rows).
- [x] `POST /inbox/chats/{id}/resolve` → **`CLOSED`** + assignment **`RESOLVED`** + audit/notifications.
- [x] Agent reply sets **`ai_paused_until`** from **`ops_runtime_config`** (`inbox.agent_reply_pause_hours_*`, Starter vs default).
- [x] Reassignment: **`inbox_assignment_audit`** + notify assignee + **CC owners** (REST paths); worker handoffs notify owners.
- [ ] Typing: team-only; optional **hard lock** (only assignee sends).
- [x] Optional: `POST /inbox/chats/{id}/messages` alias — keep **`/reply`** as canonical; documented in `README.md` / `HANDOFF.md`.
- [x] WebSocket: **`notification`** event type via **`DBPoller`** on **`inbox_notifications`**; production WS story: **WSS**, short-lived JWT, **`CLIENT_API_WS_ALLOWED_ORIGINS`**.

---

## Owner/agent Flutter UI (Chat G — `flutter_app` + `mobile`)

**Scope boundary:** Checklist rows below are the **tenant** experience (**`owner`** / **`agent`**) after login: **`HomeShell`** on both apps (Inbox · Dashboard · Account/Settings). The same binaries also route **`super_admin`** → **`SuperAdminShell`** (SOP library, runs, **Control** coordination copy, **`GET /dash/admin/*`** charts) — that surface is **Chat H** / checklist **§ M9 interactive UI** + **§ M8** super-admin dash; do not conflate with Chat G ownership.

Shipped **without** claiming full blueprint **§ M4** product completeness (backend + workers remain per Chat F/C).

- [x] **Login / session:** `GET /auth/me` → reject unsupported roles (clear token + error); **`SessionController.wsLastError`**; WS connect **try/catch**; disconnect clears WS error; role snackbars; WS after login for **tenant** users; snackbar if WS fails but REST OK; password cleared on success.
- [x] **Nav + refresh:** `flutter_app` **Inbox · Dashboard · Account**; `mobile` **Inbox · Dashboard · Settings** (`HomeShell` tab order **0=Inbox, 1=Dashboard, 2=Account-or-Settings**); app bar **Refresh** → **`bumpInboxGeneration()`** + **`bumpDashGeneration()`** (inbox + dashboard).
- [x] **Inbox + thread:** filters (All / Mine / Unassigned / **Needs human** = `human_queue`), phone search, pull-to-refresh, retry, agent hint; assign / reassign / escalate / unassign / **resolve** (owner / super_admin where API allows); assignment banner; **`ai_paused_until`** on list items; **`mobile`** tenant inbox guardrails (**`canUseTenantInboxApi`**, **`superAdminClientId`**, **`_cid(session)`** on scoped REST); typing/reply gated per RBAC.
- [x] **Client dashboard (Chat J):** **`ClientDashboardScreen`** → **`GET /dash/client/overview|agents|quality`**; **401** → logout; **404** → mock preview + banner; no new pub deps for dash alone.
- [x] **API client (`mobile` + `flutter_app`):** `listChats` (`human_queue`, blueprint states), **`listNotifications`** / **`postNotificationRead`**, **`postResolve`**, reassign/unassign/escalate, **`dashGet`**.
- [x] **Dual bases (super_admin / Chat H):** persisted **`CLIENT_API_BASE_URL`** + **`OPS_API_BASE_URL`** (dart-define or in-app link sheet); documented for **`ops_api`** smoke — see **`flutter_app/README.md`** / **`mobile/README.md`** (CORS notes).
- [x] **Docs:** `flutter_app/README.md` + `mobile/README.md` — Chat G + **Windows / Android emulator** base URL table; **`flutter create`** when `windows/` / `android/` folders are absent.

**Stem note — Chat G slice:** The checklist rows above are **all `[x]`** — **checklist-owned Chat G work** for **tenant** **`HomeShell`** (**`owner`** / **`agent`**: inbox, WS, **`GET /dash/client/*`**, shared API client, dual bases, docs) is **complete** for this section. **`dart analyze` + G/H device smoke** (Windows + Android) is a **merge / verification gate** documented for **Stem / Chat N / you** (README + **`HANDOFF.md`** **Stem note — Chat N**), **not** an unchecked item here. **Richer client dashboard charts**, **M8 phase‑2** **`/dash/client/*`** JSON or new routes, and **deep links** are **follow-ups** owned by **Chat J** (**§ M8 — Phase-2 — `/dash/*`**), **Stem**, and **Chat L** respectively — they do **not** reopen rows inside **§ Owner/agent Flutter (Chat G)**.

---

## M5 — Billing + KYC + usage

### Landed (Chat E — `billing_api` + migrations `0004`–`0009`)

- [x] **Schema:** `bill_plans`, `bill_subscriptions`, `bill_events` (**`UNIQUE (provider, provider_event_id)`**); **`0009`**: **`bill_invoices`**, **`api_clients.kyc_india_json`**, **`kyc_submitted_at`**, **`kyc_verified_at`** (workflow continues to use existing **`kyc_status`** text when set).
- [x] **App:** dedicated FastAPI **`backend/apps/billing_api/`** (default **port 8086**); **HANDOFF** *Billing (M5 layout)* + **README** *Billing (M5)*.
- [x] **Webhooks (signed):** **`POST /webhooks/razorpay`** and **`POST /webhooks/paddle`** (same signing rules as v1 slice).
- [x] **REST (JWT = `client_api` login):** **`POST /billing/razorpay/create-checkout`** (Razorpay Orders API via **`BILLING_RAZORPAY_KEY_ID` / `SECRET`**), **`POST /billing/paddle/create-checkout`** (Paddle Billing **`POST /transactions`** via **`BILLING_PADDLE_API_KEY`** + **`BILLING_PADDLE_ENVIRONMENT`**), **`GET /billing/subscription`**, **`GET /billing/invoices`**, **`POST /billing/kyc/india`** (owner/super_admin scoped).
- [x] **Map to `api_clients` + subs + invoices:** webhook handlers update **`api_clients`**, upsert **`bill_subscriptions`**, upsert **`bill_invoices`** (Razorpay **`invoice.paid`**, Paddle **`transaction.*` paid path**). Extended events: **`payment.failed`**, **`refund.processed`**, **`subscription.halted`**, Paddle **`transaction.payment_failed`**, **`refund.*`** (see **`process_webhook.py`**).
- [x] **Plan gating (internal / DB-only):** **`wa_gateway`** `_fetch_client_row` uses **`api_clients.entitlement_plan`** overridden to **`churned`** when latest **`bill_subscriptions.status`** is terminal / failure class (**no** live Razorpay/Paddle calls in paywall path).
- [x] **Chat J coordination:** **`client_api/routes_dash.py`** docstring states **`/dash/*`** is read-only and billing truth is **`billing_api` + core tables**.
- [x] **Secrets / settings:** webhook + API keys in **`backend/.env.example`** + **`backend/shared/config.py`** (includes **`BILLING_API_CORS_ORIGINS`** for browser checkout).
- [x] **Tests:** `tests/test_billing_signatures.py`, **`tests/test_billing_api_routes.py`** (auth required on REST).

### Still open (blueprint remainder)

- [ ] **KYC verification** (India): admin review APIs, **`verified` / `rejected`** transitions, notifications — beyond submit-only **`POST /billing/kyc/india`**.
- [ ] **Checkout UX / control plane:** surface UPI vs card, plan picker, **`bill_plans` + `ops_runtime_config`** pricing keys (not only pass-through provider create payloads).
- [ ] **Webhooks:** chargebacks / disputes / additional Paddle adjustment types if product requires.
- [ ] **`GET /dash/admin/*` billing tiles:** revenue / MRR-style aggregates sourced from **`bill_invoices`** / subscriptions (**Chat J**, still read-only SQL).

---

## M6 — Broadcast

### Landed (Chat L — backend slice)

- [x] **Template-only** pipeline: **`wa_outbox.kind = 'TEMPLATE'`** with strict JSON body (`template_name`, `language`, optional `components`); **`outbox_sender`** sends WhatsApp **template** messages via Graph API (no silent plain-text marketing).
- [x] **Opt-in** storage: **`customer_marketing_opt_in`**; enforced when **`ops_runtime_config`** **`m6.broadcast_policy.require_marketing_opt_in`** is true (default).
- [x] **Trial/Starter (and matrix edits)** via **`m6.broadcast_policy.blocked_entitlement_plans`** (default blocks **trial** + **starter**); **`broadcast_campaign_worker`** skips targets (`skipped_plan` / `skipped_no_optin`).
- [x] **Campaign queue tables** **`wa_broadcast_campaigns`** / **`wa_broadcast_targets`** → enqueue **`wa_outbox`** with idempotency `broadcast:{campaign_id}:{chat_id}`.

### Still open (blueprint remainder)

- [ ] Owner/tenant REST + UI to manage opt-in, approved templates, and campaign lifecycle (this slice is **worker + schema + gates** only).

---

## M7 — Analytics & alerts

### Landed (Chat L + Chat K touch)

- [x] **Aggregate hourly columns** (with **`0010`**): **`metrics_hourly_system.billing_webhook_process_errors`**, **`wa_meta_webhook_errors`** — filled by **`metrics_rollup_worker`** from **`bill_webhook_processing_errors`** and **`wa_meta_webhook_errors`**.
- [x] **DEAD** time truth: **`wa_outbox.dead_at`** set on terminal DEAD; hourly **`wa_outbox_rows_dead`** uses **`COALESCE(dead_at, created_at)`** bucket.
- [x] **Alert rows + logging (no paging yet):** **`ops_alert_events`**; **`alert_eval_worker`** thresholds from **`alerts.thresholds`** — **OUTBOX_DEAD_SPIKE**, **META_WEBHOOK_ERROR_SPIKE** (if the Meta errors table is absent or SQL fails, the worker treats the Meta count as **0**).
- [x] **Billing webhook handler failures:** **`bill_webhook_processing_errors`** + **`ops_alert_events`** (`BILLING_WEBHOOK_PROCESSING_ERROR`, minute dedupe) on Razorpay/Paddle **500** path after signature verification.

### Still open (blueprint remainder)

- [ ] Pager / Slack / on-call routing; super-admin **dashboard surfacing** of **`ops_alert_events`**; ban signals, GPU throttling, SLA breach hooks.
- [ ] **M9 phase-2:** auto-open SOP runs from alert types — **`POST /ops/sops/{id}/run`** with `trigger_type=auto` (**coordinate Chat I**; consume **`ops_alert_events`** or a mapped view).

---

## M8 — Dashboards & control plane

### APIs (backend)

- [x] **Read-only dashboard REST (Chat J)** — router **`backend/apps/client_api/routes_dash.py`**, OpenAPI tag **`dash`**, Pydantic **`Dash*Out`** models in **`backend/apps/client_api/models.py`**.
  - **Client (tenant):** `GET /dash/client/overview`, `GET /dash/client/agents`, `GET /dash/client/quality` — JWT roles **`owner` \| `agent` \| `super_admin`**; **`super_admin`** must pass **`?client_id=<uuid>`** (same scoping rule as inbox). Aggregates from **`api_clients`**, **`inbox_chats`**, **`wa_numbers`**, **`bill_usage_daily`**, **`metrics_daily_client`** / **`metrics_daily_agent`** (zeros when workers have not written rows). **`/quality`:** SQL counts chats in **`HUMAN_REQ`** or **`WAITING_OWNER_DATA`** (exposed under the legacy response key **`chats_pending_agent`** in **`DashClientQualityOut`**).
  - **Super-admin (global):** `GET /dash/admin/overview`, `GET /dash/admin/collections`, `GET /dash/admin/providers/razorpay`, `GET /dash/admin/providers/paddle`, `GET /dash/admin/ops/whatsapp`, `GET /dash/admin/geo` — JWT **`super_admin`** only. Alias **`GET /dash/admin/admin/geo`** (same JSON as **`/dash/admin/geo`**) for the blueprint’s `.../admin/geo` path under **`/dash/admin/`**.
  - **Tests (no Postgres in CI):** **`tests/test_dash_handlers_mocked_db.py`** (handler bodies + mocked `engine.begin()`), **`tests/test_dash_openapi_and_rbac.py`** (OpenAPI paths + RBAC short-circuit).
  - **Still not this row:** revenue / MRR-style **`/dash/admin/*`** tiles from **`bill_invoices`** — see **§ M5 — Still open** (`GET /dash/admin/*` billing tiles) when Stem defines SQL; implementation work is tracked under **§ M8 — Phase-2 — `/dash/*`** below.

### § M8 — Phase-2 — /dash/* (Chat J; Stem-gated)

- [ ] **Replace placeholders** (MRR / revenue / collections, latency, CSAT / proxies) using **`bill_*`**, **`metrics_*`**, **`inbox_*`**, or future rollups — coordinate **Chat E**, **Chat K**, and **Stem** when SQL and product definitions land.
- [ ] **New `GET /dash/*`** (or **breaking JSON** for **Chat G / H**): **Stem first**; document **RBAC** + paths in **`HANDOFF.md`** and under **§ M8 — APIs (backend)** here; extend **`tests/test_dash_handlers_mocked_db.py`**, **`tests/test_dash_openapi_and_rbac.py`**, and/or add sibling **`tests/test_dash_*.py`** as needed.

### Interactive control plane (super-admin UI)

Blueprint calls for an **Admin → Control Plane** experience (not only REST). Track **Flutter and/or web** — pick one primary surface and list the other as optional.

**Chat H (2026-05-14):** **`SuperAdminControlPlaneScreen`** — per-panel “Needs: …” + explicit **no admin GET/PUT routes → no Flutter editors**; **M9** phase-2 / day-1 seed / PDF = Stem + **Chat I** + **Chat L** (no extra UI hooks unless Stem assigns).

- [x] **Runtime config editor (API):** **`GET/PUT /ops/runtime-config/{key}`** + audit (**ops_api**). **Flutter (Chat H):** **`SuperAdminControlPlaneScreen`** loads/saves debounce, urgent, AI fallback, needs-owner reply, typing hard lock.
- [ ] **Pricing panel (India)**: `pricing.in.*` minor units, live **preview** (“UPI = ₹X”, “Card = ₹Y”) — keys not seeded yet.
- [x] **Debounce panel**: Flutter editors for **`debounce.*`** / **`debounce.adaptive.*`**.
- [x] **Urgent bypass panel**: Flutter JSON editor for **`ai.urgent_bypass_substrings`**.
- [x] **AI fallback panel**: Flutter toggles/fields for **`ai.fallback.*`** + daily cap key.
- [x] **Client dashboard (Flutter)**: usage, handoffs, missing-data hotspots, agent performance charts — **Chat G v1**: **`ClientDashboardScreen`** wired to **`GET /dash/client/*`** (`401` logout, `404` mock + banner); richer charts TBD.
- [x] **Super-admin dashboard (Flutter Android + Windows)**: **Chat H** — charts from real **`GET /dash/admin/*`** JSON (`DashDictBarCard` for `Map<String,int>`, **`DashMessageTotalsCard`** stacked bar for `hourly_system_last_24h`, **`DashKpiRow`**, Raw JSON dialog; **`SuperAdminDashScreen`**); richer **MRR/revenue** visuals when **Chat J** replaces placeholder aggregates.

---

## M9 — SOP / Runbook Center (in-system) — **APIs + interactive product**

**Backend (`ops_api`, Chat I) is landed** — see § **Data & APIs** below. **Interactive SOP / Runbook UI (Chat H)** is **landed** in **`flutter_app/`** (and **`mobile/`** parity per HANDOFF); remaining checklist items here are **phase-2 auto-trigger**, **day-1 SOP seed content**, and **optional PDF**.

### Data & APIs

- [x] Migrations: **`ops_sops`**, **`ops_sop_versions`**, **`ops_run_logs`** (+ indexes) — Alembic **`0006_ops_sops`**; FastAPI **`backend/apps/ops_api/`** (Stem: dedicated app, not `client_api`).
- [x] `GET/POST /ops/sops`, `GET/PUT /ops/sops/{id}` (versioning on update via `ops_sop_versions`).
- [x] `GET /ops/sops/{sop_id}/versions` — list immutable version bodies for history / diff / restore (**canonical `ops_api` only**; **Chat H** consumes — no duplicate route on `client_api`).
- [x] `POST /ops/sops/{id}/run` → creates **`ops_run_logs`** row with `context_json`.
- [x] `GET /ops/runs`, `GET /ops/runs/{run_id}` (filters: `client_id`, `sop_id`, `from_date`, `to_date`, `trigger_type`).

### Still open (ops_api — Chat I + Stem; backend / contract)

**Gate (Chat A):** Ship the items below **only** after **Stem-approved** API contract (OpenAPI + consumer notes for **Chat H** / **Chat L**) **and** new **Alembic migrations** when the contract requires schema changes — no ad-hoc raises to **`LIMIT 500`**, **`trigger_type`**, or export paths without that sign-off.

- [ ] **Auto-trigger API hooks:** Chat **L** workers (e.g. **`alert_eval_worker`**) or a thin **`ops_api` internal** caller → **`POST /ops/sops/{id}/run`** with `trigger_type=auto` (and stable **`context_json`** keys, e.g. **`ops_alert_event_id`**, **`alert_type`**); **`ops_runtime_config`** map **`alerts.sop_trigger_map`** (alert type → SOP **slug** or id); **idempotency** policy per alert/run (Stem + Chat **I**).
- [ ] **`GET /ops/runs` pagination:** today **`ORDER BY created_at DESC`** + hard **`LIMIT 500`**; add **`cursor` / `limit`** (or offset) + document contract for **Chat H** list + infinite scroll.
- [ ] **Stricter `trigger_type`:** evolve beyond API-layer literals to **DB `CHECK`**, shared allowlist, or enum aligned with **`auto`** / future **`alert:*`** values; migration + backfill rules if needed.
- [ ] **`GET /ops/sops/{id}/versions` at scale:** v1 returns **full** history **`ORDER BY version_num ASC`** (no paging). Optional **`limit` / `before_version`** (or cursor) if bodies grow large; consider **excluding** `body_markdown` on a “light” index endpoint for timeline-only UI.
- [ ] **Export:** PDF or printable runbook (see **Optional** below — keep one product-owned row).

### Interactive SOP / Runbook UI (super-admin) — **shipped (Chat H); phase 2 below**

This is the **dashboard / interactive solution** for SOPs (not a static Markdown file in the repo alone). **Auto-trigger** and **day-1 seed content** remain open.

- [x] **SOP library screen**: list by category, search, status (`active` / `archived`). — **`flutter_app`**: `SuperAdminShell` → SOPs tab → `SopLibraryScreen` (`GET /ops/sops` query params `q`, `category`, `status`).
- [x] **SOP detail**: rendered Markdown **preview** + metadata (owner, version, last updated). — **`SopDetailScreen`** + `flutter_markdown`.
- [x] **Editor**: split or tabbed **Markdown editor** with preview; **save** creates new **version** (immutable history). — **`SopEditorScreen`** (POST create / PUT update); preview can be added as a tab later.
- [x] **Version history**: timeline, **diff** between versions, **restore** prior version (writes new version + audit). — **`GET /ops/sops/{id}/versions`** (Chat I extension) + `SopVersionsScreen` (diff unified/side-by-side; restore opens editor then PUT).
- [x] **Run flow**: “Start run” captures **context** (client id, wa number, error codes, links to dead outbox rows, free text) → POST run → show **run id**. — **`SopRunStartScreen`** (`POST /ops/sops/{id}/run`).
- [x] **Run log UI**: searchable table + **run detail** (steps checklist optional; at minimum show context + timestamps + user). — **`SopRunsListScreen`**, **`SopRunDetailScreen`** (`GET /ops/runs`, `GET /ops/runs/{id}`); filters for `sop_id` / `client_id`.
- [ ] **Auto-trigger wiring** (phase 2): e.g. outbox **DEAD** spike → create run + task + in-app notification + deep link into run detail. **Surface:** consume **`ops_alert_events`** (Chat **L**) + mapped SOP slug (**`alerts.sop_trigger_map`** TBD) → **`POST /ops/sops/{id}/run`** (**Chat I** contract); Stem sequences schema/API if `context_json` needs standard keys. **Detail:** see **§ M9 — Still open (ops_api)** → **Auto-trigger API hooks** (same workstream).
- [ ] **Day-1 SOP content** seeded or imported: India provisioning, BYON, trial expiry, payment failure, dead-letter recovery, webhook downtime, ban recovery, backup drill, key rotation, release rollback (as blueprint lists).

### Optional

- [ ] Export SOP as PDF / printable runbook for audits.

---

## M10 — Release manager

**Product scope (2026-05-14):** Per architecture **gated releases**, **`/ops/releases*`** (register build, attach **test / artifact hash**, **promote**, **rollback**, **super_admin**- or ops-gated) is **still in scope** until Stem moves release tracking entirely off-repo (then replace this section with a stub + external process).

**Handoff status:** **Chat M** documentation slice is **complete** in **`HANDOFF.md`**, **`README.md`** (§ Release / CI), **Meta** cross-rule below, and this section’s intent — so scope, target CI, approval hooks, and **Chat N** coordination are **documented**. **Unchecked rows below** remain **open engineering** (no release API in tree yet; **`ci.yml`** still **pytest-only**).

- [ ] **`GET/POST /ops/releases*`** (or equivalent under **`ops_api`**): **register** build metadata + **test report hash**; **promote** current candidate; **rollback** to prior registered build — all **admin-gated** with audit fields.
- [ ] **CI (`.github/workflows/ci.yml`):** keep default **`python -m pytest tests/`** job; add **Postgres `services:`** job that runs **`alembic upgrade head`** + **`RUN_POSTGRES_INTEGRATION=1`** integration module; add **contract** job(s) (e.g. OpenAPI / billing signatures / gateway no-AI imports) as Stem assigns; optional separate job with **`RUN_WA_GATEWAY_E2E=1`** + documented secrets (off by default on PRs).
- [ ] **Manual approval hooks** documented in **README** + **HANDOFF**: changes under **`backend/apps/ai_engine/`**, **`wa_gateway/`** (routing / paywall / debounce), and **`billing_api/`** (webhooks, checkout, plan-affecting paths) require **human review** before prod — e.g. GitHub **Environments** (`production`) with **required reviewers**, **CODEOWNERS** on those paths, and/or **branch protection**; Stem picks which levers the org uses.

---

## Cross-cutting

- [ ] **`ZY_BASE_DIR`** (or equivalent): no hardcoded `C:\` paths; logs/exports/model cache derived from config (blueprint §10).
- [ ] **Acceptance tests** in repo: debounce **A1–A5**, urgent **U1–U2**, NEEDS_OWNER fixed string, burst → single reply E2E.
- [ ] Staging environment mirrors prod behavior (numbers + payment sandboxes).

---

## Meta — lifecycle of *this* checklist

**Cross-rule:** Shipping **§ M10** (release APIs + CI gates) does **not** automatically satisfy the **remove checklist** criteria below — **Chat A** still decides when open items are fully mirrored externally or the spec is frozen enough that **`HANDOFF.md`** alone suffices.

- [ ] **Remove this file** (`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`) **and** the README pointer to it when **all** of the following are true:
  - every open product item lives in your **external** tracker (Jira/Linear/etc.) with links, **or** the spec is frozen and `HANDOFF.md` alone tracks remaining deltas; and
  - the team agrees the checklist has **no unique content** left (no unchecked boxes that aren’t duplicated elsewhere).
- [ ] If you **keep** a single in-repo tracker instead, replace this file with a short stub pointing to `HANDOFF.md` + external board — then delete the long checklist.
