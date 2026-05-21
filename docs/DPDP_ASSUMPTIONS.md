# DPDP assumptions and gaps (Chat V)

This document records **engineering assumptions** for India’s Digital Personal Data Protection Act (DPDP) readiness in the Option C stack. It is **not legal advice**.

## What Chat V implements

| Control | Behavior |
|--------|----------|
| PII redaction | Phone (10–15 digit runs), email, and card-like sequences in `telemetry_trace_logs.meta`, `misfires_log.batch_text_preview`, and `misfires_log.detail` via `backend/shared/pii_redaction.py` |
| Customer blocklist / DND | Table `customer_blocks`; gateway checks before AI batching |
| Block modes | `privacy.policy.blocklist_mode`: **`drop`** (no inbox write) or **`handoff`** (store message, `HUMAN_REQ`, optional `SYSTEM` reply) |
| Retention | `privacy.policy.telemetry_retention_days` (default 30); `backend/tools/prune_observability.py` |
| Batch defense | `batch_processor` skips `/ai/respond` when number is blocked |

## Data still held in full (by design)

- **`inbox_messages.text`** — operator inbox needs message bodies; not redacted at rest in Chat V.
- **`inbox_chats.customer_phone`** — routing key; required for WhatsApp delivery.
- **Meta webhook payloads** in `inbox_messages.meta_payload` — may contain identifiers until a future media/PII minimization pass.

## Gaps vs a full DPDP program

- No consent ledger tied to purpose/lawful basis per message type.
- No automated data-subject access/erasure API (export/delete my data).
- No field-level encryption at rest for inbox bodies.
- No RLS on tenant tables in this repo slice (blueprint M10 remainder).
- No TRAI DND registry sync — only **tenant-managed** `customer_blocks` with `block_type=dnd`.
- No cross-border transfer register or processor DPAs in code.
- Pruning is **manual/scheduled script**, not guaranteed cron in all environments.

## Operational recommendations

1. Run `prune_observability.py` on a schedule (e.g. weekly Task Scheduler).
2. Use **`drop`** for numbers that must not be stored; **`handoff`** when agents must see context.
3. Restrict `show_observability_recent.py` to operators with admin access.
4. Revisit inbox retention and erasure in a later stem chat before public launch.

## Verification (dev)

```powershell
. .\dev-env.ps1
python -m alembic -c backend\alembic.ini upgrade head
python backend\tools\set_privacy_policy.py --blocklist-mode handoff
python backend\tools\manage_customer_block.py --client-id <uuid> --phone 919769825350 --add --type blocklist
python backend\tools\dev_send_inbound.py --meta-phone-number-id 1098044196727032 --from +919769825350 --text "test"
python backend\tools\dev_check.py
```

Expect `HUMAN_REQ` and no new `AI_REPLY` when blocked in handoff mode; in drop mode expect no new `inbox_messages` row.
