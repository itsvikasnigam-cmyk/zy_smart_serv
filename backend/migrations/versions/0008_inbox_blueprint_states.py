"""Blueprint inbox states + audit + in-app notifications

Revision ID: 0008_inbox_blueprint_states
Revises: 0007_wa_meta_webhook_errors
Create Date: 2026-05-14

Migrates legacy ``PENDING_AGENT`` / ``RESOLVED`` chat states to blueprint names,
adds CHECK on ``inbox_chats.state``, and creates ``inbox_assignment_audit`` +
``inbox_notifications`` for reassignment audit + WS ``notification`` fan-out.

"""

from __future__ import annotations

from alembic import op

revision = "0008_inbox_blueprint_states"
down_revision = "0007_wa_meta_webhook_errors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inbox_assignment_audit (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          chat_id UUID NOT NULL REFERENCES inbox_chats(id) ON DELETE CASCADE,
          assignment_id UUID REFERENCES chat_assignments(id) ON DELETE SET NULL,
          event_type TEXT NOT NULL,
          actor_user_id UUID REFERENCES api_users(id),
          from_user_id UUID REFERENCES api_users(id),
          to_user_id UUID REFERENCES api_users(id),
          meta JSONB NOT NULL DEFAULT '{}'::jsonb,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS inbox_assignment_audit_chat_idx
          ON inbox_assignment_audit(chat_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS inbox_assignment_audit_client_idx
          ON inbox_assignment_audit(client_id, created_at DESC);
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS inbox_notifications (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          client_id UUID NOT NULL REFERENCES api_clients(id) ON DELETE CASCADE,
          recipient_user_id UUID NOT NULL REFERENCES api_users(id) ON DELETE CASCADE,
          chat_id UUID REFERENCES inbox_chats(id) ON DELETE CASCADE,
          kind TEXT NOT NULL,
          title TEXT NOT NULL,
          body TEXT,
          payload JSONB NOT NULL DEFAULT '{}'::jsonb,
          read_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS inbox_notifications_recipient_unread_idx
          ON inbox_notifications(recipient_user_id, read_at NULLS FIRST, created_at DESC);
        CREATE INDEX IF NOT EXISTS inbox_notifications_client_idx
          ON inbox_notifications(client_id, created_at DESC);
        """
    )

    # Data migration (legacy → blueprint)
    op.execute("UPDATE inbox_chats SET state = 'HUMAN_REQ' WHERE state = 'PENDING_AGENT';")
    op.execute("UPDATE inbox_chats SET state = 'CLOSED' WHERE state = 'RESOLVED';")

    op.execute(
        """
        ALTER TABLE inbox_chats
        ADD CONSTRAINT inbox_chats_state_blueprint_chk
        CHECK (state IN (
          'AI_ACTIVE',
          'HUMAN_REQ',
          'AGENT_ACTIVE',
          'CLOSED',
          'WAITING_OWNER_DATA'
        ));
        """
    )

    op.execute(
        """
        INSERT INTO ops_runtime_config (key, value_json)
        VALUES
          ('inbox.agent_reply_pause_hours_starter', '24'::jsonb),
          ('inbox.agent_reply_pause_hours_default', '24'::jsonb)
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE inbox_chats DROP CONSTRAINT IF EXISTS inbox_chats_state_blueprint_chk;")
    op.execute("UPDATE inbox_chats SET state = 'PENDING_AGENT' WHERE state = 'HUMAN_REQ';")
    op.execute("UPDATE inbox_chats SET state = 'RESOLVED' WHERE state = 'CLOSED';")
    op.execute("UPDATE inbox_chats SET state = 'PENDING_AGENT' WHERE state = 'WAITING_OWNER_DATA';")
    op.execute("DROP TABLE IF EXISTS inbox_notifications;")
    op.execute("DROP TABLE IF EXISTS inbox_assignment_audit;")
