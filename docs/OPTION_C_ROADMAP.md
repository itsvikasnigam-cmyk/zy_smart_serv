# Option C roadmap (v6 repo + v5.3 ideas)

**Decision:** Keep **`empty-window`** architecture (8081/8083/8085/8087 + workers). Import Blueprint v5.3-WIN11 features incrementally. **Do not** re-base on `C:\zy-smart-ai\` port 8000 + Redis-first M0 unless explicitly replanned.

## Path policy (C: now → D: later)

| Phase | Code / repo | `ZY_BASE_DIR` | Database |
|-------|-------------|---------------|----------|
| **Now (dev)** | `C:\Users\TV_Station\.cursor\projects\empty-window` | Same path (set by `dev-env.ps1`) | Postgres on localhost `zysmart` |
| **Later (prod)** | Copy or clone to `D:\zy-smart-ai` (your choice of folder name) | `ZY_BASE_DIR=D:\zy-smart-ai` in `backend\.env` | Same DB name or new instance on D: |

Logs, exports, and model files use `backend/shared/paths.py` → under `ZY_BASE_DIR/logs`, `exports`, `models`.

**Not moved yet:** PostgreSQL data directory, Redis, WSL, GPU weights — plan those when you cut over to D:.

## What we keep (frozen structure)

- `wa_gateway` :8081 — store-first inbound (no AI in webhook)
- `batch_processor` + `ai_engine` :8083
- `client_api` :8085 + Flutter `flutter_app`
- `ops_api` :8087, `billing_api` :8086
- Alembic migrations in `backend/migrations/`
- Tuning via `ops_runtime_config` (matches v5.3 freeze spirit)

## Phased imports from v5.3 (behavior, not rewrite)

### Phase 1 — Done / stabilize
- [x] Gate 1 pipeline (inbound → batch → AI → outbox → Inbox UI)
- [ ] Fix outbox `DEAD` (valid `META_ACCESS_TOKEN`) or document dev-only DB replies
- [ ] Keep single gateway on 8081 (`scripts/start_wa_gateway.ps1`)

### Phase 2 — Config & product (low risk)
- [x] Trial length via `ops_runtime_config` `product.trial_days_default` (3) + signup omits `trial_days` to use DB default
- [x] Conversation hard cap trial/starter **35/day** (`usage.daily_inbound_limits`) + `m2.usage_hard_customer_reply`
- [x] Plan display: internal `growth` → **Enterprise** (`product.plan_display_aliases`)
- [x] Run migration `0017_option_c_phase2_product` (or `python backend/tools/apply_phase2_config.py`)

### Phase 3 — Gate 2 AI (medium)
- [x] Ollama / OpenAI-compatible `AI_LLM_BASE_URL` (local base URL works without cloud API key)
- [x] `enable_gate2_ollama.py` + `show_gate2_config.py` + `test_ai_respond_local.py`
- [x] Migration `0018_gate2_ai_fallback_seeds` (ai.fallback.* keys)
- [x] `scripts/setup_ollama_local.ps1` + `start_ollama_local.ps1` (vendor + models under `ZY_BASE_DIR`)
- [x] Local Ollama on **:11435** + Gate 2 smoke (`test_ai_respond_local.py`)
- [ ] Optional: read `gpu:4090:status` from Redis **later** (skip until Redis exists)

### Phase 4 — Owner-wait & SLA (medium)
- [x] Migration `0019_option_c_phase4_owner_sla` + worker `inbox_sla_watchdog.py`
- [x] `WAITING_OWNER_DATA`: 4h owner re-alert, 8h customer apology + `OWNER_WAIT_8H` ops alert + SOP hook
- [x] `sla_breach_at` when agent slow on `HUMAN_REQ` / `AGENT_ACTIVE` (default 30m, `inbox.sla.agent_response_minutes`)
- [ ] You run: `alembic upgrade head` + start `python backend\workers\inbox_sla_watchdog.py`

### Phase 5 — Observability (additive schema)
- [x] Migration `0020_phase5_observability` (`telemetry_trace_logs`, `misfires_log`)
- [x] Wired: `wa_gateway`, `ai_engine`, `batch_processor` + `show_observability_recent.py`
- [x] `batch_ai_engine_timeout_seconds` default **120s** (was 10s httpx — too short for Ollama)
- [ ] You run: `alembic upgrade head`, restart **8081/8083/batch**, one inbound, `show_observability_recent.py`
- [ ] Optional Redis stream flush — **only if** Postgres write pressure appears

### Phase 6 — Deferred (v5.3 hardware stack)
- [ ] Redis `batch_queue` + `processed:{meta_msg_id}` (replace only if Postgres dedupe insufficient)
- [ ] WSL llama.cpp dual-LoRA ports 8082/8083
- [ ] VRAM sentinel / NSSM ZYSentinel
- [ ] PGVector `client_knowledge`, media_gate OCR/STT

### Phase 7 — Move to D: drive (when you choose)
- [ ] Copy repo to `D:\zy-smart-ai`
- [ ] Set `ZY_BASE_DIR=D:\zy-smart-ai` in `backend\.env`
- [ ] Re-point Postgres `DATABASE_URL` if data lives on D:
- [ ] Update Flutter `--dart-define` URLs if APIs bind new host
- [ ] Windows Task Scheduler / NSSM for workers (optional)

## Explicitly out of scope for Option C (unless Stem reopens)

- Second gateway `webhook.py` on port 8000
- Renaming `inbox_messages` → `inbound_messages` without migration plan
- Replacing `ops_sops` / `ops_run_logs` with v5.3 `ops_tasks`-only model
- Mandatory Redis on hot path before load testing says so

## Dev commands (unchanged)

```powershell
cd C:\Users\TV_Station\.cursor\projects\empty-window; . .\dev-env.ps1
```

See `README.md`, `HANDOFF.md`, `docs/PRE_PRODUCTION_GATE.md`.
