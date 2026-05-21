"""Chat W: ops_tasks + audit events for incident response.

Revision ID: 0026_ops_tasks
Revises: 0025_phase5_privacy
"""

from __future__ import annotations

import json

from alembic import op

revision = "0026_ops_tasks"
down_revision = "0025_phase5_privacy"
branch_labels = None
depends_on = None

_TASK_POLICY = {
    "enabled": True,
    "min_severity": "warning",
    "alert_types": [
        "OUTBOX_DEAD_SPIKE",
        "META_WEBHOOK_ERROR_SPIKE",
        "BILLING_WEBHOOK_PROCESSING_ERROR",
        "INBOX_AGENT_SLA_BREACH",
        "OWNER_WAIT_8H",
    ],
}

_POLICY_JSON = json.dumps(_TASK_POLICY).replace("'", "''")


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS ops_tasks (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          title TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'open'
            CHECK (status IN ('open', 'resolved', 'cancelled')),
          priority TEXT NOT NULL DEFAULT 'normal'
            CHECK (priority IN ('critical', 'high', 'normal')),
          alert_type TEXT NOT NULL,
          alert_dedupe_key TEXT,
          summary TEXT NOT NULL,
          detail_json JSONB NOT NULL DEFAULT '{{}}'::jsonb,
          client_id UUID REFERENCES api_clients(id) ON DELETE SET NULL,
          sop_run_id UUID REFERENCES ops_run_logs(id) ON DELETE SET NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          resolved_at TIMESTAMPTZ,
          resolved_by_user_id UUID REFERENCES api_users(id) ON DELETE SET NULL,
          resolution_note TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS ops_tasks_alert_dedupe_uniq
          ON ops_tasks(alert_dedupe_key)
          WHERE alert_dedupe_key IS NOT NULL;
        CREATE INDEX IF NOT EXISTS ops_tasks_status_created_idx
          ON ops_tasks(status, created_at DESC);
        CREATE INDEX IF NOT EXISTS ops_tasks_alert_type_idx
          ON ops_tasks(alert_type, created_at DESC);

        CREATE TABLE IF NOT EXISTS ops_task_events (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          task_id UUID NOT NULL REFERENCES ops_tasks(id) ON DELETE CASCADE,
          action TEXT NOT NULL CHECK (action IN ('created', 'resolved', 'cancelled', 'reopened')),
          actor_user_id UUID REFERENCES api_users(id) ON DELETE SET NULL,
          note TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ops_task_events_task_created_idx
          ON ops_task_events(task_id, created_at DESC);

        INSERT INTO ops_runtime_config (key, value_json)
        VALUES ('alerts.ops_task_policy', '{_POLICY_JSON}'::jsonb)
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM ops_runtime_config WHERE key = 'alerts.ops_task_policy';
        DROP TABLE IF EXISTS ops_task_events;
        DROP TABLE IF EXISTS ops_tasks;
        """
    )
