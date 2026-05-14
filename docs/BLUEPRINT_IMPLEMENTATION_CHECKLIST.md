# Blueprint implementation checklist (v6.0 / v6.1)

Living checklist vs the **Whatsapp Manager Blueprint** (product definition, architecture, DDL, API list, acceptance tests). Check items off as you ship; keep this file until the **meta task** at the end says otherwise.

**Related:** `HANDOFF.md` (stem context), `README.md` (runbooks + smoke).

## Parallel chat ownership (HANDOFF paste blocks)

| Checklist area | Owns implementation | Notes |
|----------------|--------------------|--------|
| § M2 gateway | **Chat B** | Chat K supplies usage reads; paywall hook may need B+K merge order via **Chat A** |
| § Workers (batch/outbox) | **Chat C** | Overlap with checklist A5/HANDOFF/NEEDS_OWNER — Stem assigns C vs coordinated PRs |
| § Workers (usage/metrics tables + jobs) | **Chat K** — **landed** (`0005_usage_metrics`, `usage_increment_worker.py`, `metrics_rollup_worker.py`) | **Enforcing** paywall / blocking enqueue remains **Chat B** (M2) + **Chat C** (batch) per HANDOFF |
| § M1 AI | **Chat D** | |
| § M5 billing + KYC + checkout | **Chat E** | Checkout routes stay **Chat E** (billing_api); **Chat J** is dashboard REST only |
| § M3 + § M4 REST/WS | **Chat F** | |
| § M4/M8 client UI | **Chat G** — **landed** (`flutter_app` + `mobile`: owner/agent inbox, WS, **`/dash/client/*`**) | **§ M4** backend state machine rows still open (Chat F/C); **device smoke** Stem/Chat N |
| § M8 control plane + § M9 UI | **Chat H** — **landed** (`flutter_app` / `mobile`: SOP library…runs, read-only M8 cards, admin dash reader) | **`ops_api`** + **`GET /dash/admin/*`**; device **smoke** = you / Chat N |
| § M9 APIs + schema | **Chat I** — **landed** (`backend/apps/ops_api/`, `0006_ops_sops`, `dev_ops_api_smoke.py`, `tests/test_ops_api_*.py`) | Includes **`GET /ops/sops/{id}/versions`** (Stem confirmed canonical). **§ M9 interactive UI** landed **Chat H** (`flutter_app` / `mobile`). |
| § M8 dashboard REST | **Chat J** — **landed** (`routes_dash.py`, dash models in `models.py`) | **M8 interactive control plane** UI remains **Chat H** |
| § M6 + § M7 | **Chat L** | |
| § M10 + CI | **Chat M** | |
| Tests + smoke | **Chat N** | |
| Ordering, merges, checklist `[x]` | **Chat A** | This chat |

---

## How to use

- Use `- [ ]` / `- [x]` in Markdown (or your editor’s task list).
- Prefer **one PR per section** (or smaller) so the list stays honest.
- When an item is **obsolete** (spec changed), edit the line instead of leaving a lie.

---

## M2 — WhatsApp gateway & outbound loop

- [ ] Inbound: signature verify → parse → **single DB transaction** per blueprint (store-first, dedupe `meta_msg_id`) — verify edge cases under load.
- [ ] **Never** call AI inside webhook handler (regression guard / comment / test).
- [ ] Debounce: baseline **3s / 10s cap** driven by `ops_runtime_config` — audited in staging.
- [ ] **Adaptive debounce** (`debounce.adaptive.enabled`, `debounce.adaptive.two_msgs_within_sec`): extend batch window when burst arrives (blueprint **A3**).
- [ ] **Urgent path at gateway** (**U1**): skip debounce when urgent keyword/intent matched (or equivalent: seal immediately) — align with blueprint (**U2** routing intent).
- [ ] Optional: `POST /webhooks/meta/errors` (Meta errors) if product needs it.
- [ ] **Trial / entitlement gate** on inbound: expired trial → inbound gets **“service inactive”** (per SOP); no silent accept.
- [ ] **Outbound paywall**: blocked client → `PAYWALL` (or policy) instead of normal AI/agent enqueue when limits/trial demand it.

---

## Workers & reliability

- [ ] **Batch processor**: if chat is **`AGENT_ACTIVE`** or **`ai_paused_until > now()`**, still seal batches but **do not** call AI / enqueue `AI_REPLY` (blueprint **A5**).
- [ ] **Batch processor — HANDOFF**: set **`HUMAN_REQ`** (or align name with `inbox_chats.state` enum), **auto-assign** agent using `agent_profiles.responsibilities`, enqueue **`OWNER_ALERT`** / notifications per spec (not only `PENDING_AGENT` + NOTIFY).
- [ ] **Batch processor — NEEDS_OWNER_DATA**: set **`WAITING_OWNER_DATA`**, enqueue **owner alert** + **customer** `wa_outbox` with **exact** blueprint fixed string (server constant; not agent-editable).
- [ ] **Urgent bypass outcome** (**U2**): route to **`HUMAN_REQ`** or **`WAITING_OWNER_DATA`** + assignment/owner alert — **no** “AI guesses” via generic `REPLY` if blueprint is strict.
- [ ] **Outbox sender**: retry/backoff, **DEAD** + owner/dashboard signal; idempotent Meta sends on worker crash (**staging E2E**).
- [x] **Worker: usage + plan gate** (`bill_usage_daily`, soft warn / hard block at thresholds) — **Chat K**: `usage_increment_worker.py` + `ops_runtime_config.usage.daily_inbound_limits`; *blocking* normal AI/outbound when hard cap hit is still **§ M2 outbound paywall / Chat B** (read `bill_usage_daily`).
- [x] **Worker: metrics rollup** → `metrics_daily_client`, `metrics_daily_agent`, `metrics_hourly_system` (tables + jobs) — **Chat K**: `metrics_rollup_worker.py` + migration `0005_usage_metrics`.

---

## M1 — AI engine

- [ ] Full **input** contract: history, personas, catalog, rules (as blueprint lists) — wire or stub explicitly.
- [ ] **Multilingual** detection + reply style (incl. Hinglish); quality gate.
- [ ] **External LLM** path + **cost-controlled** GPT fallback / judge (`ai.fallback.*` keys).
- [ ] Contract tests stable for `batch_processor` (JSON schema / golden files).

---

## M3 — Client API (auth, onboarding, catalog)

- [ ] `POST /signup` (trial, `trial_end`, default personas).
- [ ] OTP auth (`POST /auth/otp/start`, `POST /auth/otp/verify`) if product requires it (else document “email/password only” deviation).
- [ ] `GET /me` — align path with blueprint (`GET /me` vs `/auth/me`) or document mapping.
- [ ] Team: `POST/GET /team/users`, `PUT /team/users/{id}`, `PUT /team/agents/{id}/profile` (**`agent_profiles`** backed).
- [ ] Client: `PUT /client/profile`, `PUT /client/persona`.
- [ ] Catalog: `POST/GET/PUT/DELETE /catalog/items`, optional `POST /catalog/import` (CSV).

---

## M4 — Team inbox (state machine & productivity)

- [ ] Align **`inbox_chats.state`** with blueprint: **`AI_ACTIVE`**, **`HUMAN_REQ`**, **`AGENT_ACTIVE`**, **`CLOSED`**, **`WAITING_OWNER_DATA`** (migrate from `PENDING_AGENT` / `RESOLVED` if still in use).
- [ ] `POST /inbox/chats/{id}/resolve` → **`CLOSED`** + `ai_paused_until` behavior per plan.
- [ ] Agent reply sets **`ai_paused_until = now() + 24h`** for Starter (or config-driven).
- [ ] Reassignment: audit log + notify assignee + **CC owner** (configurable).
- [ ] Typing: team-only; optional **hard lock** (only assignee sends).
- [ ] Optional: `POST /inbox/chats/{id}/messages` alias or keep `/reply` — document in `HANDOFF.md`.
- [ ] WebSocket: add **`notification`** event type if missing; JWT auth story for **production** WS.

---

## Owner/agent Flutter UI (Chat G — `flutter_app` + `mobile`)

Shipped **without** changing super-admin SOP scope (Chat H). Does **not** satisfy full blueprint **§ M4** backend state machine until Chat F/C land migrations/APIs.

- [x] **Login / session:** `GET /auth/me` → reject unknown roles (clear token + error); **`wsLastError`**; WS connect **try/catch**; disconnect clears WS error; role snackbars; WS after login for tenant users; snackbar if WS fails but REST OK; password cleared on success.
- [x] **Nav + refresh:** `flutter_app` Inbox · Dashboard · Account; `mobile` Inbox · Dashboard · Settings (`HomeShell` tab order **0/1/2**); app bar **Refresh** → **`bumpDashGeneration()`** (inbox + dashboard).
- [x] **Inbox + thread:** filters (All / Mine / Unassigned / Needs agent), phone search, pull-to-refresh, retry, agent hint; assign / reassign / escalate / unassign (owner); assignment banner; **`mobile`** **`canUseTenantInboxApi`**, **`superAdminClientId`**, **`_cid(session)`** on inbox REST; typing/reply gated.
- [x] **Client dashboard (Chat J):** **`ClientDashboardScreen`** → **`GET /dash/client/overview|agents|quality`**; **401** → logout; **404** → mock preview + banner; no new pub deps.
- [x] **API client (`mobile`):** aligned with `flutter_app` — `listChats` query params, reassign/unassign/escalate, **`dashGet`**.
- [x] **Docs:** `flutter_app/README.md` + `mobile/README.md` — Chat G section + base URL table (Windows / emulator / device).

---

## M5 — Billing + KYC + usage

- [ ] India: **`POST /billing/razorpay/create-checkout`** (UPI vs card / plan codes) + pricing keys from control plane.
- [ ] Global: **`POST /billing/paddle/create-checkout`**.
- [ ] `GET /billing/subscription`, `GET /billing/invoices` (or provider-specific equivalents).
- [ ] **KYC entry** (India) — APIs + storage + status on client record.
- [ ] Webhooks: extend event coverage as blueprint requires (renewals, refunds, chargebacks, failures).
- [ ] **Plan gating** reads internal subscription + entitlements only (single source of truth).

---

## M6 — Broadcast

- [ ] Template-only sends; opt-in enforcement; **Trial/Starter blocked** per matrix.

---

## M7 — Analytics & alerts

- [ ] Aggregate tables fed by workers; **alerts**: dead letters, webhook spikes, ban signals, GPU throttling, SLA breach hooks.

---

## M8 — Dashboards & control plane

### APIs (backend)

- [x] Client: `GET /dash/client/overview`, `.../agents`, `.../quality` — **Chat J** (`backend/apps/client_api/routes_dash.py`).
- [x] Super-admin: `GET /dash/admin/overview`, `.../collections`, `.../providers/razorpay`, `.../providers/paddle`, `.../ops/whatsapp`, `.../admin/geo` (phase 1 aggregates) — **Chat J**; checklist alias `GET /dash/admin/admin/geo` for blueprint path typo.

### Interactive control plane (super-admin UI)

Blueprint calls for an **Admin → Control Plane** experience (not only REST). Track **Flutter and/or web** — pick one primary surface and list the other as optional.

- [ ] **Runtime config editor**: key/value by type, validation, last editor + timestamp, **revert** using `ops_runtime_config_audit`.
- [ ] **Pricing panel (India)**: `pricing.in.*` minor units, live **preview** (“UPI = ₹X”, “Card = ₹Y”).
- [ ] **Debounce panel**: seconds, max, adaptive toggles.
- [ ] **Urgent bypass panel**: keywords + intents arrays (`routing.urgent_*` or aligned keys).
- [ ] **AI fallback panel**: enable, judge, band, `max_rate_per_client`.
- [x] **Client dashboard (Flutter)**: usage, handoffs, missing-data hotspots, agent performance charts — **Chat G v1**: **`ClientDashboardScreen`** wired to **`GET /dash/client/*`** (`401` logout, `404` mock + banner); richer charts TBD.
- [ ] **Super-admin dashboard (Flutter Android + Windows)**: revenue, collections mix, outbox backlog, number health, geography phase 1 (charts).

---

## M9 — SOP / Runbook Center (in-system) — **APIs + interactive product**

**Backend (`ops_api`, Chat I) is landed** — see § **Data & APIs** below. **Interactive SOP / Runbook UI (Chat H)** is **landed** in **`flutter_app/`** (and **`mobile/`** parity per HANDOFF); remaining checklist items here are **phase-2 auto-trigger**, **day-1 SOP seed content**, and **optional PDF**.

### Data & APIs

- [x] Migrations: **`ops_sops`**, **`ops_sop_versions`**, **`ops_run_logs`** (+ indexes) — Alembic **`0006_ops_sops`**; FastAPI **`backend/apps/ops_api/`** (Stem: dedicated app, not `client_api`).
- [x] `GET/POST /ops/sops`, `GET/PUT /ops/sops/{id}` (versioning on update via `ops_sop_versions`).
- [x] `GET /ops/sops/{sop_id}/versions` — list immutable version bodies for history / diff / restore (**Chat I** `routes_ops.py`; **Chat H** consumes only).
- [x] `POST /ops/sops/{id}/run` → creates **`ops_run_logs`** row with `context_json`.
- [x] `GET /ops/runs`, `GET /ops/runs/{run_id}` (filters: `client_id`, `sop_id`, `from_date`, `to_date`, `trigger_type`).

### Interactive SOP / Runbook UI (super-admin) — **shipped (Chat H); phase 2 below**

This is the **dashboard / interactive solution** for SOPs (not a static Markdown file in the repo alone). **Auto-trigger** and **day-1 seed content** remain open.

- [x] **SOP library screen**: list by category, search, status (`active` / `archived`). — **`flutter_app`**: `SuperAdminShell` → SOPs tab → `SopLibraryScreen` (`GET /ops/sops` query params `q`, `category`, `status`).
- [x] **SOP detail**: rendered Markdown **preview** + metadata (owner, version, last updated). — **`SopDetailScreen`** + `flutter_markdown`.
- [x] **Editor**: split or tabbed **Markdown editor** with preview; **save** creates new **version** (immutable history). — **`SopEditorScreen`** (POST create / PUT update); preview can be added as a tab later.
- [x] **Version history**: timeline, **diff** between versions, **restore** prior version (writes new version + audit). — **`GET /ops/sops/{id}/versions`** (Chat I extension) + `SopVersionsScreen` (diff unified/side-by-side; restore opens editor then PUT).
- [x] **Run flow**: “Start run” captures **context** (client id, wa number, error codes, links to dead outbox rows, free text) → POST run → show **run id**. — **`SopRunStartScreen`** (`POST /ops/sops/{id}/run`).
- [x] **Run log UI**: searchable table + **run detail** (steps checklist optional; at minimum show context + timestamps + user). — **`SopRunsListScreen`**, **`SopRunDetailScreen`** (`GET /ops/runs`, `GET /ops/runs/{id}`); filters for `sop_id` / `client_id`.
- [ ] **Auto-trigger wiring** (phase 2): e.g. outbox **DEAD** spike → create run + task + in-app notification + deep link into run detail.
- [ ] **Day-1 SOP content** seeded or imported: India provisioning, BYON, trial expiry, payment failure, dead-letter recovery, webhook downtime, ban recovery, backup drill, key rotation, release rollback (as blueprint lists).

### Optional

- [ ] Export SOP as PDF / printable runbook for audits.

---

## M10 — Release manager

- [ ] `GET/POST /ops/releases*`: register build + test report hash, promote, rollback (admin-gated).
- [ ] CI: expand beyond pytest-only (Postgres service, contract/integration jobs, optional `RUN_WA_GATEWAY_E2E`).
- [ ] Manual approval hooks documented for AI / routing / billing changes.

---

## Cross-cutting

- [ ] **`ZY_BASE_DIR`** (or equivalent): no hardcoded `C:\` paths; logs/exports/model cache derived from config (blueprint §10).
- [ ] **Acceptance tests** in repo: debounce **A1–A5**, urgent **U1–U2**, NEEDS_OWNER fixed string, burst → single reply E2E.
- [ ] Staging environment mirrors prod behavior (numbers + payment sandboxes).

---

## Meta — lifecycle of *this* checklist

- [ ] **Remove this file** (`docs/BLUEPRINT_IMPLEMENTATION_CHECKLIST.md`) **and** the README pointer to it when **all** of the following are true:
  - every open product item lives in your **external** tracker (Jira/Linear/etc.) with links, **or** the spec is frozen and `HANDOFF.md` alone tracks remaining deltas; and
  - the team agrees the checklist has **no unique content** left (no unchecked boxes that aren’t duplicated elsewhere).
- [ ] If you **keep** a single in-repo tracker instead, replace this file with a short stub pointing to `HANDOFF.md` + external board — then delete the long checklist.
