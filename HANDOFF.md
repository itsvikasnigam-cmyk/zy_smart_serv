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

## Stem compressed context (session key points — read for sequencing)

Use this block to **onboard fast**; details live in **What is implemented**, **Known gaps**, **Stem notes** (N / E), **M1 contract**, **Chat * paste blocks**, and **`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`**.

| Topic | One-line |
|------|----------|
| **“Slice landed”** | Means **this repo’s coded + tested (or doc’d) vertical** for that chat letter — **not** “entire blueprint section forever.” Full blueprint rows stay in the **checklist** until Stem ticks or defers them. |
| **Chat N** | **Ongoing:** default **`python -m pytest tests/`**; optional **`RUN_POSTGRES_INTEGRATION`** + **`DATABASE_URL`** and **Flutter device smoke** are **documented / manual** gates — see **Stem note — Chat N (scope vs evidence)**. |
| **Chat B (M2)** | **`WA_GATEWAY_ALLOW_CLIENT_ID_HEADER`** gates **`X-ZY-Client-Id`**; **`PAYWALL`** **`wa_outbox`** + trial/churned/**usage** gate; adaptive + urgent **U1**; **`0007`** meta errors; **no AI** in webhook + tests. **Chat C** second-line **`PAYWALL`** before **`/ai/respond`** on **legacy OPEN** batches (**batch_processor**) mirrors gateway entitlement + usage rules. **Follow-ups:** staging/load proof. |
| **Chat C (workers)** | **Batch path landed:** **A5** skip; **`HUMAN_REQ` / `WAITING_OWNER_DATA`** + **`inbox_notifications`** + **`pg_notify`**; sealed window; outbox lease/**`DEAD`**; **U2 strict** — post-**`/ai/respond`**, urgent **`REPLY`** → **`HANDOFF`** (`urgent_time_sensitive_u2`, **`reply_text`** cleared) → **no** generic urgent **`AI_REPLY`**; **`NEEDS_OWNER_DATA`** customer **`wa_outbox`** via **`_load_needs_owner_customer_reply_text`** (same rules as **`ai_engine`**); **second-line paywall** before AI call (**`PAYWALL`**, batch **`PROCESSED`**) for churned / expired trial / **hard_block**. **Tests:** **`tests/test_batch_processor_policy.py`**. **Still:** **DEAD** product surfacing (**§ M7** / **Chat L**). |
| **Chat F** | **M4** inbox/WS/notifications/**`0008`** landed; **M3** signup/OTP/team/catalog **deferred** until product. Still: pagination, **`LISTEN`**, typing **hard lock**, notifications **UI**. |
| **Chat G (Flutter tenant)** | **Landed:** **`HomeShell`** (**`owner`** / **`agent`**) — inbox + WS + **`GET /dash/client/*`**, **`ClientApiRepository`**, dual bases + READMEs — checklist **§ Owner/agent Flutter (Chat G)** is **all `[x]`**. **Not rows in § Chat G:** **`dart analyze` + device smoke** (Windows + Android) = **Stem / Chat N / you** per README + **Stem note — Chat N**; **richer client charts** / tenant **`/dash/client/*` contract** evolution = **§ M8 — Phase-2 — `/dash/*` (Chat J)** + Stem; **deep links** = **Chat L** / Stem. |
| **Chat E (M5)** | **`billing_api`** + **`0004`/`0009`** + gateway **DB-only** gating **pytest-green**; **not** full **§ M5** — see **Stem note — Chat E** + checklist **Still open** (KYC verify, pricing UX, disputes, **`/dash/admin`** tiles). |
| **Chat D (M1)** | **`/ai/respond`** contract unchanged for **`batch_processor`** (**no `batch_processor.py` edits** in Chat D slice); optional **LLM** via **`AI_LLM_*`** + **`ai.fallback.*`**; **Hinglish**; goldens + pipeline tests; **`pytest.ini`** filters Starlette **`multipart`** warning. |
| **Chat H (M8/M9 Flutter)** | **SOP Runbook** + **`GET /dash/admin/*`** charts (**`lib/widgets/dash_bar_charts.dart`**, **`SuperAdminDashScreen`** — dict bars, KPI chips, stacked hourly message totals, Raw JSON); **Control** tab = **`SuperAdminControlPlaneScreen`** read-only checklist + § M8/M9 coordination copy (**no** invented admin POSTs). **Still open:** interactive M8 editors (runtime config, pricing, debounce, urgent, AI fallback) need **Stem-approved** **`client_api`** (or dedicated admin) **read/write** routes; **M9** phase-2 / day-1 seed / PDF — no extra UI hooks unless Stem assigns; polish + **Chat L** deep links. |
| **Chat I (M9 `ops_api`)** | **v1 landed:** **`0006_ops_sops`**, **`GET/POST /ops/sops`**, **`GET/PUT …/{id}`**, **`GET …/versions`**, **`POST …/run`**, **`GET /ops/runs`** (+ filters, **`LIMIT 500`**), **`GET /ops/runs/{id}`**; **super_admin** JWT; **`tests/test_ops_api_*.py`**, **`dev_ops_api_smoke.py`**. **Still open (checklist § M9 — Still open ops_api):** auto-trigger hooks, **runs pagination** beyond 500, stricter **`trigger_type`** / DB, versions-at-scale, **export** — **Stem + contract + migrations** when needed. |
| **Chat J (`/dash/*`)** | **Phase-1 landed:** **`routes_dash.py`** + **`Dash*Out`** + **`tests/test_dash_*.py`** (**checklist § M8 — APIs (backend)**). **Phase-2 (Stem-gated):** swap **MRR / revenue / collections / latency / CSAT** placeholders for **`bill_*`**, **`metrics_*`**, **`inbox_*`**, future rollups — **Chat E**, **Chat K**, **Stem**; **no** new **`GET /dash/*`** or **breaking JSON** for **G/H** without **HANDOFF** + **§ M8 — APIs** + **§ M8 — Phase-2 — `/dash/*`** + tests. **Overlap § M5 — Still open** for admin billing tiles. |
| **Chat K (usage / metrics)** | **Landed:** **`0005_usage_metrics`**, **`usage_increment_worker.py`**, **`metrics_rollup_worker.py`**, **`usage_metrics_common.py`**, **`tests/test_usage_thresholds.py`**; optional **`tests/test_postgres_integration_optional.py`** when **`RUN_POSTGRES_INTEGRATION=1`** + **`DATABASE_URL`** (see **Stem note — Chat N**). **Not K:** inbound **paywall enforcement** = **Chat B** + **Chat C**; **CI Postgres service job** = **Chat M**. **Next:** richer rollups / new metric keys for **§ M8 — Phase-2** — **Stem** + coordinate **Chat J**. |
| **Chat L (M6/M7)** — **backend slice landed** | **`0010_m6_m7_broadcast_alerts`**: **`wa_broadcast_*`**, **`customer_marketing_opt_in`**, **`ops_alert_events`**, **`bill_webhook_processing_errors`**, **`wa_outbox.dead_at`**, hourly metrics columns; **`broadcast_campaign_worker`**, **`alert_eval_worker`**, **`broadcast_gating`**, **`ops_alerts`**; **`outbox_sender`** **TEMPLATE** path + **`dead_at`**; **`billing_api`** 500 → DB row + **`ops_alert_events`**; **`tests/test_m6_m7_helpers.py`**. **Not wired yet:** **M9** phase-2 **auto-trigger** from alerts → **`POST /ops/sops/{id}/run`** (`trigger_type=auto`) — needs **Stem + Chat I** contract (e.g. **`alerts.sop_trigger_map`**); product **pager** / campaign **UI** / extra alert types. |
| **Chat M (M10)** | **Doc / handoff slice (done):** **`/ops/releases*`** scope, **target CI**, **manual approval hooks**, **Chat N** after CI topology changes, checklist **§ M10** + **Meta** cross-rule, this paste block, **README §4** — aligned in repo. **Engineering (still open):** no **`/ops/releases*`** implementation yet; **no** Postgres **service** / integration / contract / E2E jobs in **`ci.yml`** (still **pytest-only**); GitHub **Environments** / **CODEOWNERS** = process for Stem to enable. **CI today:** pytest-only Ubuntu job. **Target:** Postgres **service** + **`RUN_POSTGRES_INTEGRATION`** + contract job(s) + optional **`RUN_WA_GATEWAY_E2E`**. **After CI topology change:** **Chat N** full README smoke. |
| **Future QA** | Plan **extensive per-module + chain runs** later; does not replace landing slices now. |

**Chat L — what “output” means next:** document or implement only **Stem-approved** follow-ups: **I+M9** auto-run wiring (schema + idempotent runner), **dashboards** reading **`ops_alert_events`**, or **operational** paging — each as its own small PR with **Chat N** tests. Do **not** re-implement **`0010`** core unless Stem files a regression.

## What is already implemented (this repo)

- FastAPI **WA Gateway** (`backend/apps/wa_gateway/` — **Chat B slice landed**): Meta verify; inbound **store-first** + dedupe **`meta_msg_id`** (`INSERT … ON CONFLICT … DO NOTHING RETURNING` — empty return **continue**s: no extra usage bump, no batch change, no duplicate **PAYWALL**); routing **`phone_number_id` → `wa_numbers` then `wa_trial_map`** (unchanged order). **Debounce:** **`ops_runtime_config`** baseline + **adaptive** (`debounce.adaptive.*`, blueprint **A3**) + **urgent U1** (merge **`ai.urgent_bypass_substrings`** + **`routing.urgent_substrings`** → **`process_after = now()`** for immediate seal). **Trial / entitlement + usage paywall:** reads **`bill_usage_daily`** (today UTC) + limits via **`usage_metrics_common`** (same rules as Chat K); per-request **+1** for in-flight multi-message hard cap; blocks **churned**, **expired trial** (UTC-aware), **usage ≥ hard_block**; **skips OPEN batch** when blocked so **Chat C** does not seal → **`/ai/respond`**; **`wa_outbox`** **`kind='PAYWALL'`** with idempotency keys **`paywall:{reason}:{client_id}:{day-or-usage-suffix}`** + **`ON CONFLICT DO NOTHING`** (needs **`from_wa_number_id`**; if routing left it **NULL**, no row — same as header-only dev path). Customer copy: default constant + optional **`ops_runtime_config`** **`m2.service_inactive_customer_reply`** (string or `{"text":"…"}`). **Never call AI in webhook** — docstring + **`tests/test_wa_gateway_no_ai.py`**; **`tests/test_wa_gateway_meta_helpers.py`** (urgent + **`extract_meta_errors`**). **`POST /webhooks/meta/errors`** → **`wa_meta_webhook_errors`** (**Alembic `0007`**). **`X-ZY-Client-Id`:** honored only when **`WA_GATEWAY_ALLOW_CLIENT_ID_HEADER=true`** (`Settings.wa_gateway_allow_client_id_header`, default **false**); see **`backend/.env.example`**. Status webhook → **`wa_status_events`** / **`wa_outbox`** update.
- **AI Engine (Chat D — M1)** (`backend/apps/ai_engine/`): **`POST /ai/respond`** — same **response JSON envelope** for **`batch_processor`** (see **M1 — `POST /ai/respond` contract** below). **Deterministic routing** (greeting → **HANDOFF** → urgent **REPLY** → **NEEDS_OWNER_DATA** → default **REPLY**). **`language`:** `en` \| `hi` \| **`hinglish`** (Devanagari + Latin in one message) \| `auto`. **`ops_runtime_config`:** **`ai.urgent_bypass_substrings`**, **`ai.needs_owner_data_customer_reply`**, plus **`ai.fallback.*`** for optional OpenAI-compatible **LLM + judge** (requires env **`AI_LLM_API_KEY`** and **`ai.fallback.enabled`**). **Tests:** **`tests/test_ai_respond_logic.py`**, **`tests/test_ai_engine_api.py`**, **`tests/test_llm_pipeline.py`**, **`tests/test_ai_respond_golden.py`**, **`tests/golden/ai_respond/`** (+ **`pytest.ini`**, **`pytest`** in **`backend/requirements.txt`**). **Still open (blueprint):** full **input** bundle (history, personas, catalog) — checklist **§ M1 — Still open**.
- **Billing (M5)** (`backend/apps/billing_api/`): Alembic **`0004_billing`** + **`0009_billing_kyc_invoices`** (`bill_plans`, `bill_subscriptions`, `bill_events`, **`bill_invoices`**, **`api_clients.kyc_india_json`** / submission timestamps); signed webhooks **`POST /webhooks/razorpay`** / **`POST /webhooks/paddle`**; **REST** **`POST /billing/razorpay|paddle/create-checkout`**, **`GET /billing/subscription`**, **`GET /billing/invoices`**, **`POST /billing/kyc/india`** (JWT = **`client_api`**); extended webhook coverage (invoice / payment failure / refund / renewals + Paddle transactions). **M7 (Chat L):** handler **500** after successful signature → **`bill_webhook_processing_errors`** row + **`ops_alert_events`** (`BILLING_WEBHOOK_PROCESSING_ERROR`, minute dedupe). Gateway paywall reads **DB-only** entitlement ( **`api_clients`** + latest **`bill_subscriptions.status`** lateral join). Default local **port 8086**.
- **Workers**: `batch_processor.py` (seal batch; **second-line paywall** before **`httpx` → AI** — **`usage_metrics_common`** + gateway-aligned entitlement + **`bill_usage_daily`**; if blocked → **`PAYWALL`** **`wa_outbox`**, batch **`PROCESSED`**, **no** **`/ai/respond`**; otherwise calls **`/ai/respond`** and may enqueue **`AI_REPLY`** only when chat is not **`AGENT_ACTIVE`** and **`ai_paused_until`** is not in the future — blueprint **A5**; **U2 strict** — after a successful AI response, **`action: REPLY`** with urgent **`intent` / `routing_intent`** is normalized to **`HANDOFF`** (`handoff_reason` **`urgent_time_sensitive_u2`**, **`reply_text`** cleared) so the existing HANDOFF path sets **`HUMAN_REQ`** + owner alerts — **no** generic urgent line via **`AI_REPLY`**; **`NEEDS_OWNER_DATA`**: customer **`wa_outbox`** **`AI_REPLY`** uses **`_load_needs_owner_customer_reply_text`** (same **`ai.needs_owner_data_customer_reply`** JSON rules + default as **`ai_engine`** **`NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED`**); otherwise seals **without** AI/outbox; batch text scoped to **`opened_at`…`sealed_at`**; on **`HANDOFF`** / **`NEEDS_OWNER_DATA`** (engine path) sets **`HUMAN_REQ`** / **`WAITING_OWNER_DATA`**, **`handoff_reason`**, **`pg_notify('zy_chat_events', json)`**, and best-effort **`inbox_notifications`** for owners). `outbox_sender.py` (lease-based **`SENDING`** claim, Meta send with retry/fatal/**`DEAD`**, `SENT` only from `SENDING` when `META_ACCESS_TOKEN` set; env: **`META_ACCESS_TOKEN`**, **`META_GRAPH_VERSION`**, optional **`OUTBOX_MAX_ATTEMPTS`**, **`OUTBOX_SENDING_LEASE_SECONDS`**). **`TEMPLATE`** rows: Graph **template** send path (JSON body from **`broadcast_gating.build_template_outbox_body`**); **`dead_at`** set when status → **`DEAD`** (hourly metrics + M7 spike alerts use **`COALESCE(dead_at, created_at)`**). **Chat K — usage + metrics**: Alembic `0005_usage_metrics` (`bill_usage_daily`, `metrics_daily_client`, `metrics_daily_agent`, `metrics_hourly_system`, `worker_usage_cursors`); `usage_increment_worker.py`; `metrics_rollup_worker.py` (hourly rollup now also fills **`billing_webhook_process_errors`** + **`wa_meta_webhook_errors`** when migration **`0010`** is applied). **Chat L — M6/M7**: Alembic **`0010_m6_m7_broadcast_alerts`** (`customer_marketing_opt_in`, `wa_broadcast_campaigns` / `wa_broadcast_targets`, `ops_alert_events`, `bill_webhook_processing_errors`); **`broadcast_campaign_worker.py`** (queued campaigns → **`wa_outbox`** **`TEMPLATE`** with plan + opt-in gates from **`ops_runtime_config`** **`m6.broadcast_policy`**); **`alert_eval_worker.py`** (thresholds from **`alerts.thresholds`** → **`ops_alert_events`** + logs; **no paging** yet). **Coordinate Chat I (M9):** phase-2 **SOP auto-trigger** should **`POST /ops/sops/{id}/run`** (`trigger_type=auto`) when alert types match mapped SOP slugs — **not wired** in this slice; keep **`ops_alert_events`** as the handoff surface (Stem: add slug map key e.g. **`alerts.sop_trigger_map`** later with Chat **I** approval).
- **client_api (M3/M4 + M8 phase-1 dashboards)** (`backend/apps/client_api/`): JWT login, owner/agent/super_admin RBAC, inbox list/detail (**blueprint `inbox_chats.state` + `human_queue` filter + `ai_paused_until`**), assign/reassign/unassign/escalate/**resolve**, **`GET /inbox/notifications`** + **`POST /inbox/notifications/{id}/read`**, typing presence, agent reply (mirrors `inbox_messages` + enqueues `wa_outbox` `AGENT_REPLY`; extends **`ai_paused_until`** from **`ops_runtime_config`**), optional **`Idempotency-Key`** on **`POST /inbox/chats/{id}/reply`**. Assignment flows write **`inbox_assignment_audit`** + **`inbox_notifications`** (assignee + owner CC). **Read-only dashboards (Chat J)** — module **`routes_dash.py`**, OpenAPI tag **`dash`**: **`GET /dash/client/overview`**, **`GET /dash/client/agents`**, **`GET /dash/client/quality`** (**`owner` \| `agent` \| `super_admin`**; **`super_admin`** requires **`?client_id=<uuid>`**); **`GET /dash/admin/overview`**, **`/dash/admin/collections`**, **`/dash/admin/providers/razorpay`**, **`/dash/admin/providers/paddle`**, **`/dash/admin/ops/whatsapp`**, **`/dash/admin/geo`** (**`super_admin`** only); checklist alias **`GET /dash/admin/admin/geo`** (same body as **`/dash/admin/geo`**). **`/dash/client/quality`** “pending” counts chats in **`HUMAN_REQ`** or **`WAITING_OWNER_DATA`**. Billing truth stays **`billing_api`** + core tables — dash **`estimated_mrr_minor_units`** etc. remain placeholders until § M5 “billing tiles” SQL is defined (checklist). **Tests:** **`tests/test_dash_handlers_mocked_db.py`**, **`tests/test_dash_openapi_and_rbac.py`**. **`DBPoller`** also polls **`inbox_notifications`** → WS **`notification`** (no duplicate hub publish from REST). **`/ws`**: optional **`CLIENT_API_WS_ALLOWED_ORIGINS`** Origin allowlist. Env: `CLIENT_API_JWT_SECRET`, `CLIENT_API_JWT_TTL_MINUTES`, `CLIENT_API_EVENT_POLL_MS`, `CLIENT_API_CORS_ORIGINS`, `CLIENT_API_WS_ALLOWED_ORIGINS`.
- **Flutter owner/agent (Chat G)** (`flutter_app/` + **`mobile/`**): **Tenant `HomeShell`** (**`owner`** / **`agent`**) — **Inbox** (filters All / Mine / Unassigned / **Needs human** = **`human_queue`**, phone search, pull-to-refresh, retry, agent hint) + **thread** (assign / reassign / escalate / unassign / **resolve** where RBAC allows; assignment banner; **`ai_paused_until`** on rows; typing + reply gated); **WebSocket** after login **for tenant users only** ( **`connectWebSocket` no-ops for `super_admin`** ); **`SessionController.wsLastError`** + try/catch around connect; snackbar if REST works but WS fails; **`GET /auth/me`** rejects unsupported roles; password cleared on successful tenant login. **`ClientDashboardScreen`** → **`GET /dash/client/overview|agents|quality`** (**401** logout; **404** mock + banner); app bar **Refresh** → **`bumpInboxGeneration()`** + **`bumpDashGeneration()`**. **`mobile`** tenant scoping: **`canUseTenantInboxApi`**, **`superAdminClientId`**, **`_cid(session)`** on inbox REST when **`super_admin`** acts on a chosen client. **`ClientApiRepository`** (`flutter_app` + `mobile`): `listChats` (+ **`human_queue`**), **`listNotifications`** / **`postNotificationRead`**, **`postResolve`**, assignment endpoints, **`dashGet`**. **`super_admin`** login does **not** open tenant **`HomeShell`** — both apps show **`SuperAdminShell`** (next bullet, **Chat H**). **Docs:** `flutter_app/README.md`, `mobile/README.md` (base URLs, **`flutter create`** when `windows/` / `android/` missing). **Smoke:** Stem / Chat N on device.
- **ops_api (M9 SOP Center — Chat I)** (`backend/apps/ops_api/`): **Core REST + Alembic `0006_ops_sops` landed** — dedicated FastAPI app (default local **port 8087**); **Stem choice:** parallel app (not under `client_api`). **Auth:** `Authorization: Bearer <JWT>` from **`POST /auth/login`** on **`client_api`**, **`super_admin` only** (403 otherwise). **DB:** `ops_sops`, `ops_sop_versions`, `ops_run_logs` (`context_json` JSONB; optional `client_id`; `trigger_type` default `manual` as plain **TEXT** in v1). **REST (`ops`):** `GET/POST /ops/sops`, `GET/PUT /ops/sops/{sop_id}`, **`GET /ops/sops/{sop_id}/versions`** (**canonical on `ops_api` only** — **Chat H** consumes; **no** duplicate route on `client_api` or Flutter backends), `POST /ops/sops/{sop_id}/run`, `GET /ops/runs`, `GET /ops/runs/{run_id}`. **`GET /ops/sops/{sop_id}/versions` (v1):** **404** if SOP missing; else **all** `ops_sop_versions` for that SOP **`ORDER BY version_num ASC`** as **`SopVersionOut`**; **no** query pagination; **restore** = **new `PUT`** (append-only). **`GET /ops/runs` (v1):** filters + **`ORDER BY created_at DESC`** + hard **`LIMIT 500`**. **Extensions (gated — not core):** **pagination** beyond the 500 cap, **export** (e.g. PDF), **`trigger_type` / event-type** enums or stricter DB rules, and **auto-trigger** hooks — **only** with **Stem-approved contract** (OpenAPI + Chat **H**/**L** consumers) **and Alembic migrations** if the contract needs schema changes — track in **`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md` § M9 — Still open (ops_api)**. **Chat H JSON** for POST/PUT/run/list: `backend/apps/ops_api/models.py`. Env: **`OPS_API_CORS_ORIGINS`**, shared **`CLIENT_API_JWT_SECRET`**.
- **Flutter (Chat H — SOP Runbook UI)** (`flutter_app/` + **`mobile/`** parity): Super-admin **`SuperAdminShell`** — tabs **SOPs** · **Runs** · **Control** (**`SuperAdminControlPlaneScreen`** — read-only “Needs: …” per checklist § M8/M9; no editors until admin APIs exist) · **Dash** (**`SuperAdminDashScreen`** + **`lib/widgets/dash_bar_charts.dart`**: horizontal bars for `Map<String,int>`, KPI row, stacked **`hourly_system_last_24h`** segments, Raw JSON dialog; matches **`DashAdmin*Out`** from **`GET /dash/admin/*`**); dual bases **`CLIENT_API_BASE_URL`** / **`OPS_API_BASE_URL`** (`dart-define` or in-app link sheet, persisted); `lib/screens/sops/*` + auth helpers (`401` → logout, **`403`** → one-shot “needs **super_admin**”, no retry loop); CommonMark-only Markdown preview (`flutter_markdown` + `markdown`); Android emulator hosts **`10.0.2.2:8085`** / **`:8087`**. Root + per-app READMEs document **Flutter web dev CORS** (`CLIENT_API_CORS_ORIGINS` / `OPS_API_CORS_ORIGINS`, exact origin string).
- **Alembic**: `0001_init_core`, `0002_reliability_queueing`, `0003_wa_trial_map`, `0004_billing`, `0005_usage_metrics`, `0006_ops_sops`, **`0007_wa_meta_webhook_errors`**, **`0008_inbox_blueprint_states`** (blueprint **`inbox_chats.state`**, `inbox_assignment_audit`, `inbox_notifications`, `ops_runtime_config` pause keys), **`0009_billing_kyc_invoices`** (`bill_invoices`, `api_clients` KYC JSON + timestamps), **`0010_m6_m7_broadcast_alerts`** (M6 broadcast + M7 alerts + **`wa_outbox.dead_at`** + hourly metrics columns); `backend/alembic.ini` uses `%(here)s/migrations`.
- **Dev helpers**: `backend/tools/dev_seed.py`, `dev_send_inbound.py`, `dev_check.py`, **`dev_e2e_smoke.ps1`** (full local smoke: alembic + seed + inbound + debounce wait + batch/outbox retries + `dev_check`; needs gateway **8081** + AI **8083**), **`dev_run_pipeline_tail.py`** (sleep + batch retries + outbox retries; `--skip-outbox` optional), `dev_seed_users.py` (owner/agent; optional **`--super-admin-email`** for **`ops_api`** / Flutter super-admin smoke), `dev_inbox_smoke.py` (drives the assign flow + watches WS without Flutter), **`dev_ops_api_smoke.py`** (httpx: `client_api` login → **`ops_api`** CRUD + run against live **8085/8087**; needs a **`super_admin`** — use `dev_seed_users.py --super-admin-email …` or a manual DB row; see stem note below).
- **Tests + CI**: `tests/` — `pytest` (payloads, billing signatures, **M1 / Chat D** `tests/test_ai_respond_logic.py` + `tests/test_ai_engine_api.py` + **`tests/test_llm_pipeline.py`** + **`tests/test_ai_respond_golden.py`**, **ops_api** OpenAPI/RBAC + mocked DB handlers: `tests/test_ops_api_openapi_rbac.py`, `tests/test_ops_api_handlers_mocked_db.py`, **Chat J** **`/dash/*`**: `tests/test_dash_handlers_mocked_db.py`, `tests/test_dash_openapi_and_rbac.py`, **Chat K** `tests/test_usage_thresholds.py`, **Chat B** `tests/test_wa_gateway_no_ai.py` + `tests/test_wa_gateway_meta_helpers.py`, optional **Postgres integration** `tests/test_postgres_integration_optional.py` when `RUN_POSTGRES_INTEGRATION=1` + `DATABASE_URL`, optional live gateway when `RUN_WA_GATEWAY_E2E=1`). GitHub Actions **`.github/workflows/ci.yml`** (Ubuntu, Python **3.12**) runs **`python -m pytest tests/ -q`** with **`PYTHONPATH=${{ github.workspace }}`** on push/PR to **`main`** / **`master`** — **no** Postgres service in CI yet (comment only for future E2E). **M10 / Chat M** target: add Postgres **service** job, **integration + contract** jobs, optional **`RUN_WA_GATEWAY_E2E`** job; after workflow topology changes, **Chat N** **full** README smoke.
- **README**: **Copy-paste PowerShell command reference** (blocks A–K), **10-step staging smoke**, **Sequential follow-through** (WhatsApp delivery, quality notes, Flutter, CI), local dev paths.

## M1 — `POST /ai/respond` contract (Chat C coordination)

- **Request JSON** (`batch_processor` → `httpx.post`): `client_id`, `chat_id`, `batch_id`, `customer_phone`, `batch_text` only. **`AIRequest`** uses **`extra="forbid"`** — any new field requires **Stem + Chat C** to extend the worker payload and this section.
- **Chat D / Chat C boundary:** **`Chat D`** implements **`POST /ai/respond`** under **`backend/apps/ai_engine/`** only — **no** worker edits there. **`Chat C`** owns **`backend/workers/batch_processor.py`** policy (**U2** normalization after AI response, **second-line paywall** before the AI HTTP call, **`NEEDS_OWNER_DATA`** customer **`wa_outbox`** copy) while keeping the **same five-field** JSON POST and the **same response keys** consumed by the worker unless **Stem + Chat C + this section** extend the contract.
- **Response JSON** (`r.json()`): `action` (`REPLY`|`HANDOFF`|`NEEDS_OWNER_DATA`), `reply_text`, `intent`, `routing_intent`, `confidence`, `language`, `handoff_reason`, `missing_fields`, `risk_reason`. **`AIResponse`** also **`extra="forbid"`**. **Chat C** branches on `action` and reads `reply_text` / `handoff_reason` / `risk_reason` for inbox state + outbox.
- **Optional LLM spend:** Env **`AI_LLM_BASE_URL`**, **`AI_LLM_API_KEY`**, **`AI_LLM_PRIMARY_MODEL`**, **`AI_LLM_JUDGE_MODEL`** (see **`backend/shared/config.py`**, **`backend/.env.example`**). Ops keys **`ai.fallback.enabled`**, **`ai.fallback.use_judge`**, **`ai.fallback.quality_threshold`**, **`ai.fallback.max_primary_tokens`**, **`ai.fallback.max_judge_tokens`**. OpenAI-compatible **`/chat/completions`** only. LLM applies to the default **general** acknowledgement path; failures fall back to the deterministic **REPLY** (no extra **HANDOFF** from the engine for a bad model).
- **Golden fixtures:** `tests/golden/ai_respond/` exercised by **`tests/test_ai_respond_golden.py`**.

## Stem sequencing — next module chats (2026-05-14)

**Single migration / shared-contract owner:** Chat **A** approves order before any overlapping Alembic or JWT/API contract edits land together.

| Order | Chat | Rationale |
|-------|------|-----------|
| 1 | **N** | **Ongoing:** keep **`python -m pytest tests/`** green on every merge; extend smoke docs / contract tests as Stem points; no schema ownership. A **Chat N doc/harness slice** can be “done” without optional Postgres or device smoke **having been run** on Stem’s machine — see **Stem note — Chat N (scope vs evidence)**. |
| 2 | **B** | **M2 slice landed:** paywall / trial / churned / urgent / adaptive / **`PAYWALL`** outbox + **`0007`** meta errors + **`WA_GATEWAY_ALLOW_CLIENT_ID_HEADER`**. **Chat C** mirrors paywall read for **legacy OPEN** batches before AI (**second-line**). **Follow-ups:** staging/load proof. |
| 3 | **C** | **Workers — batch path:** **A5**; **`HUMAN_REQ` / `WAITING_OWNER_DATA`** + notifications; **U2 strict** (urgent **`REPLY`** → **`HANDOFF`**); **`NEEDS_OWNER_DATA`** customer **`wa_outbox`** aligned with **`ai_engine`**; **second-line `PAYWALL`** before **`/ai/respond`**; sealed window; **`outbox_sender`** reliability (**`DEAD`** / lease). **Still:** **DEAD** surfacing in product UI (**§ M7** / **Chat L**). |
| 4 | **F** | **M4 blueprint inbox slice landed** (`0008`, resolve, notifications REST + read, **`human_queue`**, WS **`notification`** + **`CLIENT_API_WS_ALLOWED_ORIGINS`**, assignment audit). **M3** (signup/OTP/team/catalog) **deferred** until product re-opens scope (checklist § M3). **Follow-ups:** pagination, **`LISTEN`** bridge, typing **hard lock**, dedicated notifications **UI** (API exists). |
| 5 | **E** | **M5 — Chat E slice landed + pytest-green** (`billing_api` webhooks + REST + **`0009`** + gateway lateral gating). **Not** “M5 blueprint complete” — see **Stem note — Chat E** + checklist § M5 **Still open** (KYC verify, pricing UX, disputes, **`/dash/admin`** billing tiles via **Chat J**). |
| 6 | **D** | **M1 — Chat D slice landed** (deterministic + optional **LLM/judge**, **`ai.fallback.*`**, **Hinglish**, golden fixtures). **Next:** blueprint **input** bundle; per-client **budget** metering; optional OpenAPI contract CI (**Chat N**). **Contract:** HANDOFF **M1 — `POST /ai/respond` contract** + **Chat C** for any **`AIRequest`/`AIResponse`** field changes. |
| 7 | **L** | **M6/M7 — slice landed:** **`0010`**, campaign worker + alert eval + billing failure rows + **`ops_alert_events`**; **still:** product UI for opt-in/campaigns, pager channels, extra alert types. **Coordinate I:** M9 phase-2 auto-trigger consumes **`ops_alert_events`** (or a view) + **`POST /ops/sops/{id}/run`** — Stem sequences contract with **Chat I**. |
| 8 | **M** | **M10:** **`/ops/releases*`** (gated releases) + CI (**Postgres service**, **integration/contract** jobs, optional **`RUN_WA_GATEWAY_E2E`**) + **manual approval hooks** doc for **AI / routing / billing** — after pytest baseline is reliable (**N**); **Chat N** **full smoke** when CI workflow shape changes. |

**Parallel (non-migration):** **Chat H** — **super-admin dash charts landed**; **M8** interactive editors still need admin APIs; **Chat I** ops extensions — no Alembic unless Stem opens a new revision window.

**Device smoke (cannot run inside Cursor agent reliably):** **G** owner/agent + **H** super-admin on **Windows + Android** — **Stem / Chat N / you** on a dev machine: `flutter pub get`, `dart analyze`, then README / HANDOFF smoke paths (`dev_inbox_smoke.py`, optional `dev_ops_api_smoke.py` with a real **`super_admin`** user).

## Known gaps / next work (pick one module per chat)

1. **M2 Gateway**: ~~trial map + routing~~ **landed** (`0003_wa_trial_map`). **2026-05-14 slice:** adaptive debounce + **U1** urgent (`ai.urgent_bypass_substrings` + `routing.urgent_substrings`), trial/churned + **usage hard_block** gate (reads `bill_usage_daily` + `usage.daily_inbound_limits` per Chat K), **`PAYWALL`** outbox enqueue (skips OPEN batch so Chat C does not AI-reply), optional **`POST /webhooks/meta/errors`** → `wa_meta_webhook_errors` (**`0007`**). **`X-ZY-Client-Id`:** explicit **`WA_GATEWAY_ALLOW_CLIENT_ID_HEADER=true`** (Settings) — default **off**. **Chat C** **second-line paywall** on **legacy OPEN** batches before **`/ai/respond`** (**landed**). Follow-ups: device/staging verification under load.
2. **M1 AI**: **Chat D — slice landed** — deterministic routing + optional **OpenAI-compatible LLM** (env **`AI_LLM_*`**) gated by **`ops_runtime_config`** **`ai.fallback.*`** (enabled, judge, thresholds, token caps); **Hinglish** `language` tag + prompts; local **quality gate** + optional **judge** JSON; failures → deterministic **REPLY**. **Golden / contract:** `tests/golden/ai_respond/`, **`tests/test_ai_respond_golden.py`**. **Contract doc:** HANDOFF **M1 — `POST /ai/respond` contract (Chat C coordination)**. **Follow-ups:** full blueprint **input** bundle (history, personas, catalog, rules); richer multilingual scoring; per-client rate / budget enforcement beyond token caps (**Chat N** / Stem).
3. **M4 Inbox / client_api**: **Blueprint slice landed** (`0008`, resolve, notifications REST + WS poller, assignment audit, `ai_paused_until`, `CLIENT_API_WS_ALLOWED_ORIGINS`, Flutter filters). Follow-ups: **in-process `LISTEN zy_chat_events`** (or bridge) to reduce **`DBPoller`** latency; per-chat pagination cursors; stricter WS/session binding if product requires it.
4. **M5 Billing**: **Stem wording:** **Chat E** slice (**`billing_api`** + **`0004`/`0009`** + gateway **DB-only** gating) is **landed** and **pytest-green**; full **blueprint § M5** is **not** closed — follow-ups remain in checklist **§ M5 — Still open** (see **Stem note — Chat E (scope vs blueprint M5)**). **Shipped in this slice:** webhooks, REST (checkout, subscription, invoices, **KYC submit**), extended events, **`/dash/*`** coordination doc (**Chat J** read-only). **Follow-ups:** KYC **verification** workflow; control-plane **pricing** UX; chargebacks/disputes webhooks if required; **`/dash/admin/*`** revenue/MRR-style tiles when aggregates are defined.
5. **Flutter**: **Chat G** — checklist **§ Owner/agent Flutter (Chat G)** **all `[x]`** (**tenant** **`HomeShell`**: inbox + WS + **`GET /dash/client/*`**); **Chat H** — **`super_admin`** **`SuperAdminShell`**. **Verification:** device smoke (**Stem / Chat N / you**) — README + **Stem note — Chat N**, not an open row under § Chat G. **Follow-ups:** richer tenant charts / **`/dash/client/*` phase-2** → **Chat J** + Stem; **deep links** → **Chat L**; **M8** super-admin editors → admin APIs (**Chat H** checklist).
6. **M10 Release**: **Basic CI** (pytest only) in `.github/workflows/ci.yml` on **`main`/`master`** push/PR. **Chat M — documentation / coordination slice done** (scope, target CI, approval hooks, **Chat N** after CI topology changes, checklist § M10 + **Meta**, **HANDOFF**, **README §4**). **Still open (engineering):** **`GET/POST /ops/releases*`** on **`ops_api`** — register build + **test report hash**, **promote**, **rollback**, audit fields, **super_admin** gate. **CI follow-ups:** Postgres **`services:`** job (**`alembic upgrade head`** + **`RUN_POSTGRES_INTEGRATION=1`**), dedicated **contract** job(s), optional **`RUN_WA_GATEWAY_E2E=1`** job with secrets off by default. **Process:** **manual approval hooks** for **`ai_engine/`**, **`wa_gateway/`**, **`billing_api/`** are **documented**; GitHub **Environments** / **CODEOWNERS** / **branch protection** = Stem configures org. **Coordination:** when **Chat M** changes **CI job shape** (new jobs, services, matrices), **Chat N** runs **full** README smoke (**10-step** + documented optional worker / Flutter gates) as merge evidence for that PR.
7. **M9 (post–Chat I — for Chat A)**: **`ops_api` v1 + Chat H UI landed** (library/detail/editor/versions+diff+restore/runs vs **`ops_api`**; **M8** read-only **Control** coordination copy + **`/dash/admin/*`** chart reader on **`client_api`**). **Chat I session done** for **v1 baseline**; **`GET /ops/runs`** still hard **`LIMIT 500`** — **pagination / export / stricter `trigger_type` / auto-trigger hooks** = checklist **§ M9 — Still open (ops_api)** + Stem contract. **Stem follow-ups:** (a) ~~add **`super_admin`** to dev seed path~~ **`dev_seed_users.py --super-admin-email`** (same `--client-id` as tenant); (b) optional **Postgres-backed** pytest or CI job for `ops_api` SQL paths; (c) reconcile external blueprint DDL names vs repo if v6.x differs; (d) ~~**`GET /ops/runs` hard cap 500**~~ see **§ M9 — Still open (ops_api)** → **runs pagination** row; (e) ~~**`mobile/`** parity~~ **done** (synced with `flutter_app` Chat H tree; run `flutter pub get` + `dart analyze` + **Windows + Android** smoke locally); (f) phase-2 **auto-trigger** runs + day-1 SOP seed content per checklist — **Chat L** now lands **`ops_alert_events`** as the intake surface; wire **`POST /ops/sops/{id}/run`** (`trigger_type=auto`) with **Chat I** + Stem (`alerts.sop_trigger_map` TBD).
8. **Chat K tests**: **`tests/test_usage_thresholds.py`** covers **`usage_metrics_common`** helpers (no DB). **Optional Postgres integration:** **`tests/test_postgres_integration_optional.py`** exercises **`usage_increment_worker.run_once`**, **`metrics_rollup_worker.run_once`** (including **`metrics_daily_*`** and a **`metrics_hourly_system`** row for the current UTC hour), **Chat K** public table presence, and minimal **`ops_*`** checks when **`RUN_POSTGRES_INTEGRATION=1`** + **`DATABASE_URL`** + migrations at head — see README and HANDOFF **Usage & metrics workers**; default **`python -m pytest tests/`** omits that module via **`tests/conftest.py`**. **Stem:** optional integration is **documented harness only** until someone runs it with a **valid** `DATABASE_URL` and sees **pass** — wrong password / DB down is **not** a Chat N failure; see **Stem note — Chat N (scope vs evidence)** below.

## Stem note — Chat N (scope vs evidence)

Use this so “**Chat N done**” is not misread as “every optional gate was executed and proven.”

| Topic | Policy |
|------|--------|
| **Chat N “done”** | Means **deliverables in tree** (default **`python -m pytest tests/`** path, README smoke / optional-env docs, **`conftest.py`** collection rules, optional integration **module** when present). It does **not** mean Stem or CI has **log evidence** for every optional path unless someone recorded a run. |
| **Optional Postgres** (`RUN_POSTGRES_INTEGRATION=1` + **`DATABASE_URL`**) | **Not required** to call Chat N “shipped.” A run that **fails** (bad URL, wrong password, Postgres not running) proves nothing about code quality — **skip** or fix env and re-run. Treat as **verified** only after a deliberate run with a **valid** URL, **migrations at head**, and the optional tests **pass** (e.g. all cases in that file green). |
| **`dart analyze` + G/H device smoke** | **Documented** in README / HANDOFF as the **manual** gate when a change touches **Flutter** behavior or UX. **Execution** stays on **Stem / you** when relevant for merge — same as prior HANDOFF policy; not a checkbox “completed by Chat N” in the automation sense. |

## Stem note — Chat E (scope vs blueprint M5)

**Practical Stem wording:** the **Chat E** slice (**`billing_api`** + Alembic **`0004`/`0009`** + **gateway DB-only** entitlement gating + **`tests/test_billing_*.py`** green in CI) is **landed**. Do **not** say “**M5 / Chat E** is finished forever” against the full blueprint.

| Topic | Policy |
|------|--------|
| **“Chat E done”** | Means the **coded + verified** slice: signed **webhooks**, **REST** (checkout, subscription, invoices, **KYC submit**), migrations, gateway **Postgres-only** gating, docs/checklist alignment, **billing pytest** passing. |
| **Blueprint § M5 remainder** | Stays **open** in **`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md` § M5 — Still open** — e.g. **KYC verification** (admin approve/reject, **`kyc_verified_at`**, notifications) beyond submit/store; **checkout / pricing UX** tied to **`bill_plans` + `ops_runtime_config`** beyond pass-through provider calls; **extra webhook** cases (chargebacks/disputes) if product wants them; **`/dash/admin/*`** billing-style aggregates (**Chat J**, read-only, SQL from DB when defined). |

## Stem note — Chat I extras (Chat A analysis)

Work **beyond** the original Chat I paste block (document here so Stem sequences merges and assigns follow-ups):

**Extension gate (Stem — Chat A):** **`0006_ops_sops`** + core **`/ops/*` REST** are **landed**. Anything beyond v1 behavior — **`GET /ops/runs` pagination** past the **500** cap, **export** (e.g. PDF), **`trigger_type` / event-type** enums or DB **`CHECK`**, **auto-trigger** from alerts/workers — ships **only** with a **Stem-approved API contract** (OpenAPI + notes for **Chat H** / **Chat L**) **and new Alembic migrations** when the contract requires schema changes. **`GET /ops/sops/{id}/versions`** stays **canonical on `ops_api` only**; **Chat H** is a consumer, not a second source of truth.

**Chat I session (2026-05-14):** marked **done** — **v1 `ops_api` baseline** in tree (no additional extension routes merged in this bookkeeping pass). Next **`ops_api`** work = checklist **`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md` § M9 — Still open (ops_api — Chat I + Stem)** rows, each behind the extension gate above.

| Item | Detail |
|------|--------|
| **`GET /ops/sops/{sop_id}/versions` policy** | **Canonical `ops_api` only** — **Chat H consumes**; no shadow route elsewhere. **v1 (implemented):** **`super_admin`** JWT; **404** if SOP not found; **full** `ops_sop_versions` list **`ORDER BY version_num ASC`** as **`SopVersionOut`**; **no** query pagination; **restore** = **new `PUT`** (append-only). **Scale / contract changes** = extension gate above + checklist **§ M9 — Still open (ops_api)**. |
| **`GET /ops/runs` (v1)** | **`ORDER BY created_at DESC`**, hard **`LIMIT 500`** with filter query params as shipped. **Pagination / cursor** = same checklist **Still open** row (coordinate Chat **H** infinite-scroll contract). |
| **`trigger_type` / auto-trigger** | Request body allows `manual` \| `auto` \| `scheduled` \| `other` at API layer; **DB** remains plain `TEXT`. **Stricter allowlist / `CHECK` / alert-specific values** + **worker → `POST .../run`** idempotency = checklist **§ M9 — Still open (ops_api)** + phase-2 **Auto-trigger wiring** row. |
| **Export (PDF / print)** | Product optional; tracked checklist **§ M9 — Still open** + **Optional** PDF row. |
| **`ops_sop_versions` table** | Checklist text originally named `ops_sops` + `ops_run_logs` only; implementation added **`ops_sop_versions`** for immutable Markdown per version (PUT always appends). If external blueprint DDL used a single-table design, align or document deviation. |
| **`backend/tools/dev_ops_api_smoke.py`** | Live **httpx** smoke: `POST /auth/login` on **client_api** → bearer calls on **ops_api** (create SOP, GET, PUT, POST run, list/get runs). **Does not create users** — seed **`super_admin`** via **`dev_seed_users.py --super-admin-email …`** (same `--client-id` as owner/agent) or a manual `api_users` row. |
| **Automated tests** | `tests/test_ops_api_openapi_rbac.py` (OpenAPI paths + 403 for owner/agent); `tests/test_ops_api_handlers_mocked_db.py` (mocked `engine`, no Postgres). **Verified green** on Windows / Python 3.13 (7 tests). |
| **Shared config** | `backend/shared/config.py`: **`ops_api_cors_origins`** (env **`OPS_API_CORS_ORIGINS`**); `backend/.env.example` updated. |
| **Not done (intentional)** | No Postgres service job in CI for `ops_api`; no README “10-step” line-item unless Stem adds it. **`super_admin` dev seed:** optional **`--super-admin-email`** / **`--super-admin-password`** on `dev_seed_users.py` (2026-05-14). |

**Suggested Stem actions:** ~~extend `dev_seed_users.py` with optional `--super-admin-email`~~ **done**; ~~README one-liner for `dev_ops_api_smoke.py`~~ **done** (README *Client API* section); schedule Chat H against `http://127.0.0.1:8087` OpenAPI; **Extension gate** applies to every **§ M9 — Still open (ops_api)** row (contract + migrations before implementation); sequence **Chat L** ↔ **Chat I** for auto-trigger after contract.

## Stem note — Chat H wrap-up (main stem / Chat A)

Use this block to sequence verification, checklist ticks, and any contract decisions.

| Topic | Status / note |
|------|----------------|
| **§ M9 interactive UI** (`flutter_app/`) | Shipped: SOP library (search, category, status), detail + **CommonMark-only** Markdown preview, create/edit (POST/PUT, client-side slug `^[a-z0-9][a-z0-9_-]*$`), **version list + line diff + restore-via-editor**, start run (`context_json`: key/value + raw JSON, validate before POST), run list (filters + **500-row** server cap UX + date filters) + run detail. |
| **§ M8 control plane (Flutter)** | **`SuperAdminControlPlaneScreen`:** per-panel “Needs: …” aligned with checklist (runtime config + audit, pricing, debounce, urgent, AI fallback) + explicit **no GET/PUT admin routes → no Flutter editors**; **no** invented POSTs. **M9** phase-2 / day-1 seed / PDF called out as **Stem + Chat I + Chat L** (no deep links yet). |
| **§ Chat J (`/dash/admin/*`)** | **SuperAdminShell → Dash** tab: lazy-load JSON per endpoint; **KPI chips + horizontal bar charts** for string→int dicts (entitlement, outbox, billing, WA ops, geo) + **stacked bar** for `hourly_system_last_24h` message totals; **Raw JSON** dialog; empty metrics OK; **`401`** on `client_api` → logout. |
| **`mobile/`** | **Parity with `flutter_app` Chat H** (same `lib/` additions, `SessionController` + `ClientApiRepository.dashGet`, `SuperAdminShell`, removed legacy **`SuperAdminOpsScreen`**). **`mobile/README.md`** updated (dual bases, CORS, run commands). |
| **Auth / errors** | Every **`ops_api`** call: `Authorization: Bearer <access_token>`. **`401`** → return to login; **`403`** → clear “needs **super_admin**” (no retry loop). Tokens not logged. |
| **Backend contract** | **`GET /ops/sops/{sop_id}/versions`** is **canonical `ops_api` only** (Chat **I**); **Chat H** consumes — **no duplicate** on **`client_api`**. **v1 policy:** see **Stem note — Chat I extras** (404, full ASC list, `SopVersionOut`, append-only restore). **Extensions** (pagination past 500, export, enums/event types, auto-trigger): **Stem-approved contract + migrations** only — same stem note **Extension gate**. **`GET /ops/runs`:** `LIMIT 500` until pagination ships under that gate. |
| **Smoke acceptance** | Intended path: **super_admin** login → create SOP → detail → edit/save → start run with sample `context_json` → list runs → open run detail on **Windows + Android**. **Not re-run inside Cursor agent shell** in the last pass — **Stem / Chat N / you on a dev machine** should run `flutter pub get`, `dart analyze`, and this smoke after pulling. |
| **Checklist** | `docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md` § M9 reflects shipped **Flutter + ops_api**; **§ M9 — Still open (ops_api)** lists backend follow-ups (**auto-trigger hooks**, **runs pagination**, **stricter `trigger_type`**, **versions at scale**, **export**). § M8 super-admin dash charts **`[x]`** (Chat H); § M8 interactive control-plane rows **open** until admin APIs; Stem owns further ticks when merging. **Chat N** can add the same flow to automated smoke docs if desired. |

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

# M6/M7 (Chat L): broadcast campaign queue → TEMPLATE outbox; alert thresholds → ops_alert_events (needs migration 0010)
python backend\workers\broadcast_campaign_worker.py
python backend\workers\alert_eval_worker.py

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

**Optional automated verification (Postgres):** with **Alembic at head** on the target DB, set `RUN_POSTGRES_INTEGRATION=1` and `DATABASE_URL`, then:

```powershell
python -m pytest tests/test_postgres_integration_optional.py -v
```

That module exercises Chat K `run_once()` paths (``bill_usage_daily``, ``metrics_daily_*``, ``metrics_hourly_system``) plus minimal ``ops_*`` sanity; it is **omitted** from default `python -m pytest tests/` unless both env vars are set (`tests/conftest.py`). See README *Optional Postgres integration*.

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

3. **Hard usage block (Chat B — landed in gateway):** when **`inbound_customer_messages_today_utc >= hard_block`** (per plan JSON), the gateway **skips OPEN batch** and enqueues **`wa_outbox`** **`PAYWALL`** (see “What is implemented” WA Gateway bullet). **Soft warn** only: owner/dashboard signal (**`soft_threshold_crossed_at`** / **`hard_threshold_crossed_at`** on **`bill_usage_daily`**) remains Chat **K** worker behavior.

**Coordinate:** Chat **E** owns subscription write path (**webhooks** + **`billing_api`** REST) on **`api_clients`**, **`bill_subscriptions`**, **`bill_invoices`**, **`bill_events`**; gateway **plan gating** reads **Postgres only** (latest **`bill_subscriptions.status`** via lateral join + **`api_clients.entitlement_plan`** / **`trial_end`**, **`bill_usage_daily`**, **`usage.daily_inbound_limits`**) — **no live Razorpay/Paddle calls** in the hot path. Chat **J** **`/dash/*`** is **read-only**; it must not become a second source of billing truth.

## Billing (M5 layout)

**Choice:** dedicated FastAPI app `backend/apps/billing_api/` (default **port 8086**), parallel to `client_api` (8085), so provider webhook signing and raw-body verification stay separate from Meta WA webhooks and JWT APIs.

**Webhook URLs** (no version prefix; configure these in Razorpay / Paddle dashboards for your deployed host):

| Provider | Method | Path |
|----------|--------|------|
| Razorpay | `POST` | `/webhooks/razorpay` |
| Paddle Billing | `POST` | `/webhooks/paddle` |

**REST** (same **`Authorization: Bearer`** JWT as `client_api` login; **`CLIENT_API_JWT_SECRET`** must match):

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/billing/razorpay/create-checkout` | Server-side Razorpay **Order** (`BILLING_RAZORPAY_KEY_ID` / `SECRET`) |
| `POST` | `/billing/paddle/create-checkout` | Server-side Paddle **transaction** create (`BILLING_PADDLE_API_KEY`, env `sandbox`/`production`) |
| `GET` | `/billing/subscription` | `api_clients` + latest `bill_subscriptions` |
| `GET` | `/billing/invoices` | `bill_invoices` (from webhooks / provider events) |
| `POST` | `/billing/kyc/india` | Stores **`kyc_india_json`**, **`kyc_submitted_at`**; response **`200`** + **`{"ok": true}`** |

**Linking to `api_clients`:** Razorpay subscription payloads must include `notes.client_id` (UUID string). Paddle subscription payloads must include `custom_data.client_id`. Optional `bill_plans` rows map `external_plan_id` → `plan_code`; otherwise set `notes.entitlement_plan` / `custom_data.entitlement_plan` to `trial` \| `starter` \| `growth` \| `pro` \| `churned` when needed.

**Idempotency:** `bill_events` unique `(provider, provider_event_id)`; duplicate deliveries return JSON `{"status":"duplicate"}` and do not re-apply `api_clients` updates.

**Manual / sandbox calls:** README section *Billing (M5)* — PowerShell + `curl.exe` examples with a small Python helper to compute `X-Razorpay-Signature`.

## Multi-chat workflow

| Chat | Role | Scope (primary paths) | Starts with |
|------|------|----------------------|-------------|
| **A — Stem** | Integration lead; sequencing; merge gates; **full control** | No large feature work unless unblocking; owns [`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`](docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md) check-offs when merging | This file + git status + checklist |
| **B** | M2 gateway — **slice landed** | `backend/apps/wa_gateway/`, **`0007_wa_meta_webhook_errors`** | This file + checklist § M2 + Known gaps §1 follow-ups |
| **C** | Workers (batch + outbox) | `backend/workers/batch_processor.py`, `outbox_sender.py`, worker config | This file + checklist § Workers (**goal** paragraph + rows) |
| **D** | M1 AI — **slice landed** (deterministic + optional LLM) | `backend/apps/ai_engine/`, `backend/shared/config.py` ( **`AI_LLM_*`** only), golden tests | This file (**M1 contract**) + checklist **§ M1** |
| **E** | M5 billing — **Chat E slice landed** | `backend/apps/billing_api/`, **`0004_billing`**, **`0009_billing_kyc_invoices`** | This file + checklist § M5 (**Landed** vs **Still open**) + **Stem note — Chat E** |
| **F** | M3/M4 **client_api** — **M4 inbox slice landed** | `backend/apps/client_api/`, **`0008_inbox_blueprint_states`** | This file + checklist § M4 (+ § M3 deferral) |
| **G** | Flutter **client (tenant)** — **landed** | `flutter_app/` + `mobile/` **`HomeShell`** for **`owner`** / **`agent`**: inbox + WS + **`GET /dash/client/*`**. **`super_admin`** → **`SuperAdminShell`** (SOP / Runs / Control / admin dash) = **Chat H** in the same apps | This file + checklist **§ Owner/agent Flutter (Chat G)** + § M8 client dashboard line |
| **H** | Flutter **super-admin** — **landed** | `flutter_app/` + `mobile/` **`SuperAdminShell`**, `lib/screens/sops/*`, **`SuperAdminDashScreen`**, **`SuperAdminControlPlaneScreen`**, **`lib/widgets/dash_bar_charts.dart`**, dual **`CLIENT_API_BASE_URL`** + **`OPS_API_BASE_URL`**; **device smoke** = Stem / Chat N / you | This file + checklist § M8 + § M9 |
| **I** | Backend **SOP Center** — **v1 landed** | `backend/apps/ops_api/`, Alembic `0006_ops_sops`, `GET/POST /ops/sops`, `GET/PUT /ops/sops/{id}`, **`GET /ops/sops/{id}/versions`**, `POST /ops/sops/{id}/run`, `GET /ops/runs` (**`LIMIT 500`**), `GET /ops/runs/{run_id}` (super_admin JWT from `client_api`); extensions → checklist **§ M9 — Still open (ops_api)** | This file + checklist § M9 |
| **J** | Backend **dashboard APIs** — **phase-1 landed** | `backend/apps/client_api/routes_dash.py` (+ dash `models.py`); prefix `/dash`; **`tests/test_dash_*.py`** | This file + checklist **§ M8 — APIs (backend)** + **§ M8 — Phase-2 — `/dash/*`** |
| **K** | Workers **usage + metrics** — **landed** | **`0005_usage_metrics`**, **`usage_increment_worker.py`**, **`metrics_rollup_worker.py`**, **`usage_metrics_common.py`**; **`tests/test_usage_thresholds.py`**; optional **`tests/test_postgres_integration_optional.py`** (Chat K `run_once` paths) | This file + checklist **§ Workers** (usage/metrics); **CI Postgres** = **Chat M** |
| **L** | M6 + M7 — **backend slice landed** | **`0010_m6_m7_broadcast_alerts`**, `broadcast_campaign_worker.py`, `alert_eval_worker.py`, `broadcast_gating.py`, `ops_alerts.py`; **`billing_api`** webhook failure rows + alerts | This file + checklist § M6 + § M7 |
| **M** | M10 release + CI | **`/ops/releases*`** (register + test hash, promote, rollback), CI Postgres + integration + contract + optional E2E, manual approval hooks for AI/routing/billing; **Chat N full smoke** after CI topology changes | This file + checklist § M10 + meta |
| **N** | QA / staging | Pytest, smoke checklists, staging verification (deliverables vs manual gates: HANDOFF **Stem note — Chat N (scope vs evidence)**) | This file + `tests/` + README smoke |

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

### Chat B — M2 WhatsApp Gateway *(routing + paywall slice **landed** — extend with Stem)*

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M2 + Known gaps §1 (M2 follow-ups).
Then read and modify only:
- backend/apps/wa_gateway/main.py
- backend/apps/wa_gateway/meta_payload.py
- backend/apps/wa_gateway/status_payload.py
- backend/migrations/versions/ (new migration only if Stem approves)

**Landed (Chat B):** `wa_numbers` + `wa_trial_map` routing; **`WA_GATEWAY_ALLOW_CLIENT_ID_HEADER`** for **`X-ZY-Client-Id`** (default off); trial/churned/**usage hard_block** gate (reads **`bill_usage_daily`** + **`usage_metrics_common`** + **`ops_runtime_config`**); skips **OPEN** batch when blocked; **`PAYWALL`** **`wa_outbox`** + customer copy + **`m2.service_inactive_customer_reply`**; adaptive debounce + urgent U1; dedupe **RETURNING** empty → **continue**; never AI in webhook (docstring + **`test_wa_gateway_no_ai.py`**); **`POST /webhooks/meta/errors`** + **`0007`**; tests **`test_wa_gateway_meta_helpers.py`**.

**Follow-ups (Stem assigns):** load/staging verification; SQL audit if new queries.

Acceptance for new work: contract tests + `dev_send_inbound` / optional `RUN_WA_GATEWAY_E2E` notes in README.
```

### Chat C — Workers (batch + outbox reliability)

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § Workers (batch_processor, outbox_sender).

Goal — delivery correctness + blueprint alignment:
- Idempotent sends, backoff, DEAD, crash-safe retries (outbox).
- Batch behavior per blueprint A5 (pause AI path when agent active / ai_paused).
- Batch text scoped to the sealed window (opened_at..sealed_at), not loose rolling time windows.

Coordinate: With Chat B if enqueue vs paywall interacts. Do not expand into Chat K worker files (usage_increment_worker, metrics_rollup_worker, etc.) unless Stem assigns overlap.

**Landed (reliability + batch policy):** sealed-window batch text; outbox lease/SENDING, Meta error split, DEAD after max attempts, SENT idempotency from SENDING; **U2 strict** after `/ai/respond` — urgent `REPLY` → `HANDOFF` (`urgent_time_sensitive_u2`, `reply_text` cleared) → `HUMAN_REQ` + owner alerts — **no** generic urgent `AI_REPLY`; **`NEEDS_OWNER_DATA`** customer `wa_outbox` `AI_REPLY` via `_load_needs_owner_customer_reply_text` (same rules as `ai_engine` + `NEEDS_OWNER_DATA_CUSTOMER_REPLY_FIXED`); **second-line paywall** before `httpx` → AI (`second_line_paywall_block`, `usage_metrics_common`, gateway-aligned entitlement) → `PAYWALL`, batch `PROCESSED`, **no** AI when blocked. **Tests:** `tests/test_batch_processor_policy.py`.

Then read and modify only (unless Stem widens scope):
- backend/workers/batch_processor.py
- backend/workers/outbox_sender.py
- backend/shared/config.py (only if new env keys)

**Next (Stem assigns):** DEAD surfacing in owner/super-admin UI (**§ M7** / **Chat L**); any further batch/AI contract changes with **Chat D** + HANDOFF M1 section.

Acceptance: `python -m pytest tests/ -q` green; PowerShell worker run documented on PR.

Give PowerShell: workers + dev_check.py; optional dev_e2e_smoke.ps1 when gateway 8081 + AI 8083 are up.
```

**Status:** Chat C **batch-path slice done** — checklist **§ Workers** rows for **U2**, **NEEDS_OWNER** customer **`wa_outbox`**, and **second-line paywall** are **`[x]`**; **`outbox_sender`** unchanged in this slice.

### Chat D — M1 AI Engine *(LLM slice **landed** — extend with Stem)*

```text
@HANDOFF.md Read first (incl. **M1 — POST /ai/respond contract**). @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M1 (Landed vs Still open).

**Landed (Chat D):** `POST /ai/respond` — **`REPLY` \| `HANDOFF` \| `NEEDS_OWNER_DATA`**; stable JSON for **`batch_processor`** (`routing_intent`, **`language`** `en`|`hi`|`hinglish`|`auto`, …; Pydantic **`extra="forbid"`**). Deterministic routing + **optional** OpenAI-compatible **LLM + judge** (env **`AI_LLM_*`**) gated by **`ops_runtime_config`** **`ai.fallback.*`**. Helpers: **`backend/apps/ai_engine/helpers/`** (`respond_logic.py`, `runtime_config.py`, `llm_client.py`, `quality_gate.py`, `llm_pipeline.py`). Tests: **`tests/test_ai_respond_logic.py`**, **`tests/test_ai_engine_api.py`**, **`tests/test_llm_pipeline.py`**, **`tests/test_ai_respond_golden.py`**, **`tests/golden/ai_respond/`**; **`pytest.ini`**; **`pytest`** in **`backend/requirements.txt`**.

**Follow-ups (Stem assigns; see checklist § M1 — Still open):** full **input** bundle (history, personas, catalog); per-client **budget / rate** beyond token caps; non–OpenAI providers if needed.

Then read and modify only (unless Stem widens scope):
- backend/apps/ai_engine/main.py
- backend/apps/ai_engine/helpers/*.py
- backend/shared/config.py + backend/.env.example (only for new **AI_LLM_*** env vars)
- tests/test_ai_*.py, tests/test_llm_pipeline.py, tests/test_ai_respond_golden.py, tests/golden/ai_respond/

**Contract rule:** Any change to **`AIRequest`** / **`AIResponse`** field sets requires **Stem + Chat C** (`batch_processor` httpx JSON) + HANDOFF **M1 contract** section + checklist note.

Acceptance: **`python -m pytest tests/`** green.

Do not touch **`wa_gateway`** unless the inbound contract must change — then document in HANDOFF + checklist.
```

### Chat E — M5 Billing (Razorpay India + Paddle global)

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M5 (Landed vs Still open).

**Stem wording:** Chat **E** slice (**`billing_api`** + **`0004`/`0009`** + gateway **DB-only** gating) is **landed** and **pytest-green**; full blueprint **§ M5** is **not** “closed forever” — follow-ups remain in checklist **§ M5 — Still open** and **Stem note — Chat E (scope vs blueprint M5)**.

**Landed (Chat E):** Alembic **`0004_billing`** + **`0009_billing_kyc_invoices`**. FastAPI **`backend/apps/billing_api/main.py`** (default **port 8086**): signed **`POST /webhooks/razorpay`** / **`POST /webhooks/paddle`** (idempotent **`bill_events`**); **REST** (JWT = **`client_api`**) **`POST /billing/razorpay/create-checkout`**, **`POST /billing/paddle/create-checkout`**, **`GET /billing/subscription`**, **`GET /billing/invoices`**, **`POST /billing/kyc/india`**; webhooks extended (**Razorpay:** `invoice.paid`, `payment.failed`, `refund.processed`, `subscription.halted`, renewals; **Paddle:** `transaction.*`, `refund.*`); **`bill_invoices`** upserts; **WA gateway** paywall uses **DB-only** effective entitlement (**`api_clients`** + latest **`bill_subscriptions.status`**). Env: **`backend/.env.example`** (webhook secrets + **`BILLING_RAZORPAY_KEY_*`**, **`BILLING_PADDLE_*`**). Tests: **`tests/test_billing_signatures.py`**, **`tests/test_billing_api_routes.py`**.

**Follow-ups (Stem assigns; see checklist § M5 “Still open”):** KYC **verified/rejected** admin flow; more Paddle/Razorpay event types; revenue aggregates for **`/dash/admin/*`** (read-only, sourced from DB tables only).

Then read and modify only paths Stem approves for the next slice (typically `backend/apps/billing_api/*`, `backend/migrations/versions/`, `backend/shared/config.py`, `backend/.env.example`, `tests/test_billing_*.py`, README/HANDOFF billing bullets; **gateway** only when changing paywall read contract — coordinate **Chat B**).
```

### Chat F — M3/M4 Client API + Inbox *(**M4 blueprint slice landed** — M3 deferred)*

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M4 (+ § M3 deferral note).

**Landed (Chat F / M4):** Alembic **`0008_inbox_blueprint_states`**; **`GET /inbox/notifications`**, **`POST /inbox/notifications/{id}/read`**; **`POST /inbox/chats/{id}/resolve`** → **`CLOSED`**; **`human_queue`** on list; **`ai_paused_until`** on reply (from **`ops_runtime_config`**); assignment **audit** + owner CC + **`inbox_notifications`**; **`DBPoller`** → WS **`notification`**; **`CLIENT_API_WS_ALLOWED_ORIGINS`**; tests e.g. **`tests/test_inbox_openapi_notifications.py`**. **`dev_inbox_smoke.py`** includes resolve step.

**Deferred (M3):** signup, OTP, team, catalog REST — **product confirmation** required (checklist § M3).

**Follow-ups (Stem assigns):** per-chat pagination; **`LISTEN zy_chat_events`** vs **`DBPoller`**; typing **hard lock**; optional dedicated notifications **screen** (API already exists). **Worker batch policy** (**U2** strict, **`NEEDS_OWNER_DATA`** customer **`wa_outbox`**, second-line **`PAYWALL`**) — **Chat C** (landed).

Then read and modify only paths Stem approves for the next slice (typically under `backend/apps/client_api/` + migrations if needed).
```

### Chat G — Flutter **client (tenant)** *(landed — owner/agent; device smoke: Stem / Chat N / you)*

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § Owner/agent Flutter (Chat G) + § M8 client dashboard.

Scope: `flutter_app/` and `mobile/` — **Chat G owns** **`owner`** / **`agent`** flows after login: **`HomeShell`** (Inbox · Dashboard · Account on `flutter_app`; Inbox · Dashboard · Settings on `mobile`), tenant **WebSocket**, **`ClientDashboardScreen`** → **`GET /dash/client/*`**, and the shared **`ClientApiRepository`** inbox + notification calls.

**Not Chat G:** **`super_admin`** users open **`SuperAdminShell`** (SOPs / Runs / Control / admin Dash) — same repo paths, **Chat H** checklist + paste block. Chat G PRs should not grow SOP editors or **`ops_api`** features without Stem routing that work to **H** / **I**.

Task (tenant only):
1) Harden login + role nav for **owner** vs **agent**; inbox list/detail + WS (REST from landed `client_api` Chat F slice).
2) Client dashboard wired to **`GET /dash/client/*`** (Chat J); offline preview if 404.
3) Document ANDROID_EMULATOR / Windows base URLs (`CLIENT_API_BASE_URL`; optional `OPS_API_BASE_URL` only where super_admin link sheet touches shared `SessionController` — document in README, implement under Chat H when changing ops flows).

Acceptance:
- Tenant flows run on Android + Windows desktop; README or `flutter_app/README.md` / `mobile/README.md` build/run commands updated (`flutter create` when platform folders absent).
- Coordinate with Chat A before adding deps that affect CI.

Do not: expand **`SuperAdminShell`** / SOP / **`GET /dash/admin/*`** beyond tenant-touched shared code — that is Chat H.
```

**Status (2026-05-18):** Chat G **checklist slice complete** — **`§ Owner/agent Flutter (Chat G)`** is **all `[x]`**; paste heading **“landed — owner/agent; device smoke: Stem / Chat N / you”** matches: **implementation tasks for G are done**; **smoke** + **downstream** dash/deep-link work live under **Chat N**, **Chat J** (**§ M8 — Phase-2**), **Chat L** / Stem (see **Stem compressed context** **Chat G** row).

### Chat H — Flutter **super-admin** *(M9/M8 interactive landed — smoke on device: Stem / Chat N / you)*

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M8 (control plane) + § M9 (interactive SOP UI).

Scope: `flutter_app/` + `mobile/` — **super-admin** surfaces (**`SuperAdminShell`**: SOPs · Runs · Control · Dash) — Android + Windows desktop targets.

Task:
1) Control plane: runtime config editor (validate keys, audit/revert UX; SOP REST is **`ops_api`** `GET/PUT /ops/sops*` — other ops keys TBD), pricing/debounce/urgent/fallback panels per checklist.
2) SOP Runbook Center: library, Markdown editor + preview, version history/diff, start run + run log viewer; deep links reserved for Chat L auto-trigger later.
3) Super-admin dashboards consuming Chat J `/dash/admin/*` when available.

Acceptance:
- Clear separation from Chat G (no owner/agent inbox logic mixed into super-admin root).
- Works against **`ops_api`** (`http://127.0.0.1:8087`) for SOP/run flows when configured; list TODOs for Stem for gaps.

Do not: wa_gateway or workers — backend stays in B/C/I/J/K.
```

**Status (2026-05-14):** **SOP Runbook** + **`GET /dash/admin/*`** charts (**`dash_bar_charts.dart`**, **`SuperAdminDashScreen`**) + **Control** coordination copy (**`SuperAdminControlPlaneScreen`**) — **no new backend**, **no invented POSTs**. **Still follow-ups:** paste block item **1** (interactive editors — blocked on Stem-approved **`client_api`** or admin API); polish / deep links (**Chat L**).

### Chat I — Backend **SOP Center** *(landed — extend only with Chat A)*

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M9 (Data & APIs).

Stem decision (documented in HANDOFF “What is implemented”): **dedicated FastAPI app** `backend/apps/ops_api/` (port **8087**), not routes under client_api.

Landed scope:
- Alembic `0006_ops_sops`: `ops_sops`, `ops_sop_versions`, `ops_run_logs` + indexes.
- REST + super_admin-only JWT (same secret as client_api `POST /auth/login`).
- Pytest: `tests/test_ops_api_openapi_rbac.py`, `tests/test_ops_api_handlers_mocked_db.py`.
- **Additional (stem doc):** `backend/tools/dev_ops_api_smoke.py` — live httpx smoke; see **Stem note — Chat I extras** in HANDOFF (incl. **Extension gate**).

Extend with Chat A only: **pagination** past `GET /ops/runs` **500**, **export**, **`trigger_type`/event-type enums**, **auto-trigger** hooks — each needs **Stem-approved contract** + **Alembic** if schema changes. **`GET /ops/sops/{id}/versions`** stays **canonical on `ops_api`** (Chat H consumes only). Owner/agent reads on `ops_api` = Stem decision + RBAC contract if ever required.
```

**Status (2026-05-14):** Chat I **done** for this session — **v1 `ops_api`** + **`0006`** + pytest + **`dev_ops_api_smoke.py`** remain the shipped baseline. **Still open:** checklist **§ M9 — Still open (ops_api)** (auto-trigger hooks, runs pagination, stricter `trigger_type`, versions-at-scale, export) — future **Stem-gated** PRs.

### Chat J — Backend **dashboard APIs** *(phase-1 landed — phase-2 Stem-gated)*

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M8 — APIs (backend) + § M8 — Phase-2 — /dash/*.

**Landed (phase-1):** `GET /dash/client/overview|agents|quality` and `GET /dash/admin/overview|collections|providers/razorpay|providers/paddle|ops/whatsapp|admin/geo` (alias `GET /dash/admin/geo`); OpenAPI tag `dash`; RBAC in code + HANDOFF + checklist § M8 — APIs.

**Next (phase-2 — Stem-gated):** Replace placeholders (MRR/revenue/collections, latency, CSAT/proxies) using `bill_*`, `metrics_*`, `inbox_*`, future rollups — Chat E, Chat K, Stem. New `GET /dash/*` or breaking JSON for Chat G/H: Stem first; RBAC + paths in HANDOFF + § M8 — APIs; extend `tests/test_dash_*.py`.
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

**Status (2026-05-17):** Chat K **done** for this session — **v1 usage + metrics workers** + **`usage_metrics_common`** + **`test_usage_thresholds`** + optional **`test_postgres_integration_optional`** harness remain the shipped baseline (checklist **§ Workers**). **No default CI Postgres** (still **Chat M**). Further rollup/schema work = **Stem-gated** PRs; coordinate **Chat J** § M8 phase-2 when dashboards consume new aggregates.

### Chat L — **M6 broadcast + M7 alerts** (backend)

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M6 + § M7.

**Landed (2026-05-14 slice):** Alembic **`0010_m6_m7_broadcast_alerts`**; **`customer_marketing_opt_in`**; **`wa_broadcast_campaigns`** / **`wa_broadcast_targets`**; **`ops_alert_events`**; **`bill_webhook_processing_errors`**; **`wa_outbox.dead_at`**; seed keys **`m6.broadcast_policy`**, **`alerts.thresholds`**; **`broadcast_campaign_worker.py`**; **`alert_eval_worker.py`**; **`outbox_sender`** TEMPLATE Graph path + **`dead_at`** on DEAD; **`metrics_rollup_worker`** hourly billing/meta error counts (requires **`0010`** columns); **`billing_api`** 500 path → DB error row + **`ops_alert_events`** (minute-bucket dedupe); shared **`broadcast_gating.py`**, **`ops_alerts.py`**; tests **`tests/test_m6_m7_helpers.py`**.

**Follow-ups (Stem assigns):** owner/super-admin REST + Flutter for opt-in + campaign authoring; pager/webhook; **`alerts.sop_trigger_map`** + worker/bridge to **`ops_api`** **`POST /ops/sops/{id}/run`** (**M9** phase 2 with **Chat I**); ban/GPU/SLA alert types.

Then read and modify only paths Stem approves for the next slice (typically `backend/migrations/`, `backend/workers/*`, `backend/shared/*`, `backend/apps/billing_api/main.py`, tests, HANDOFF/checklist notes).

Acceptance (this slice):
- No free-text marketing enqueue: **`TEMPLATE`** bodies must pass **`validate_template_only_body`**; trial/starter blocked per **`m6.broadcast_policy`**; opt-in enforced when **`require_marketing_opt_in`** is true.
- Alerts: **`ops_alert_events`** rows + logs; billing failures persisted; no assumed paging integration.

Coordinate: **Chat I** for SOP auto-trigger contract (`trigger_type=auto`, `context_json` from alert row) — **not implemented** here.
```

### Chat M — **M10 release manager + CI expansion**

```text
@HANDOFF.md Read first. @docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md § M10 + checklist **Meta** (do not delete the long checklist until Chat A confirms the meta criteria; landing M10 does not auto-satisfy meta removal).

Status (Stem record):
- **Done (documentation / coordination):** scope for **`/ops/releases*`**, target CI shape, manual approval hooks for **AI / routing / billing**, **Chat N** after **`.github/workflows/ci.yml`** topology changes, **§ M10** + **Meta** cross-rule, this paste block, **HANDOFF**, **README §4** — written in tree.
- **Not done (real engineering — checklist § M10 checkboxes):** **`GET/POST /ops/releases*`** (or equivalent) in **`ops_api`**; Postgres **service** + integration / contract / optional E2E jobs in CI; org-side **Environments** / **CODEOWNERS** only described until Stem turns them on. Next Chat M (or assignee) implements when scheduled.

Product scope — **`/ops/releases*`** (still **in** blueprint **gated releases** unless Stem defers):
- **`GET/POST /ops/releases*`** (or equivalent under **`backend/apps/ops_api/`**): **register** a candidate build + **test report / artifact hash**; **promote**; **rollback** to a prior registered revision — **super_admin**-gated, audited (Stem defines exact JSON + tables in a small PR).

CI — **`.github/workflows/ci.yml`** (incremental PRs OK):
- Keep the default **fast** **`pytest`** job.
- Add a **Postgres `services:`** job: start DB, **`alembic upgrade head`**, **`RUN_POSTGRES_INTEGRATION=1`** + **`DATABASE_URL`**, run **`tests/test_postgres_integration_optional.py`** (and extend only as Stem assigns).
- Add **contract** job(s) as needed (OpenAPI drift, billing signatures, gateway “no AI in webhook” imports — reuse existing tests; split only if runtime warrants).
- Optional job: **`RUN_WA_GATEWAY_E2E=1`** + documented secrets; **default off** on PRs from forks.

Manual approval hooks — **document in README + HANDOFF** (implementation may be repo-only docs until GitHub settings exist):
- Touches to **`backend/apps/ai_engine/`** (AI behavior / spend), **`backend/apps/wa_gateway/`** (routing, paywall, debounce, urgent), **`backend/apps/billing_api/`** (webhooks, checkout, subscription-affecting code) should require **human review** before production — e.g. **`production` Environment** with **required reviewers**, **`CODEOWNERS`**, and/or **branch protection** rules. Stem picks the lever; Chat M writes the runbook paragraph.

Acceptance:
- Checklist § M10 rows ticked by Chat A when merged.
- **After any CI workflow topology change** (new jobs / services / matrix): **Chat N** runs **full** README smoke (**10-step** staging checklist + documented optional gates: workers, **`dev_ops_api_smoke`**, Flutter **`dart analyze` + G/H device** when UI-relevant) and records outcome for the PR.

Coordinate: Chat A owns checklist **Meta** removal vs keeping a stub; Chat N owns smoke evidence policy per **Stem note — Chat N (scope vs evidence)** — for CI topology changes, full smoke is the **explicit** bar above.
```

### Chat N — **QA / staging gates**

```text
@HANDOFF.md Read first. tests/ + README (smoke, automated tests).

Task:
1) Extend pytest/contract tests as Stem requests per slice (debounce, urgent, billing, dash APIs).
2) Keep README **10-step staging smoke** accurate; optional **RUN_WA_GATEWAY_E2E** and **RUN_POSTGRES_INTEGRATION** docs (Chat K workers + `ops_*` schema sanity).
3) Maintain **Flutter** `dart analyze` + **Chat G / Chat H** device smoke checklist (Windows + Android) in README.

Acceptance:
- `python -m pytest tests/` passes locally; document any new env vars.
- **Stem policy:** “Chat N done” = **deliverables in repo** (tests + docs + optional harness). It does **not** require log proof that **`RUN_POSTGRES_INTEGRATION`** or **Flutter device smoke** was executed unless Stem asks for that merge gate.
- **Exception (coordination with Chat M):** If a PR **changes `.github/workflows/ci.yml` job topology** (new jobs, `services:`, matrix), run **full** README smoke (**10-step** + documented optional gates) and note pass/fail on the PR — Stem treats that as the evidence bar for CI shape changes.

This chat does not own feature implementation — verification + tests + smoke lists only unless Stem assigns a small fix.
```

**Status:** `python -m pytest tests/` from repo root (see README **Automated tests**). Optional live gateway: `RUN_WA_GATEWAY_E2E=1` + `ZY_E2E_META_PHONE_NUMBER_ID`. Optional Postgres integration: `RUN_POSTGRES_INTEGRATION=1` + valid `DATABASE_URL` + migrations at head → `tests/test_postgres_integration_optional.py` (**green run is optional proof**, not a default Chat N bar — see **Stem note — Chat N (scope vs evidence)**). Full **10-step staging smoke** checklist: README section *Non-dev / staging smoke checklist (10 steps)*; optional extensions (workers, ops_api, Flutter analyze/device) documented in the same README section — **execute manually** when UI or DB-backed paths change.

## Testing (quick reference)

| What | Command / location |
|------|---------------------|
| Unit + contract tests | From repo root: `python -m pytest tests/` |
| **ops_api (M9)** | `python -m pytest tests/test_ops_api_openapi_rbac.py tests/test_ops_api_handlers_mocked_db.py -v` (mocked DB); live stack: `python backend/tools/dev_ops_api_smoke.py --email … --password …` |
| **WA Gateway (M2 / Chat B)** | `tests/test_wa_gateway_no_ai.py`, `tests/test_wa_gateway_meta_helpers.py` (no live Meta); optional E2E row above |
| **AI Engine (M1 / Chat D)** | `tests/test_ai_respond_logic.py`, `tests/test_ai_engine_api.py` (mock `load_ai_engine_ops_bundle` + short-circuit LLM), `tests/test_llm_pipeline.py`, `tests/test_ai_respond_golden.py` |
| Optional Postgres integration (Chat K + `ops_*` schema) | `RUN_POSTGRES_INTEGRATION=1`, **valid** `DATABASE_URL`, migrations at head, `tests/test_postgres_integration_optional.py` (see README). **Not** part of default “Chat N shipped” proof unless Stem records a green run. |
| Non-dev smoke (10 steps) | README → *Non-dev / staging smoke checklist* |
| Flutter analyze + G/H device smoke | README → *Flutter / Chat N — `dart analyze` and device smoke* |

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

**Convention:** Each line starts with an **ISO date** (`yyyy-mm-dd`). **Subsections** (`### yyyy-mm-dd`) group **strictly descending** calendar days (**2026-05-14** → **2026-05-13** → **2026-05-12**). **Within each day**, every bullet is **A→Z by bold headline** (stable scan; no “floating” exceptions). *Baseline “today” when this pass was written: **2026-05-14** (14 May 2026).*

### 2026-05-18

- 2026-05-18 — **Chat G — checklist slice complete (bookkeeping):** [`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`](docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md) — **§ Owner/agent Flutter (Chat G)** **Stem note** after block (**all `[x]`**; **device smoke** = **Chat N** merge gate, not § G rows; **richer charts / tenant `/dash/client/*` phase-2** = **§ M8 — Phase-2 (Chat J)**; **deep links** = **Chat L** / Stem). Parallel **§ M4/M8 client UI** row expanded. **`HANDOFF.md`** — **Stem compressed context** **Chat G** row; **Known gaps** §5; **Chat G** paste **Status** (aligns with heading *landed — owner/agent; device smoke: Stem / Chat N / you*).

### 2026-05-14

- 2026-05-14 — **Chat A (Stem) — sequencing + verification note**: New **`Stem sequencing — next module chats (2026-05-14)`** (order **N → B → C → F → E → D → L → M** + device smoke assignment); **Known gaps** item **8** (Chat **K**: helper pytest **landed** in `test_usage_thresholds.py`; **optional Postgres worker SQL pytest** = **`tests/test_postgres_integration_optional.py`** when `RUN_POSTGRES_INTEGRATION=1` — **Chat N**; CI Postgres **service job** still optional / **Chat M**). **Pytest (verified locally, same day):** from repo root with **`$env:PYTHONPATH="$PWD"`** — **`python -m pytest tests/`** → **72 passed**, **1 skipped** (optional gateway E2E), **1** Starlette `multipart` PendingDeprecationWarning — Windows / Python **3.13.12**. **Still run before push:** Flutter **`dart analyze`** + **G/H** device smoke on **Windows + Android**; `git push` if you use a remote.
- 2026-05-14 — **Chat C (Workers) — batch path policy landed:** **`backend/workers/batch_processor.py`** — **U2 strict** after **`/ai/respond`** (urgent **`REPLY`** → **`HANDOFF`** / `urgent_time_sensitive_u2`); **`NEEDS_OWNER_DATA`** customer **`wa_outbox`** via **`_load_needs_owner_customer_reply_text`** (aligned with **`ai_engine`**); **second-line paywall** before AI (**`PAYWALL`**, batch **`PROCESSED`**). **`tests/test_batch_processor_policy.py`**. **HANDOFF:** **M1** **Chat D / Chat C boundary** (worker owns policy, **`ai_engine`** owns **`POST /ai/respond`**); **Chat C** paste + **Status**; **Chat F** follow-ups (remove duplicate **U2** / **`NEEDS_OWNER`** worker item). **User run:** **`python -m pytest tests/ -q`** → **105 passed**, **1 skipped** (optional gateway E2E).
- 2026-05-14 — **Chat C (Workers) — goal + docs:** Checklist § Workers opens with **delivery + blueprint alignment** goal (idempotent sends, backoff, DEAD, crash-safe retries; **A5**; HANDOFF / NEEDS_OWNER / **U2** vs `PENDING_AGENT` + notify; sealed batch window only); **Chat C** paste block updated (**coordinate B**; **no Chat K** unless Stem assigns). **HANDOFF:** Workers bullet + dev helpers + multi-chat **C** column; **“What is implemented”** Workers line restores full **Chat K** metrics sentence + blueprint follow-up pointer. New **`Stem note — Chat N (scope vs evidence)`** — “Chat N done” = **repo deliverables**, not mandatory log proof for optional Postgres or device smoke; optional integration **green** only after **valid** `DATABASE_URL` + migrations + pass; **`dart analyze` / G+H smoke** remain **manual** merge gates when UI matters. Sequencing row **N** + Known gaps §8 + Chat N paste **Acceptance** + **Status** + Testing table aligned.
- 2026-05-14 — **Chat D (M1) — verification + hygiene:** **`llm_client.py`** — removed stray unused **`logger`** after **`logging`** import dropped. **`pytest.ini`** — **`filterwarnings`** for Starlette **`formparsers`** **`PendingDeprecationWarning`** (`python_multipart`). **HANDOFF** **M1 contract** — **Chat D** session touched **`ai_engine`** / tests only (**no** **`batch_processor.py`** in that slice; **worker batch policy** = **Chat C** — see **Chat C (Workers) — batch path policy landed** above). **Checklist § M1** landed row — same **Chat D** boundary. **User run:** `pytest tests/test_ai_respond_logic.py tests/test_ai_engine_api.py tests/test_llm_pipeline.py tests/test_ai_respond_golden.py` — **34 passed** (Python **3.13.12**).
- 2026-05-14 — **Chat F / M4 inbox slice (Stem bookkeeping):** **`HANDOFF.md`** — **Stem sequencing** rows **C**/**F**, **multi-chat F** row, **Chat F** paste block updated (**M4 landed**, **M3 deferred**, follow-ups: pagination, **`LISTEN`**, typing hard lock, **U2**/NEEDS_OWNER **`wa_outbox`**, notifications UI). Aligns with **`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`** parallel table + § M3 deferral + § M4/`§ Workers` checkboxes already in tree.
- 2026-05-14 — **Chat G vs Chat H (doc sync):** [`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`](docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md) — parallel **§ M4/M8 client UI** row + **§ Owner/agent Flutter (Chat G)** — **scope boundary** (**`HomeShell`** tenant vs **`SuperAdminShell`**); **nav/refresh**, **inbox/thread**, **`SessionController.wsLastError`**, dual API bases, **`flutter create`** note. **`HANDOFF.md`** — **What is implemented** **Flutter owner/agent (Chat G)** bullet (tenant-only WS; **`super_admin`** → **`SuperAdminShell`**); **Known gaps §5**; **multi-chat** rows **G**/**H**; **Chat G** paste block + **Chat H** scope line (`mobile/` included).
- 2026-05-14 — **Chat I — session done:** Stem compressed context row **Chat I**; **Stem note — Chat I extras** session line; **Chat I** paste **Status**; checklist parallel **§ M9 APIs** row (**v1 landed** vs **§ M9 Still open ops_api** extensions). **Tree:** **`ops_api`** baseline unchanged this pass (`GET /ops/runs` still **`LIMIT 500`**). `flutter_app` + `mobile` — **`lib/widgets/dash_bar_charts.dart`** (`DashDictBarCard`, `DashMessageTotalsCard`, `DashKpiRow`); **`SuperAdminDashScreen`** per **`DashAdmin*Out`** + Raw JSON dialog; **`SuperAdminControlPlaneScreen`** § M8/M9 coordination copy (**no** new backend / invented POSTs). **HANDOFF:** Stem compressed context **Chat H** row; **Known gaps** §5/§7; **Stem note — Chat H**; **Chat H** paste **Status**. **Checklist:** § M8 super-admin dash **`[x]`**; parallel row **§ M8 + § M9 UI**; README Flutter bullets.
- 2026-05-14 — **Chat K (harness extension):** **`tests/test_postgres_integration_optional.py`** — **`test_chat_k_public_tables_present`**, **`test_metrics_hourly_system_inserts_current_utc_hour_bucket`**; module docstring notes **`0010`** columns on **`metrics_hourly_system`**; **`HANDOFF.md`** **Usage & metrics workers** optional pytest block; **`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`** § Workers optional Postgres line **`[x]`** + parallel **§ Workers (usage/metrics)** row (CI job still **Chat M**).
- 2026-05-14 — **Chat K — session done:** **`HANDOFF.md`** — **Stem compressed context** row **Chat K**; **Chat K** paste **Status**; **multi-chat** row **K** (tests + optional integration harness). **`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`** — parallel **§ Workers (usage/metrics)** row (session closed on **v1** baseline; **CI Postgres** still **Chat M**).
- 2026-05-14 — **Chat L (M6/M7 backend slice):** Alembic **`0010_m6_m7_broadcast_alerts`** (`customer_marketing_opt_in`, **`wa_broadcast_*`**, **`ops_alert_events`**, **`bill_webhook_processing_errors`**, **`wa_outbox.dead_at`**, hourly metrics columns + seeds **`m6.broadcast_policy`** / **`alerts.thresholds`**); **`broadcast_campaign_worker.py`**, **`alert_eval_worker.py`**, **`broadcast_gating.py`**, **`ops_alerts.py`**; **`outbox_sender`** TEMPLATE Graph send + **`dead_at`**; **`metrics_rollup_worker`** billing/meta hourly counts; **`billing_api`** webhook 500 → DB + alert; HANDOFF services + **Chat L** paste + checklist § M6/§ M7/M9 auto-trigger note; **`tests/test_m6_m7_helpers.py`**; **`.env.example`** worker env hints.
- 2026-05-14 — **Chat M — doc vs implementation:** Stem compressed context row **Chat M**, **Chat M** paste block **Status**, checklist **§ M10** “Handoff status”, **README §4** — explicit split: **documentation / coordination slice done**; **unchecked § M10 rows** = **no** **`/ops/releases*`** APIs, **no** Postgres/integration/contract/E2E CI jobs yet, **Environments/CODEOWNERS** process-only until org config.
- 2026-05-14 — **Chat N (QA):** optional Postgres integration pytest **`tests/test_postgres_integration_optional.py`** + **`tests/conftest.py`** (collect when `RUN_POSTGRES_INTEGRATION=1` + `DATABASE_URL`); README **Optional Postgres integration**, **10-step** optional extensions, **Flutter / Chat N** `dart analyze` + G/H device smoke; **`RUN_POSTGRES_INTEGRATION`** in **`backend/.env.example`**; HANDOFF Testing table + Chat N paste block + Known gaps §8 note.
- 2026-05-14 — **Dev seed — `super_admin`:** `dev_seed_users.py` optional **`--super-admin-email`** / **`--super-admin-password`** (same `--client-id` as owner/agent); README **ops_api smoke** block; **`dev_ops_api_smoke.py`** docstring points to seed script; HANDOFF dev helpers + Chat I extras + Known gaps §7(a) updated.
- 2026-05-14 — **HANDOFF — Last updated full resort:** Regrouped **every** changelog bullet under **`### 2026-05-14`**, **`### 2026-05-13`**, **`### 2026-05-12`** (strict **descending** day order, no interleaved days); **A→Z by bold headline** within each day; removed duplicate **Chat G vs Chat H** line; convention text matches **14 May 2026** baseline.
- 2026-05-14 — **HANDOFF — Stem compressed context:** New section **Stem compressed context (session key points)** — table for **slice vs blueprint**, **N/B/C/F/E/D/L** one-liners, **Chat L** “next output” scope (M9 auto-trigger **not** wired; **`alerts.sop_trigger_map` TBD**), pointer to future **chain tests**.
- 2026-05-14 — **Integrated landing commit (local `master`):** **`2b51db3`** — `feat: dashboards, ops_api SOP center, usage/metrics workers, Flutter G/H parity` (79 files). **`git push`** requires a remote: `git remote add origin <url>` then `git push -u origin master` (or your default branch name).
- 2026-05-14 — **M10 + meta (Chat M / checklist):** [`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`](docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md) — § **M10** expanded (**`/ops/releases*`** still in **gated-release** product scope; CI = Postgres service + integration + contract + optional **`RUN_WA_GATEWAY_E2E`**; **manual approval hooks** for **AI / routing / billing** paths); **Meta** cross-rule (**M10 ≠** auto-delete checklist). **`HANDOFF.md`** — **Stem compressed context** row **Chat M**; **Known gaps §6**; **Tests + CI** bullet matches current **`ci.yml`** (pytest-only, Python 3.12); **Chat M** paste block = scope + CI + approvals + **Chat N full smoke after CI topology changes**.
- 2026-05-14 — **M5 billing expansion (Chat E):** **`0009_billing_kyc_invoices`** (`bill_invoices`, **`api_clients`** KYC JSON + timestamps); **`billing_api`** REST (**checkout**, **subscription**, **invoices**, **KYC India** submit) + CORS; extended **Razorpay/Paddle** webhooks (**invoice / payment failure / refund / halted**, Paddle **transactions**); **`wa_gateway`** paywall **`_fetch_client_row`** lateral join on **`bill_subscriptions`** (DB-only gating); **`client_api/routes_dash.py`** docstring (**Chat J** read-only vs **`billing_api`** truth); **`README`** + **`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`** § M5 + **Chat E** paste; **`tests/test_billing_api_routes.py`**.
- 2026-05-14 — **M5 checklist + Chat E paste (Stem bookkeeping):** **`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`** § **M5** split **Landed (Chat E)** vs **Still open** (checkout, GET subscription/invoices, KYC, broader webhooks, plan-gating E2E). **`HANDOFF.md`** **Chat E** paste block aligned with **`billing_api`** / **`0004_billing`**, env keys, tests, follow-ups pointer to checklist **Still open**.
- 2026-05-14 — **Stem — Chat B log synced to HANDOFF:** “What is implemented” **WA Gateway** bullet expanded (**`PAYWALL`**, **`WA_GATEWAY_ALLOW_CLIENT_ID_HEADER`**, adaptive + urgent U1, **`0007`**, dedupe **RETURNING**, **`m2.service_inactive_customer_reply`**, tests); **Alembic** lists **`0007`**; **Tests + CI** lists **`test_wa_gateway_no_ai.py`** / **`test_wa_gateway_meta_helpers.py`**; **Usage & metrics** §3–Coordinate updated (hard block **landed** in gateway); **Stem sequencing** rows **B**/**C**; **multi-chat B** row; **Chat B** paste block = **landed + follow-ups**. Checklist parallel **§ M2** + usage worker row note (**B** vs legacy **OPEN**).
- 2026-05-14 — **Stem — Chat E closure policy:** New **`Stem note — Chat E (scope vs blueprint M5)`** (“Chat E slice **landed + pytest-green**” ≠ “**M5** finished forever”); **Known gaps §4**, **Stem sequencing** row **E**, **multi-chat E**, checklist parallel **§ M5** row point at **§ M5 — Still open** (KYC verify, pricing UX, disputes, **`/dash/admin`** billing tiles).

### 2026-05-13

- 2026-05-13 — **Chat A (Stem) — `GET /ops/sops/{id}/versions` policy:** Confirmed **canonical Chat I**; Chat H wrap-up table row updated; checklist § M9 intro + Data & APIs (`POST …/run` line restored) + parallel **§ M9** row; **Chat H** paste heading = landed + device smoke note.
- 2026-05-13 — **Chat G handoff (Stem)**: `HANDOFF` “What is implemented” **Flutter owner/agent (Chat G)** bullet; multi-chat row **G landed**; **Chat G** paste heading; **Known gaps** §5; **`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`** — parallel **§ M4/M8 client UI** row, new **§ Owner/agent Flutter UI (Chat G)** `[x]` block, § M8 **Client dashboard (Flutter)** line ticked for Chat G v1.
- 2026-05-13 — **Chat H (M9 interactive SOP UI)**: `flutter_app` super_admin **SOP Runbook** — `SuperAdminShell`, `OPS_API_BASE_URL` + persisted URL sheet, `lib/screens/sops/*` (library, detail+Markdown, editor POST/PUT, versions+diff+restore, start run, run list/detail). **ops_api:** `GET /ops/sops/{sop_id}/versions` + `SopVersionOut`. Checklist § M9 interactive bullets updated `[x]` (except phase-2 auto-trigger + day-1 content + optional PDF).
- 2026-05-13 — **Chat H HANDOFF for stem**: New section **Stem note — Chat H wrap-up (main stem / Chat A)** (M9/M8/Dash scope, `mobile/` parity done, auth/error rules, **`GET …/versions`** = **Stem-confirmed** Chat I contract, smoke = manual on device). **“What is implemented”** Flutter bullet refreshed (four tabs, CORS, both apps). **Known gaps** §7: **`mobile/`** parity marked **done**; stem still owns seed user, CI Postgres, runs pagination, phase-2 auto-trigger, day-1 SOP content.
- 2026-05-13 — **Chat I (M9 Data & APIs)**: New FastAPI **`backend/apps/ops_api/`** (port **8087**); Alembic **`0006_ops_sops`** (`ops_sops`, `ops_sop_versions`, `ops_run_logs`); REST under **`/ops/*`** with **`super_admin`** JWT from `client_api`; `OPS_API_CORS_ORIGINS` + shared **`CLIENT_API_JWT_SECRET`** in `backend/.env.example`; pytest **`tests/test_ops_api_*.py`**; checklist § M9 **Data & APIs** marked done.
- 2026-05-13 — **Chat I extras for Stem (HANDOFF)**: New section **Stem note — Chat I extras (Chat A analysis)** (`ops_sop_versions` vs checklist wording, `dev_ops_api_smoke.py`, pytest file names + Windows/py3.13 green run, `ops_api_cors_origins`, suggested Stem actions); **Known gaps** item **7** (M9 post–Chat I); **Dev helpers** + **Tests + CI** + **Testing** table + **ops_api smoke** PowerShell under client_api smoke; Chat I paste block points to stem note.
- 2026-05-13 — **Chat J — doc pass (phase-1 vs phase-2):** Checklist **§ M8 — Phase-2 — `/dash/*` (Chat J; Stem-gated)** (placeholders → **`bill_*` / `metrics_*` / `inbox_*`**; new routes / breaking JSON → **Stem** + **HANDOFF** + **§ M8 — APIs** + **`tests/test_dash_*.py`**); parallel **§ M8 dashboard REST** row (**phase-1** + pointer + **§ M5 — Still open** overlap). **`HANDOFF.md`:** **Stem compressed context** **Chat J** row; **multi-chat J**; **Chat J** paste block (**phase-1 landed — phase-2 Stem-gated**).
- 2026-05-13 — **Chat K usage/metrics** (implementation): Alembic `0005_usage_metrics` + `usage_increment_worker.py` + `metrics_rollup_worker.py`; HANDOFF **Usage & metrics workers**; `backend/.env.example` + `Settings` knobs.
- 2026-05-13 — **Flutter `flutter_app/`**: scaffold + client_api login/inbox/WS shell + super_admin stub; README Flutter section; HANDOFF **Chat G / Chat H** paste blocks split client vs super-admin.
- 2026-05-13 — **M10-lite testing**: `tests/` pytest …; HANDOFF **Chat N** owns QA/smoke (replaces prior Chat H testing-only block).
- 2026-05-13 — **M5 billing**: Alembic `0004_billing` (`bill_plans`, `bill_subscriptions`, `bill_events`); FastAPI `billing_api` on port **8086** with signed `POST /webhooks/razorpay` and `POST /webhooks/paddle`; `BILLING_*` env keys in `backend/.env.example`; README billing curl/PowerShell; HANDOFF **Billing (M5 layout)** subsection.
- 2026-05-13 — **M8 dashboard read APIs (Chat J)** in `client_api`: `routes_dash.py` + response models; `GET /dash/client/*` and `GET /dash/admin/*` (see “What is implemented” for paths and RBAC).
- 2026-05-13 — **M9 ops_api — checklist + HANDOFF (Stem):** [`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`](docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md) § **M9** — new **Still open (ops_api — Chat I + Stem)** rows (**auto-trigger API hooks**, **`GET /ops/runs` pagination**, **stricter `trigger_type`**, **`GET …/versions` at scale**, **export**); phase-2 **Auto-trigger wiring** row cross-links that section. **`HANDOFF.md`** — **`ops_api` bullet**: explicit **`GET /ops/sops/{sop_id}/versions` v1 policy** (404, full `ORDER BY version_num ASC`, `SopVersionOut`, append-only restore via `PUT`), **`GET /ops/runs` v1** (`ORDER BY created_at DESC`, **`LIMIT 500`**), pointer to checklist **Still open**; **Stem note — Chat I extras** table expanded (**versions** / **runs** / **`trigger_type`**+auto-trigger / **export**); **Stem note — Chat H** backend contract + checklist rows updated; **multi-chat I** row lists **`GET …/versions`**.
- 2026-05-13 — **ops_api extension gate (Stem):** **`HANDOFF.md`** — **`ops_api` bullet** reframed (**core `0006` + REST landed**; **extensions** = runs pagination past **500**, **export**, **`trigger_type`/event-type enums**, **auto-trigger** — **only** with **Stem-approved contract** + **Alembic** when needed); **`GET /ops/sops/{id}/versions`** explicitly **canonical on `ops_api` only** (Chat **H** consumes). **Stem note — Chat I extras:** new **Extension gate** paragraph + tightened **versions** / **Chat H** backend contract rows. **`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`** § M9 **Still open (ops_api)** — lead **Gate** paragraph; **Data & APIs** `/versions` row = canonical **`ops_api`** only.

### 2026-05-12

- 2026-05-12 — **Chat I done** (stem bookkeeping): `docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md` parallel-ownership row **Chat I landed**; M9 intro text updated (**backend landed**, UI = Chat H). Implementation already logged on 2026-05-13 below.
- 2026-05-12 — **Chat J done** (stem bookkeeping): `docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md` § M8 **APIs** marked `[x]`; parallel-ownership row **Chat J landed**; HANDOFF multi-chat table + **Chat J** paste heading marked landed. Implementation already noted on 2026-05-13 below.
- 2026-05-12 — **Chat K done** (stem bookkeeping): `docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md` — § Workers items for usage gate + metrics rollup marked `[x]`; parallel-ownership row shows **Chat K landed**. Paywall **enforcement** in M2/batch paths remains **Chat B / Chat C** (see checklist notes on those lines).
- 2026-05-12 — **M1 / Chat D (stem bookkeeping):** **`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`** § **M1** split **Landed (deterministic slice)** vs **Still open** (LLM, full input, quality, golden tests). **`HANDOFF.md`** — “What is implemented” **AI Engine** bullet expanded; **Known gaps §2**, **Stem sequencing** row **D**, **multi-chat D** row, **Chat D** paste block, **Testing** table (**AI Engine** row), **Tests + CI** bullet aligned with **`test_ai_*`**.
- 2026-05-12 — **M1 AI — LLM + quality gate (Chat D):** OpenAI-compatible **`/chat/completions`** behind env **`AI_LLM_*`** + **`ops_runtime_config`** **`ai.fallback.*`**; **Hinglish** `language`; local + judge **quality gate**; **`tests/golden/ai_respond/`** + **`tests/test_ai_respond_golden.py`**, **`tests/test_llm_pipeline.py`**; **`load_ai_engine_ops_bundle`**; HANDOFF **M1 — `POST /ai/respond` contract (Chat C coordination)** + checklist § M1 landed rows; **`backend/shared/config.py`** + **`backend/.env.example`**. **`batch_processor`** request/response JSON unchanged.
- 2026-05-12 — **M1:** documented `ops_runtime_config` keys `ai.urgent_bypass_substrings` and `ai.needs_owner_data_customer_reply` in gap list.
- 2026-05-12 — **M3/M4 client_api landed**: JWT login, RBAC, inbox list/detail, assign/reassign/unassign/escalate, typing, agent reply (mirrors `inbox_messages` + outbox `AGENT_REPLY`), `/ws` with `message_new` / `assignment_changed` / `typing` / `chat_state_changed`. Cross-process events via in-process `DBPoller` over `inbox_messages` / `wa_outbox` / `chat_assignments`. New env keys; new dev tools `dev_seed_users.py` + `dev_inbox_smoke.py`.
- 2026-05-12 — **Multi-chat model**: table A–N; Chat A stem **full control** + `@docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`; paste blocks **G–M** (Flutter split, SOP backend, dash APIs, usage/metrics workers, M6/M7, M10); **Chat N** = QA/smoke; B–F link to checklist sections.
- 2026-05-12 — **Stem wrap-up**: `batch_processor` HANDOFF/NEEDS_OWNER_DATA + **`pg_notify('zy_chat_events')`**; client_api **`Idempotency-Key`** on agent reply; **`dev_listen_chat_events.py`**; README **Sequential follow-through** + CI note; **`.github/workflows/ci.yml`**; HANDOFF gaps refreshed; **Next chat** paste block above.
- 2026-05-12 — **multi-chat stem**; added **Paste blocks for new Cursor chats** (Chats A–H).
