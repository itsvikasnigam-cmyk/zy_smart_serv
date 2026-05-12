"""init core tables

Revision ID: 0001_init_core
Revises: None
Create Date: 2026-05-12

"""

from __future__ import annotations

from alembic import op

revision = "0001_init_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # --- Core minimal tables (enough to start M2/M4 pipeline) ---
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS api_clients (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          business_name TEXT,
          category TEXT,
          owner_phone_e164 TEXT,
          entitlement_plan TEXT CHECK (entitlement_plan IN ('trial','starter','growth','pro','churned')) DEFAULT 'trial',
          billing_plan_code TEXT,
          billing_provider TEXT CHECK (billing_provider IN ('razorpay','paddle')),
          trial_end TIMESTAMPTZ,
          kyc_status TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS api_users (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          client_id UUID REFERENCES api_clients(id) ON DELETE CASCADE,
          name TEXT,
          email TEXT,
          role TEXT NOT NULL CHECK (role IN ('owner','agent','super_admin')),
          password_hash TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS api_users_client_idx ON api_users(client_id);
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS wa_numbers (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          phone_e164 TEXT NOT NULL UNIQUE,
          type TEXT NOT NULL CHECK (type IN ('TRIAL','PROD','INTERNAL')),
          ownership TEXT CHECK (ownership IN ('ZY_OWNED','CLIENT_BYON')) DEFAULT 'ZY_OWNED',
          client_id UUID REFERENCES api_clients(id) ON DELETE SET NULL,
          meta_waba_id TEXT,
          meta_phone_number_id TEXT,
          country_code TEXT,
          status TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS wa_numbers_meta_phone_number_id_uniq
          ON wa_numbers(meta_phone_number_id) WHERE meta_phone_number_id IS NOT NULL;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inbox_chats (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          customer_phone TEXT NOT NULL,
          waba_number UUID REFERENCES wa_numbers(id),
          state TEXT NOT NULL DEFAULT 'AI_ACTIVE',
          assigned_agent_id UUID REFERENCES api_users(id),
          ai_paused_until TIMESTAMPTZ,
          handoff_reason TEXT,
          pending_since TIMESTAMPTZ,
          priority INT NOT NULL DEFAULT 0,
          last_customer_msg_at TIMESTAMPTZ,
          last_outbound_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE UNIQUE INDEX IF NOT EXISTS inbox_chats_client_customer_uniq ON inbox_chats(client_id, customer_phone);
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inbox_messages (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          chat_id UUID NOT NULL REFERENCES inbox_chats(id) ON DELETE CASCADE,
          direction TEXT NOT NULL CHECK (direction IN ('in','out')),
          sender TEXT NOT NULL CHECK (sender IN ('ai','agent','customer','system')),
          text TEXT NOT NULL,
          timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
          meta_msg_id TEXT,
          meta_payload JSONB
        );
        CREATE UNIQUE INDEX IF NOT EXISTS inbox_messages_meta_msg_id_uniq
          ON inbox_messages(meta_msg_id) WHERE meta_msg_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS inbox_messages_chat_ts_idx ON inbox_messages(chat_id, timestamp);
        """
    )

    # --- Runtime config (pricing, debounce, AI gates) ---
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS ops_runtime_config (
          key TEXT PRIMARY KEY,
          value_json JSONB NOT NULL,
          updated_by_user_id UUID REFERENCES api_users(id),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS ops_runtime_config_audit (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          key TEXT NOT NULL,
          old_value_json JSONB,
          new_value_json JSONB,
          changed_by_user_id UUID REFERENCES api_users(id),
          changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          reason TEXT
        );
        CREATE INDEX IF NOT EXISTS ops_runtime_config_audit_key_idx ON ops_runtime_config_audit(key, changed_at);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS ops_runtime_config_audit;")
    op.execute("DROP TABLE IF EXISTS ops_runtime_config;")
    op.execute("DROP TABLE IF EXISTS inbox_messages;")
    op.execute("DROP TABLE IF EXISTS inbox_chats;")
    op.execute("DROP TABLE IF EXISTS wa_numbers;")
    op.execute("DROP TABLE IF EXISTS api_users;")
    op.execute("DROP TABLE IF EXISTS api_clients;")

