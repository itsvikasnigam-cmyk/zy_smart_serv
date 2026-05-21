# Release approval checklist (Chat Z)

Use before **promoting** a build from `candidate` → `promoted`. Stored in `ops_runtime_config` key `release.approval_checklist` and surfaced at `GET /ops/releases/approval-checklist` (super_admin).

## Required checks

1. **Tests** — `pytest` green; optional `RUN_POSTGRES_INTEGRATION=1` when DB available.
2. **Contract** — `POST /ai/respond` and batch_processor JSON shape unchanged unless Stem approved.
3. **Routing** — Review `wa_gateway`, `batch_processor`, `ai_engine` diffs for inbound/outbound behavior.
4. **Billing** — If `billing_api` touched, webhook signature tests and entitlement mapping smoke.
5. **Config** — Document any `ops_runtime_config` key changes (prompts, limits, canary).
6. **Canary** — Start at **0%**; raise only after promote + observability review.
7. **Sign-off** — Super_admin operator recorded via `ops_release_events` (promote API or CLI).

## Quick commands

```powershell
. .\dev-env.ps1
python -m alembic -c backend\alembic.ini upgrade head
python backend\tools\register_ops_release.py --build-id dev-YYYYMMDD --git-sha <sha>
python backend\tools\show_release_status.py
python backend\tools\promote_ops_release.py --build-id dev-YYYYMMDD --canary-percent 0
# later: raise canary or rollback
python backend\tools\disable_canary.py
python backend\tools\rollback_ops_release.py --build-id dev-YYYYMMDD --note "reason"
```

## Rollback hook

```powershell
.\scripts\rollback_release.ps1 -BuildId dev-YYYYMMDD -Note "reason"
```

Rollback sets release `rolled_back`, writes audit events, and **disables canary** (`enabled=false`, `percent=0`).
