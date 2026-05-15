"""M6 broadcast (opt-in, plan matrix) + M7 alert events + outbox dead_at

Revision ID: 0010_m6_m7_broadcast_alerts
Revises: 0009_billing_kyc_invoices
Create Date: 2026-05-14

"""

from __future__ import annotations

from alembic import op

revision = "0010_m6_m7_broadcast_alerts"
down_revision = "0009_billing_kyc_invoices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE wa_outbox
          ADD COLUMN IF NOT EXISTS dead_at TIMESTAMPTZ;
        CREATE INDEX IF NOT EXISTS wa_outbox_dead_at_idx
          ON wa_outbox(dead_at)
          WHERE dead_at IS NOT NULL;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_marketing_opt_in (
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          customer_phone_e164 TEXT NOT NULL,
          opted_in BOOLEAN NOT NULL DEFAULT false,
          source TEXT,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (client_id, customer_phone_e164)
        );
        CREATE INDEX IF NOT EXISTS customer_marketing_opt_in_client_idx
          ON customer_marketing_opt_in(client_id, opted_in);
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS wa_broadcast_campaigns (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          from_wa_number_id UUID NOT NULL REFERENCES wa_numbers(id),
          template_name TEXT NOT NULL,
          template_language TEXT NOT NULL DEFAULT 'en_US',
          status TEXT NOT NULL CHECK (status IN ('draft','queued','running','completed','cancelled','failed')) DEFAULT 'draft',
          created_by_user_id UUID REFERENCES api_users(id),
          error_message TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          started_at TIMESTAMPTZ,
          finished_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS wa_broadcast_campaigns_client_status_idx
          ON wa_broadcast_campaigns(client_id, status, created_at DESC);
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS wa_broadcast_targets (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          campaign_id UUID NOT NULL REFERENCES wa_broadcast_campaigns(id) ON DELETE CASCADE,
          chat_id UUID NOT NULL REFERENCES inbox_chats(id) ON DELETE CASCADE,
          customer_phone_e164 TEXT NOT NULL,
          status TEXT NOT NULL CHECK (status IN (
            'pending','skipped_no_optin','skipped_plan','skipped_template_policy',
            'enqueued','failed'
          )) DEFAULT 'pending',
          skip_detail TEXT,
          wa_outbox_id UUID REFERENCES wa_outbox(id) ON DELETE SET NULL,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (campaign_id, chat_id)
        );
        CREATE INDEX IF NOT EXISTS wa_broadcast_targets_campaign_status_idx
          ON wa_broadcast_targets(campaign_id, status);
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ops_alert_events (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          alert_type TEXT NOT NULL,
          severity TEXT NOT NULL DEFAULT 'warning' CHECK (severity IN ('info','warning','error')),
          summary TEXT NOT NULL,
          detail_json JSONB NOT NULL DEFAULT '{}'::jsonb,
          dedupe_key TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS ops_alert_events_type_created_idx
          ON ops_alert_events(alert_type, created_at DESC);
        CREATE UNIQUE INDEX IF NOT EXISTS ops_alert_events_dedupe_key_uniq
          ON ops_alert_events(dedupe_key)
          WHERE dedupe_key IS NOT NULL;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bill_webhook_processing_errors (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          provider TEXT NOT NULL CHECK (provider IN ('razorpay','paddle')),
          detail TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS bill_webhook_processing_errors_created_idx
          ON bill_webhook_processing_errors(created_at DESC);
        """
    )

    op.execute(
        """
        ALTER TABLE metrics_hourly_system
          ADD COLUMN IF NOT EXISTS billing_webhook_process_errors INT NOT NULL DEFAULT 0,
          ADD COLUMN IF NOT EXISTS wa_meta_webhook_errors INT NOT NULL DEFAULT 0;
        """
    )

    op.execute(
        """
        INSERT INTO ops_runtime_config (key, value_json)
        VALUES
          (
            'm6.broadcast_policy',
            '{
              "blocked_entitlement_plans": ["trial", "starter"],
              "require_marketing_opt_in": true,
              "template_only": true
            }'::jsonb
          ),
          (
            'alerts.thresholds',
            '{
              "outbox_dead_spike_window_minutes": 15,
              "outbox_dead_spike_min_count": 5,
              "meta_webhook_errors_spike_window_minutes": 60,
              "meta_webhook_errors_spike_min_count": 50
            }'::jsonb
          )
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM ops_runtime_config WHERE key IN ('m6.broadcast_policy', 'alerts.thresholds');")
    op.execute(
        """
        ALTER TABLE metrics_hourly_system
          DROP COLUMN IF EXISTS billing_webhook_process_errors,
          DROP COLUMN IF EXISTS wa_meta_webhook_errors;
        """
    )
    op.execute("DROP TABLE IF EXISTS bill_webhook_processing_errors;")
    op.execute("DROP TABLE IF EXISTS ops_alert_events;")
    op.execute("DROP TABLE IF EXISTS wa_broadcast_targets;")
    op.execute("DROP TABLE IF EXISTS wa_broadcast_campaigns;")
    op.execute("DROP TABLE IF EXISTS customer_marketing_opt_in;")
    op.execute("ALTER TABLE wa_outbox DROP COLUMN IF EXISTS dead_at;")
