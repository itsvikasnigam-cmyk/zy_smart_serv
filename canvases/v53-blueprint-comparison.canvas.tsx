import { Divider, Grid, H1, H2, Stack, Stat, Table, Text } from "cursor/canvas";

const summaryRows = [
  ["M0 Store-first gateway", "Mostly done, different shape", "wa_gateway on 8081, HMAC, DB store-first, no AI inline, real inbound tested. Redis queue and port-8000 webhook.py are intentionally not used."],
  ["M1 AI orchestration", "Partial / working core", "batch_processor + ai_engine + local Ollama Gate 2 verified. No dual-LoRA grammar router, Redis session context, 4090 arbitration, EXECUTE_ORDER, or full tone clamp."],
  ["M2 Multi-modal / RAG", "Pending", "Image OCR, voice STT, document parsing, PGVector knowledge retrieval are not implemented in the current Option C path."],
  ["M3 Client API & Inbox", "Mostly done", "client_api 8085, Flutter Inbox, assignment states, human queue, replies, notifications, dashboards. SLA breach worker implemented. Redis typing locks and Meta 24h template fallback remain pending."],
  ["M4 Billing / plans", "Partial", "3-day trial, 35/day trial/starter caps, paywall replies and usage tables exist. Razorpay/Paddle production billing, FX/GST/margin formula remain deferred."],
  ["M5 Observability", "Good MVP done", "telemetry_trace_logs, misfires_log, trace propagation gateway -> batch -> AI verified. Redis stream buffering, retention pruning, rich cost dashboards pending."],
  ["M6 Release / LoRA", "Pending", "No model adapter symlink versioning, canary percentage router, automated rollback, or approval workflow yet."],
  ["M7 VRAM sentinel", "Pending / deferred", "Project-local Ollama exists under ZY_BASE_DIR. Redis gpu:4090 status, NSSM sentinel, WSL llama.cpp, dual-GPU eviction not implemented."],
  ["M8 Outbox delivery", "Core done", "Durable wa_outbox, retry/dead handling, status handling, real WhatsApp SENT verified. Rate bucket, 24h template fallback, and campaign pacing hardening pending."],
  ["M9 SOP / incidents", "Partial", "ops_sops, ops_run_logs, alert events, some auto-trigger and Slack hooks exist. ops_tasks exact schema, Redis watchdog, one-click rollback pending."],
  ["M10 Security / compliance", "Partial", "HMAC and tenant scoping exist. DPDP aggregation, TRAI/DND blocklist, PII redaction, hard DB RLS are not complete."],
];

const verifiedRows = [
  ["Gate 1", "Inbound -> DB -> batch -> outbox -> Flutter Inbox", "Verified"],
  ["Gate 2", "Local Ollama on 11435 + ai_engine 8083 /ai/respond", "Verified"],
  ["Real WhatsApp send", "wa_outbox SENT with Meta wamid", "Verified"],
  ["Telemetry", "wa_gateway, batch_processor, ai_engine trace rows", "Verified"],
  ["Path portability", "ZY_BASE_DIR + local Ollama vendor/models", "Implemented"],
];

const pendingRows = [
  ["Production hosting", "Use VPS/dedicated server, HTTPS, firewall, backups; not daily PC exposure."],
  ["Long-lived Meta token", "Temporary token worked but should be replaced with System User token."],
  ["Webhook public URL", "Meta inbound from real phones requires public HTTPS tunnel or hosted gateway."],
  ["Billing production", "Razorpay/Paddle activation and webhook validation."],
  ["Redis/WSL/GPU sentinel", "Deferred until load or hardware architecture needs it."],
  ["Multi-modal/RAG", "OCR, STT, document ingestion, PGVector knowledge."],
  ["Compliance hardening", "DND/blocklists, PII redaction, DPDP retention, RLS."],
];

export default function BlueprintComparison() {
  return (
    <Stack gap={20}>
      <H1>ZY Smart AI v5.3 Blueprint Comparison</H1>
      <Text>
        Current implementation follows the Option C decision: keep the existing v6-style FastAPI/Postgres worker
        architecture and import v5.3 behavior incrementally, rather than rebasing to the exact v5.3 Redis/WSL/port-8000 design.
      </Text>

      <Grid columns={4} gap={16}>
        <Stat value="5" label="Verified capabilities" tone="success" />
        <Stat value="4" label="Mostly or partially complete modules" tone="warning" />
        <Stat value="4" label="Major deferred modules" tone="danger" />
        <Stat value="0" label="Need for D: move now" />
      </Grid>

      <Divider />

      <H2>Module Status</H2>
      <Table
        headers={["Blueprint area", "Current status", "Evidence / gap"]}
        rows={summaryRows}
      />

      <Divider />

      <H2>Verified On This Machine</H2>
      <Table
        headers={["Area", "What was tested", "Status"]}
        rows={verifiedRows}
      />

      <Divider />

      <H2>Main Pending Work Before Production</H2>
      <Table
        headers={["Pending area", "Why it matters"]}
        rows={pendingRows}
      />

      <Text tone="secondary" size="small">
        Source: current repo state and manual test results through May 21, 2026.
      </Text>
    </Stack>
  );
}
