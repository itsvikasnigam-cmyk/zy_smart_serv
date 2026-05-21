"""Option C phase 4: owner-wait watchdog columns + SLA config seeds.

Revision ID: 0019_option_c_phase4_owner_sla
Revises: 0018_gate2_ai_fallback_seeds
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0019_option_c_phase4_owner_sla"
down_revision = "0018_gate2_ai_fallback_seeds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE inbox_chats
          ADD COLUMN IF NOT EXISTS owner_wait_4h_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS owner_wait_8h_at TIMESTAMPTZ,
          ADD COLUMN IF NOT EXISTS sla_breach_at TIMESTAMPTZ;

        CREATE INDEX IF NOT EXISTS inbox_chats_waiting_owner_due_idx
          ON inbox_chats(state, pending_since)
          WHERE state = 'WAITING_OWNER_DATA';

        CREATE INDEX IF NOT EXISTS inbox_chats_sla_breach_idx
          ON inbox_chats(state, sla_breach_at)
          WHERE state IN ('HUMAN_REQ', 'AGENT_ACTIVE');
        """
    )

    op.execute(
        """
        INSERT INTO ops_runtime_config (key, value_json) VALUES
          ('inbox.owner_wait', '{
            "realert_hours": 4,
            "apology_hours": 8,
            "apology_customer_reply": "We are sorry for the delay. Our team is still working on your request and will get back to you as soon as possible. Thank you for your patience."
          }'::jsonb),
          ('inbox.sla.agent_response_minutes', '30'::jsonb)
        ON CONFLICT (key) DO NOTHING;
        """
    )

    bind = op.get_bind()
    slug = "forward-owner-watchdog"
    body = (
        "# Forward owner (8h)\n\n"
        "1. Review chat in WAITING_OWNER_DATA.\n"
        "2. Supply missing data in owner panel.\n"
        "3. Re-open AI path or assign agent.\n"
    )
    bind.execute(
        text(
            """
            INSERT INTO ops_sops (title, slug, category, status, current_version)
            SELECT :title, :slug, 'operations', 'active', 1
            WHERE NOT EXISTS (SELECT 1 FROM ops_sops WHERE slug = :slug)
            """
        ),
        {"title": "Forward owner — 8h owner-data wait", "slug": slug},
    )
    bind.execute(
        text(
            """
            INSERT INTO ops_sop_versions (sop_id, version_num, body_markdown)
            SELECT s.id, 1, :body
            FROM ops_sops s
            WHERE s.slug = :slug
              AND NOT EXISTS (
                SELECT 1 FROM ops_sop_versions v
                WHERE v.sop_id = s.id AND v.version_num = 1
              )
            """
        ),
        {"slug": slug, "body": body},
    )

    op.execute(
        """
        UPDATE ops_runtime_config
        SET value_json = value_json || '{"OWNER_WAIT_8H": "forward-owner-watchdog"}'::jsonb
        WHERE key = 'alerts.sop_trigger_map'
          AND NOT (value_json ? 'OWNER_WAIT_8H');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE inbox_chats
          DROP COLUMN IF EXISTS owner_wait_4h_at,
          DROP COLUMN IF EXISTS owner_wait_8h_at,
          DROP COLUMN IF EXISTS sla_breach_at;
        """
    )
    op.execute(
        """
        DELETE FROM ops_runtime_config
        WHERE key IN ('inbox.owner_wait', 'inbox.sla.agent_response_minutes');
        """
    )
