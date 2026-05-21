from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root (parent of backend/) — env files resolve here regardless of process cwd.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILES = (
    _REPO_ROOT / ".env",
    _REPO_ROOT / "backend" / ".env",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=tuple(str(p) for p in _ENV_FILES if p.exists()) or None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = Field(default="dev", description="dev|staging|prod")
    database_url: str = Field(default="postgresql+psycopg://postgres:postgres@localhost:5432/zysmart")

    zy_base_dir: str = Field(
        default="",
        description=(
            "Workspace root for logs/exports/models. Dev: repo path on C:. "
            "Prod (Option C): e.g. D:\\zy-smart-ai. Empty = auto-detect repo root."
        ),
    )

    meta_app_secret: str = Field(default="", description="Meta app secret for webhook signature validation")
    meta_verify_token: str = Field(default="change-me", description="Meta webhook verify token")
    meta_access_token: str = Field(
        default="",
        description="Required for outbox_sender: Meta Cloud API system-user or long-lived token used to POST /messages",
    )
    meta_graph_version: str = Field(
        default="v22.0",
        description="Required for outbox_sender: Graph API version segment in https://graph.facebook.com/{version}/… (e.g. v22.0)",
    )

    wa_gateway_allow_client_id_header: bool = Field(
        default=False,
        description=(
            "When true, wa_gateway accepts X-ZY-Client-Id as a last-resort client route in dev-like setups. "
            "Keep false in staging/prod; prefer wa_numbers + wa_trial_map routing only."
        ),
    )

    outbox_max_attempts: int = Field(default=15, ge=1, description="Outbox: after this many failed send attempts, row is marked DEAD")
    outbox_sending_lease_seconds: int = Field(
        default=120,
        ge=10,
        description="Outbox: SENDING lease; if a worker dies mid-send, row becomes eligible again after this (see worker comments on duplicates)",
    )

    # client_api (M3/M4: inbox + assignments + WS)
    client_api_jwt_secret: str = Field(
        default="dev-insecure-change-me",
        description="HS256 signing secret for client_api JWTs. MUST be set to a strong random value in staging/prod.",
    )
    client_api_jwt_ttl_minutes: int = Field(
        default=720,
        ge=5,
        description="Access token lifetime for client_api login JWTs (default 12h).",
    )
    client_api_event_poll_ms: int = Field(
        default=500,
        ge=100,
        description="client_api WS background poll interval (ms) for cross-process events (new messages, assignments, outbox).",
    )
    client_api_cors_origins: str = Field(
        default="*",
        description="Comma-separated CORS origins for client_api (set explicit origins in non-dev).",
    )
    client_api_ws_allowed_origins: str = Field(
        default="",
        description=(
            "Comma-separated browser Origin values allowed for GET /ws (exact string match after trim). "
            "Empty means do not enforce Origin (typical in local dev). Set explicit https://… origins in "
            "staging/production so only your web apps may open a socket; pair with WSS and short-lived JWTs."
        ),
    )

    # ops_api (M9: SOP / Runbook Center — same JWT as client_api)
    ops_api_cors_origins: str = Field(
        default="*",
        description="Comma-separated CORS origins for ops_api (set explicit origins in non-dev).",
    )

    # billing_api (M5: Razorpay + Paddle webhooks)
    billing_razorpay_webhook_secret: str = Field(
        default="",
        description="Razorpay webhook signing secret (Dashboard → Webhooks). Required to accept POST /webhooks/razorpay.",
    )
    billing_paddle_webhook_secret: str = Field(
        default="",
        description="Paddle Billing notification destination secret. Required to accept POST /webhooks/paddle.",
    )
    billing_razorpay_key_id: str = Field(
        default="",
        description="Razorpay Key ID for REST API (create order / checkout). Not the webhook secret.",
    )
    billing_razorpay_key_secret: str = Field(
        default="",
        description="Razorpay Key Secret for REST API. Keep out of git; use env / secrets manager.",
    )
    billing_paddle_api_key: str = Field(
        default="",
        description="Paddle Billing API key (Bearer) for POST /transactions (create-checkout).",
    )
    billing_paddle_environment: str = Field(
        default="sandbox",
        description="paddle environment: sandbox|production (selects api.paddle.com vs sandbox-api.paddle.com).",
    )
    billing_paddle_api_version: str = Field(
        default="1",
        description="Paddle-Version header value for Billing API requests (provider default often 1).",
    )
    billing_api_cors_origins: str = Field(
        default="*",
        description="Comma-separated CORS origins for billing_api REST (checkout from browser).",
    )

    # Chat K: usage_increment_worker + metrics_rollup_worker (see HANDOFF.md)
    usage_worker_batch_size: int = Field(
        default=500,
        ge=50,
        le=5000,
        description="Max inbox_messages rows applied per usage_increment_worker tick.",
    )
    usage_worker_sleep_seconds: float = Field(
        default=2.0,
        ge=0.5,
        description="Sleep between usage_increment_worker ticks when caught up or after errors.",
    )
    metrics_rollup_sleep_seconds: float = Field(
        default=300.0,
        ge=15.0,
        description="Sleep between metrics_rollup_worker full rollup cycles.",
    )
    metrics_rollup_lookback_days: int = Field(
        default=3,
        ge=1,
        le=30,
        description="UTC calendar days (today .. today-N+1) recomputed each metrics rollup.",
    )
    metrics_rollup_hourly_lookback: int = Field(
        default=48,
        ge=1,
        le=168,
        description="Number of recent UTC hour buckets metrics_hourly_system refreshes each cycle.",
    )

    broadcast_worker_sleep_seconds: float = Field(
        default=2.0,
        ge=0.5,
        description="Sleep between broadcast_campaign_worker ticks when idle or after errors.",
    )
    broadcast_worker_batch_size: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Max wa_broadcast_targets rows processed per campaign tick.",
    )
    alert_eval_worker_sleep_seconds: float = Field(
        default=120.0,
        ge=15.0,
        description="Sleep between alert_eval_worker evaluations (M7 spike → ops_alert_events).",
    )
    inbox_sla_watchdog_sleep_seconds: float = Field(
        default=60.0,
        ge=15.0,
        description="Sleep between inbox_sla_watchdog ticks (owner-wait 4h/8h + agent SLA).",
    )
    batch_ai_engine_timeout_seconds: float = Field(
        default=120.0,
        ge=5.0,
        description="httpx timeout for batch_processor -> POST /ai/respond (Gate 2 local LLM needs more than 10s).",
    )
    ops_alert_slack_webhook_url: str = Field(
        default="",
        description="Optional Slack incoming webhook for new ops_alert_events (overrides DB if set).",
    )

    # Chat X: optional Redis (Postgres remains source of truth; Redis is best-effort).
    redis_enabled: bool = Field(
        default=False,
        description="Master switch. When false, dedupe mirror and telemetry buffer are no-ops.",
    )
    redis_url: str = Field(
        default="redis://127.0.0.1:6379/0",
        description="Redis connection URL (redis://host:port/db).",
    )
    redis_dedupe_mirror_enabled: bool = Field(
        default=True,
        description="When redis_enabled, mirror processed:{meta_msg_id} keys at gateway.",
    )
    redis_dedupe_ttl_seconds: int = Field(
        default=604800,
        ge=3600,
        description="TTL for processed:{meta_msg_id} dedupe mirror keys (default 7 days).",
    )
    redis_telemetry_buffer_enabled: bool = Field(
        default=True,
        description="When redis_enabled, XADD trace payloads to a Redis stream before/alongside PG.",
    )
    redis_telemetry_stream_key: str = Field(
        default="zy:telemetry:buffer",
        description="Redis stream key for buffered telemetry_trace rows.",
    )

    # Chat Y: GPU VRAM sentinel (Redis keys or file under ZY_BASE_DIR/logs).
    gpu_redis_key_prefix: str = Field(
        default="gpu:4090",
        description="Redis key prefix for GPU sentinel (status at gpu:4090:status).",
    )
    gpu_sentinel_state_file: str = Field(
        default="logs/gpu_sentinel_state.json",
        description="File fallback when Redis disabled or unreachable.",
    )

    # ai_engine (M1 / Gate 2): optional OpenAI-compatible chat completions (primary + judge).
    # Empty API key + local base URL (e.g. Ollama :11434) uses placeholder bearer when ai.fallback.enabled.
    ai_llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="Base URL for OpenAI-compatible Chat Completions (no trailing path).",
    )
    ai_llm_api_key: str = Field(
        default="",
        description="Bearer API key for LLM calls. Never commit; set via env AI_LLM_API_KEY.",
    )
    ai_llm_primary_model: str = Field(
        default="gpt-4o-mini",
        description="Model id for the primary customer reply (Chat Completions).",
    )
    ai_llm_judge_model: str = Field(
        default="gpt-4o-mini",
        description="Model id for the optional quality judge pass.",
    )


settings = Settings()

