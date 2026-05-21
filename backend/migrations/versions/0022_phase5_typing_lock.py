"""Chat Q: seed typing lock ops_runtime_config keys.

Revision ID: 0022_phase5_typing_lock
Revises: 0021_phase5_service_window
"""

from __future__ import annotations

from alembic import op

revision = "0022_phase5_typing_lock"
down_revision = "0021_phase5_service_window"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO ops_runtime_config (key, value_json)
        VALUES
          ('inbox.typing_lock.policy', '{"enabled": true}'::jsonb),
          ('inbox.typing_hard_lock_enabled', 'true'::jsonb)
        ON CONFLICT (key) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM ops_runtime_config
        WHERE key IN ('inbox.typing_lock.policy', 'inbox.typing_hard_lock_enabled');
        """
    )
