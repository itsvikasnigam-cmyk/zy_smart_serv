"""M5 billing: plans, subscriptions, idempotent webhook events

Revision ID: 0004_billing
Revises: 0003_wa_trial_map
Create Date: 2026-05-13

"""

from __future__ import annotations

from alembic import op

revision = "0004_billing"
down_revision = "0003_wa_trial_map"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bill_plans (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          provider TEXT NOT NULL CHECK (provider IN ('razorpay','paddle')),
          external_plan_id TEXT NOT NULL,
          plan_code TEXT NOT NULL CHECK (plan_code IN ('starter','growth','pro')),
          display_name TEXT,
          active BOOLEAN NOT NULL DEFAULT TRUE,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE(provider, external_plan_id)
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bill_subscriptions (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          provider TEXT NOT NULL CHECK (provider IN ('razorpay','paddle')),
          external_subscription_id TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'unknown',
          plan_code TEXT CHECK (plan_code IS NULL OR plan_code IN ('starter','growth','pro')),
          current_period_end TIMESTAMPTZ,
          raw_last_payload JSONB,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE(provider, external_subscription_id)
        );
        CREATE INDEX IF NOT EXISTS bill_subscriptions_client_idx ON bill_subscriptions(client_id);
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bill_events (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          provider TEXT NOT NULL CHECK (provider IN ('razorpay','paddle')),
          provider_event_id TEXT NOT NULL,
          event_type TEXT NOT NULL,
          payload JSONB NOT NULL DEFAULT '{}'::jsonb,
          received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          applied BOOLEAN NOT NULL DEFAULT FALSE,
          error_message TEXT,
          UNIQUE(provider, provider_event_id)
        );
        CREATE INDEX IF NOT EXISTS bill_events_received_idx ON bill_events(received_at);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS bill_events;")
    op.execute("DROP TABLE IF EXISTS bill_subscriptions;")
    op.execute("DROP TABLE IF EXISTS bill_plans;")
