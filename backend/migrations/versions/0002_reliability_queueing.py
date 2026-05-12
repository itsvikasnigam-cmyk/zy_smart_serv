"""reliability queueing: batches, outbox, statuses, assignments

Revision ID: 0002_reliability_queueing
Revises: 0001_init_core
Create Date: 2026-05-12

"""

from __future__ import annotations

from alembic import op

revision = "0002_reliability_queueing"
down_revision = "0001_init_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Debounce batching
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inbox_inbound_batches (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          chat_id UUID NOT NULL REFERENCES inbox_chats(id) ON DELETE CASCADE,
          status TEXT NOT NULL CHECK (status IN ('OPEN','SEALED','PROCESSED','CANCELLED')),
          opened_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          sealed_at TIMESTAMPTZ,
          process_after TIMESTAMPTZ NOT NULL,
          max_process_after TIMESTAMPTZ NOT NULL,
          last_inbound_msg_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          inbound_msg_count INT NOT NULL DEFAULT 0,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS inbox_inbound_batches_due_idx ON inbox_inbound_batches(status, process_after);
        CREATE INDEX IF NOT EXISTS inbox_inbound_batches_chat_idx ON inbox_inbound_batches(chat_id, status, process_after);
        """
    )

    # TTL locks to prevent double processing
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS processing_locks (
          lock_key TEXT PRIMARY KEY,
          owner_id TEXT NOT NULL,
          acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          expires_at TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS processing_locks_expires_idx ON processing_locks(expires_at);
        """
    )

    # Durable outbox for outbound retries + idempotency
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS wa_outbox (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          chat_id UUID NOT NULL REFERENCES inbox_chats(id) ON DELETE CASCADE,
          to_phone_e164 TEXT NOT NULL,
          from_wa_number_id UUID NOT NULL REFERENCES wa_numbers(id),
          kind TEXT NOT NULL CHECK (kind IN ('AI_REPLY','OWNER_ALERT','PAYWALL','TEMPLATE','AGENT_REPLY','SYSTEM')),
          body_text TEXT NOT NULL,
          reply_to_batch_id UUID REFERENCES inbox_inbound_batches(id),
          idempotency_key TEXT NOT NULL UNIQUE,
          status TEXT NOT NULL CHECK (status IN ('PENDING','SENDING','SENT','DELIVERED','READ','FAILED','DEAD')),
          attempt_count INT NOT NULL DEFAULT 0,
          next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          last_error_code TEXT,
          last_error_detail TEXT,
          meta_message_id TEXT,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          sent_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS wa_outbox_due_idx ON wa_outbox(status, next_attempt_at);
        CREATE INDEX IF NOT EXISTS wa_outbox_chat_idx ON wa_outbox(chat_id, created_at);
        CREATE INDEX IF NOT EXISTS wa_outbox_meta_message_idx ON wa_outbox(meta_message_id);
        """
    )

    # Status events (delivery closure)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS wa_status_events (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          meta_message_id TEXT NOT NULL,
          event_type TEXT NOT NULL CHECK (event_type IN ('SENT','DELIVERED','READ','FAILED')),
          event_at TIMESTAMPTZ NOT NULL,
          raw_json JSONB NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS wa_status_events_msg_idx ON wa_status_events(meta_message_id, event_at);
        """
    )

    # Responsibilities + assignment log + presence/typing
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_profiles (
          user_id UUID PRIMARY KEY REFERENCES api_users(id) ON DELETE CASCADE,
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          responsibilities JSONB NOT NULL DEFAULT '[]'::jsonb,
          languages JSONB NOT NULL DEFAULT '[]'::jsonb,
          working_hours JSONB,
          max_active_chats INT,
          active BOOLEAN NOT NULL DEFAULT true,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS agent_profiles_client_idx ON agent_profiles(client_id);

        CREATE TABLE IF NOT EXISTS chat_assignments (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          chat_id UUID NOT NULL REFERENCES inbox_chats(id) ON DELETE CASCADE,
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          assigned_to_user_id UUID NOT NULL REFERENCES api_users(id),
          assigned_by_user_id UUID REFERENCES api_users(id),
          reason TEXT,
          note TEXT,
          status TEXT NOT NULL CHECK (status IN ('ACTIVE','REASSIGNED','RESOLVED')),
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          ended_at TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS chat_assignments_chat_idx ON chat_assignments(chat_id, status, created_at);
        CREATE UNIQUE INDEX IF NOT EXISTS chat_assignments_one_active_per_chat
          ON chat_assignments(chat_id) WHERE status = 'ACTIVE';

        CREATE TABLE IF NOT EXISTS chat_presence (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          chat_id UUID NOT NULL REFERENCES inbox_chats(id) ON DELETE CASCADE,
          user_id UUID NOT NULL REFERENCES api_users(id) ON DELETE CASCADE,
          state TEXT NOT NULL CHECK (state IN ('typing','viewing')),
          expires_at TIMESTAMPTZ NOT NULL,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS chat_presence_expires_idx ON chat_presence(expires_at);
        CREATE UNIQUE INDEX IF NOT EXISTS chat_presence_unique_state ON chat_presence(chat_id, user_id, state);
        """
    )

    # Seed default runtime config (debounce defaults)
    op.execute(
        """
        INSERT INTO ops_runtime_config (key, value_json)
        VALUES
          ('debounce.seconds', '3'::jsonb),
          ('debounce.max_seconds', '10'::jsonb),
          ('debounce.adaptive.enabled', 'true'::jsonb),
          ('debounce.adaptive.two_msgs_within_sec', '2'::jsonb)
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chat_presence;")
    op.execute("DROP TABLE IF EXISTS chat_assignments;")
    op.execute("DROP TABLE IF EXISTS agent_profiles;")
    op.execute("DROP TABLE IF EXISTS wa_status_events;")
    op.execute("DROP TABLE IF EXISTS wa_outbox;")
    op.execute("DROP TABLE IF EXISTS processing_locks;")
    op.execute("DROP TABLE IF EXISTS inbox_inbound_batches;")

