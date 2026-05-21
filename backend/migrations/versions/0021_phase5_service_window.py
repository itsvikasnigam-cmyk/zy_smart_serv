"""Chat P: customer service window expiry on inbox_chats + ops policy seed.

Revision ID: 0021_phase5_service_window
Revises: 0020_phase5_observability
"""

from __future__ import annotations

from alembic import op

revision = "0021_phase5_service_window"
down_revision = "0020_phase5_observability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE inbox_chats
          ADD COLUMN IF NOT EXISTS customer_service_window_expires_at TIMESTAMPTZ;

        CREATE INDEX IF NOT EXISTS inbox_chats_service_window_idx
          ON inbox_chats(customer_service_window_expires_at)
          WHERE customer_service_window_expires_at IS NOT NULL;

        INSERT INTO ops_runtime_config (key, value_json)
        VALUES (
          'wa.service_window.policy',
          '{
            "window_hours": 24,
            "session_kinds": ["AI_REPLY", "AGENT_REPLY", "PAYWALL", "OWNER_ALERT"],
            "use_last_customer_msg_fallback": true,
            "fallback_templates": {}
          }'::jsonb
        )
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE inbox_chats
          DROP COLUMN IF EXISTS customer_service_window_expires_at;
        DELETE FROM ops_runtime_config WHERE key = 'wa.service_window.policy';
        """
    )
