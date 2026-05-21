# Implementation Stem: Chat O Onward

This document is the base controller plan for implementing the remaining v5.3-WIN11 blueprint ideas into the current Option C codebase.

Decision remains unchanged:

- Keep the working v6-style service layout: `wa_gateway:8081`, `ai_engine:8083`, `client_api:8085`, `ops_api:8087`, workers, Postgres-first queues.
- Do not rebase to a separate `webhook.py:8000` or Redis-first hot path unless a later explicit architecture decision changes this.
- Preserve the verified flow: inbound -> DB -> batch -> Ollama/AI -> outbox -> Meta -> Flutter Inbox.
- Each chat below should be small enough to implement, migrate, test, and hand off independently.

## Verified Baseline

- Gate 1 pipeline: verified.
- Gate 2 local Ollama: verified on `127.0.0.1:11435`.
- Flutter Inbox: verified.
- Real WhatsApp outbound: verified with `wa_outbox.status = SENT` and Meta `wamid`.
- Phase 4 owner/SLA watchdog: implemented.
- Phase 5 telemetry/misfires: implemented.

## Chat O: Production Readiness Hardening

Goal: make the currently working stack safer and easier to operate before adding larger features.

Scope:

- Add start/stop/status scripts for the full local stack.
- Add a single `preflight_real_whatsapp.py` that checks:
  - env load source,
  - Meta token validity,
  - linked `meta_phone_number_id`,
  - Ollama health,
  - `8081`, `8083`, `8085` health,
  - migration head,
  - recent outbox errors.
- Add safer tools for resetting test chats and requeueing selected outbox rows.
- Document source-of-truth `.env` rules to avoid Windows env override incidents.

Acceptance:

- One command reports all blockers before a real WhatsApp test.
- Existing Gate 1/Gate 2/Meta flow remains green.

## Chat P: Meta 24-Hour Window and Template Fallback

**Status:** implemented (migration `0021`, `wa.service_window.policy`, `outbox_sender` fallback).

Goal: implement the production WhatsApp rule that free-form replies are only safe inside the customer service window.

Scope:

- Persist useful Meta status webhook timestamps where available.
- Add `customer_service_window_expires_at` or equivalent state.
- In `outbox_sender`, detect expired/near-expired windows before free-form sends.
- Route to approved template rows where configured.
- Add ops_runtime_config keys for template names/languages.

Acceptance:

- Free-form `AI_REPLY` sends normally inside window.
- Expired window uses template fallback or fails with a clear config error.
- Tests cover both paths.

## Chat Q: Inbox Typing Lock and Collision Prevention

**Status:** implemented (`inbox_typing_lock`, `batch_processor` skip, `ai_skipped` NOTIFY, migration `0022`).

Goal: prevent AI replies while an agent is actively typing or recently took ownership.

Scope:

- Implement Postgres-first typing lock (Redis optional later).
- Wire existing typing endpoint to persist lock TTL.
- Make `batch_processor` skip AI if active typing lock exists.
- Add UI-visible reason where possible.

Acceptance:

- Agent typing stops AI reply for that chat.
- Lock expires automatically.
- Tests cover AI skip vs normal reply.

## Chat R: Billing Production Slice

**Status:** implemented (signature hardening, `_paddle_custom_data` fix, simulate tools).

Goal: move billing from deferred scaffolding toward production-safe Razorpay/Paddle behavior.

Scope:

- Validate current billing tables and webhook handlers.
- Harden Razorpay signature verification.
- Harden Paddle signature verification.
- Update plans and entitlement transitions.
- Add tools to simulate paid upgrade and churn safely.

Acceptance:

- Test webhook can move trial -> starter/growth.
- Invalid signature is rejected.
- Plan state affects paywall and usage cap.

## Chat S: Cost and Margin Analytics

**Status:** implemented (`0023`, `metrics.cost_model`, daily cost/margin rollup, `/dash/admin/cost-margin`).

Goal: implement slim version of v5.3 cost tracking without overbuilding the full formula.

Scope:

- Add cost fields to telemetry or daily rollups.
- Add configurable local/cloud token cost assumptions.
- Add estimated monthly client margin view.
- Alert when estimated cost crosses threshold.

Acceptance:

- Dashboard/API can show estimated cost per client.
- Alert row appears when threshold exceeded.

## Chat T: Multi-Modal Minimum Viable Router

**Status:** implemented (safe media bypass, owner notification, customer ack, dev payload support).

Goal: safely route non-text inbound payloads before doing OCR/STT/RAG.

Scope:

- Detect image/audio/document/button/list payloads.
- Store payload metadata.
- For unsupported media, send brand-safe handoff/owner message.
- Add button/list direct mapping only if existing schema supports it.

Acceptance:

- Non-text payloads do not crash or enter the text LLM path.
- UI shows useful media/system message.

## Chat U: Knowledge Base and Catalog MVP

**Status (2026-05-21):** Backend slice landed — migration `0024_client_catalog`, `client_catalog_items`, `backend/shared/catalog_lookup.py`, AI engine catalog routing before generic/LLM path, `seed_client_catalog.py`.

Goal: answer basic product/catalog questions from tenant data before full PGVector.

Scope:

- [x] `client_catalog_items` table (tenant SKU, name, price_inr, stock_qty).
- [x] Exact/fuzzy name + SKU token lookup in `catalog_lookup.py`.
- [x] `POST /ai/respond` uses deterministic catalog facts (`intent=catalog_fact`, `routing_intent=catalog`); skips LLM.
- [x] Unknown price/stock → `NEEDS_OWNER_DATA` → batch sets `WAITING_OWNER_DATA`.

Acceptance:

- Known SKU/product answer includes accurate data.
- Unknown price/stock does not hallucinate.

**Verify (after `alembic upgrade head` to `0024_client_catalog`):**

```powershell
. .\dev-env.ps1
python -m alembic -c backend\alembic.ini upgrade head
python backend\tools\seed_client_catalog.py --client-id 17682c77-1524-4ebd-94e5-958e7f37ac60 --sku WIDGET-A --name "Widget A" --price 499 --stock 12
python backend\tools\seed_client_catalog.py --client-id 17682c77-1524-4ebd-94e5-958e7f37ac60 --list
# Restart ai_engine if already running
python backend\tools\reset_chat_ai_active.py --phone 919769825350
python backend\tools\dev_send_inbound.py --meta-phone-number-id 1098044196727032 --from +919769825350 --text "What is the price of WIDGET-A?"
# ~30s
python backend\tools\dev_check.py
```

Expect `AI_REPLY` with ₹499 and SKU; for `How much is the mystery product?` expect `WAITING_OWNER_DATA` (no LLM price guess).

## Chat V: Compliance and Privacy Hardening

**Status (2026-05-21):** Backend slice landed — migration `0025_phase5_privacy`, `customer_blocks`, `pii_redaction.py`, observability redaction, gateway block drop/handoff, batch skip for blocked numbers, `manage_customer_block.py`, `prune_observability.py`, `set_privacy_policy.py`, `docs/DPDP_ASSUMPTIONS.md`.

Goal: reduce regulatory risk before public launch.

Scope:

- [x] PII redaction helpers for telemetry/misfires (`backend/shared/pii_redaction.py` → `observability.py`).
- [x] DND/blocklist schema (`customer_blocks`) and gateway checks (`privacy.policy.blocklist_mode`).
- [x] Basic retention/pruning script (`prune_observability.py`).
- [x] Document DPDP assumptions and gaps (`docs/DPDP_ASSUMPTIONS.md`).

Acceptance:

- Phone/email/card-like values are redacted in logs.
- Blocked customer text/number is dropped or handed off per config.

**Verify:**

```powershell
. .\dev-env.ps1
python -m alembic -c backend\alembic.ini upgrade head
python backend\tools\set_privacy_policy.py --blocklist-mode handoff
python backend\tools\manage_customer_block.py --client-id 17682c77-1524-4ebd-94e5-958e7f37ac60 --phone 919769825350 --add --type blocklist
# Restart wa_gateway + batch_processor
python backend\tools\reset_chat_ai_active.py --phone 919769825350
python backend\tools\dev_send_inbound.py --meta-phone-number-id 1098044196727032 --from +919769825350 --text "blocked test"
python backend\tools\dev_check.py
python backend\tools\show_observability_recent.py
python backend\tools\prune_observability.py --dry-run
```

Expect blocked inbound → `HUMAN_REQ`, no `AI_REPLY`; misfire previews show `[PHONE]` not raw digits when PII was logged.

## Chat W: Ops Tasks and Incident Response

**Status (2026-05-22):** Backend slice landed — migration `0026_ops_tasks`, `ops_tasks` + `ops_task_events`, auto-create from `insert_ops_alert_event`, `ops_api` `GET /ops/tasks` + `POST /ops/tasks/{id}/resolve`, CLI `list_ops_tasks.py` / `resolve_ops_task.py`.

Goal: align existing SOP/alerts with v5.3 incident task concepts.

Scope:

- [x] `ops_tasks` + audit `ops_task_events` (links optional `sop_run_id` from alert SOP run).
- [x] Auto-create on critical alerts (`alerts.ops_task_policy` types: DEAD spike, meta errors, billing, SLA breach, owner wait).
- [x] Operator tools + ops_api list/resolve with audit.
- [x] Keeps `ops_sops` / `ops_run_logs` (SOP auto-trigger unchanged).

Acceptance:

- Critical alert can create a task.
- Task can be resolved and audited.

**Verify:**

```powershell
. .\dev-env.ps1
python -m alembic -c backend\alembic.ini upgrade head
python backend\tools\fire_test_alert.py --type OUTBOX_DEAD_SPIKE
python backend\tools\list_ops_tasks.py --status open
python backend\tools\resolve_ops_task.py --task-id <uuid-from-list> --note "Chat W verified"
python backend\tools\list_ops_tasks.py --status resolved
```

Optional: `GET http://127.0.0.1:8087/ops/tasks` with super_admin JWT from `client_api` login.

## Chat X: Redis Introduction (Optional, Evidence-Gated)

**Status (2026-05-22):** Backend slice landed — `REDIS_ENABLED` (default off), `backend/shared/redis_client.py`, `redis_telemetry.py`, gateway dedupe mirror + `/health` redis block, `check_redis_health.py`, `flush_redis_telemetry.py`.

Goal: add Redis only where it earns its complexity.

Scope:

- [x] Redis configuration (`Settings.redis_*`) and health check (`check_redis_health`, gateway `/health`).
- [x] Optional telemetry stream buffer (`zy:telemetry:buffer` → `flush_redis_telemetry.py` → Postgres).
- [x] Optional dedupe mirror `processed:{meta_msg_id}` (gateway fast-path; PG insert still authoritative).
- [x] Postgres remains source of truth when Redis off or unreachable.

Acceptance:

- App works with Redis disabled.
- App gains Redis buffering/dedupe when enabled.

**Verify (disabled — default):**

```powershell
. .\dev-env.ps1
pip install redis==5.0.8
python backend\tools\check_redis_health.py
curl http://127.0.0.1:8081/health
```

Expect `redis.enabled: false`, app unchanged.

**Verify (enabled — optional local Redis):**

```powershell
# Install/run Redis locally (e.g. Docker: docker run -d -p 6379:6379 redis:7)
$env:REDIS_ENABLED = "true"
$env:REDIS_URL = "redis://127.0.0.1:6379/0"
python backend\tools\check_redis_health.py
# Restart wa_gateway 8081, send duplicate inbound with same wamid — second should skip via mirror
python backend\tools\flush_redis_telemetry.py
```

## Chat Y: GPU Sentinel and WSL Inference (Deferred Hardware Track)

**Status (2026-05-22):** Backend slice landed — `gpu_sentinel.py`, Redis keys `gpu:4090:status` (+ file fallback), `gpu_sentinel_cli.py`, `scripts/gpu_sentinel.ps1`, WSL stubs `scripts/wsl/start_llama_inference.sh`, `scripts/start_wsl_llama.ps1`. Ollama `:11435` unchanged.

Goal: implement the v5.3 dual-GPU sentinel only after the product path is stable.

Scope:

- [x] Sentinel script and status tools (`gpu_sentinel.ps1`, `show_gpu_status.py`).
- [x] Redis `gpu:4090:*` keys when `REDIS_ENABLED=true`; else `logs/gpu_sentinel_state.json`.
- [x] WSL/llama.cpp starter stubs for ports **8082** (owner) / **8083** (sales).
- [x] Ollama `11435` remains stable Gate 2 fallback (no routing change).

Acceptance:

- Sentinel can report/force BUSY/AVAILABLE.
- No disruption to current Ollama path.

**Verify:**

```powershell
. .\dev-env.ps1
python backend\tools\gpu_sentinel_cli.py status
.\scripts\gpu_sentinel.ps1 busy -Owner "dev-test" -Note "Chat Y"
.\scripts\gpu_sentinel.ps1 status
.\scripts\gpu_sentinel.ps1 available
python -c "import httpx; print(httpx.get('http://127.0.0.1:8083/health').json().get('gpu_sentinel'))"
```

With Redis: `$env:REDIS_ENABLED='true'` then busy/available — keys visible via `redis-cli GET gpu:4090:status`.

## Chat Z: Release Manager and Canary

**Status (2026-05-22):** Backend slice landed — extends `ops_releases` + `ops_release_events`, `release.canary_policy`, `ops_api` `/ops/releases*`, CLI tools, `scripts/rollback_release.ps1`, `docs/RELEASE_APPROVAL_CHECKLIST.md`.

Goal: introduce controlled release and rollback after telemetry/misfire signals are mature.

Scope:

- [x] Release registry (`ops_releases` + audit `ops_release_events`) and APIs.
- [x] Canary percent config (`release.canary_policy`; `disable_canary.py` / `POST .../canary/disable`).
- [x] Rollback script hooks (`rollback_ops_release.py`, `rollback_release.ps1`).
- [x] Approval checklist (`release.approval_checklist` + doc).

Acceptance:

- Release can be registered/promoted/rolled back.
- Canary can be disabled quickly.

**Verify:**

```powershell
. .\dev-env.ps1
python -m alembic -c backend\alembic.ini upgrade head
# If legacy ops_releases table: head must include 0029_align_ops_releases_schema
python backend\tools\inspect_ops_releases_schema.py
python backend\tools\register_ops_release.py --build-id dev-chatz-1 --git-sha local
python backend\tools\promote_ops_release.py --build-id dev-chatz-1 --canary-percent 5
python backend\tools\show_release_status.py
python backend\tools\disable_canary.py
python backend\tools\rollback_ops_release.py --build-id dev-chatz-1 --note "Chat Z test"
```

Expect promoted build, canary off after disable/rollback, `ops_release_events` rows for registered/promoted/rolled_back.

## Execution Rule

Start with Chat O. Do not begin Chat P until Chat O preflight is green against the current working stack.

Each chat should end with:

- migration status,
- commands run,
- manual test output,
- remaining known gaps,
- whether the next chat can start.
