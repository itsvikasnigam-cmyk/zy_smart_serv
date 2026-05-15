"""Day-1 SOP markdown seeds for ops runbook center + alert auto-trigger slugs.

Revision ID: 0012_day1_sop_seed
Revises: 0011_blueprint_remainder
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "0012_day1_sop_seed"
down_revision = "0011_blueprint_remainder"
branch_labels = None
depends_on = None

_SOPS: list[tuple[str, str, str, str]] = [
    (
        "dead-letter-recovery",
        "Dead letter recovery",
        "operations",
        "# Dead letter recovery\n\n1. Check wa_outbox rows with status DEAD.\n2. Inspect dead_at and last error.\n3. Fix root cause.\n4. Re-enqueue or manual follow-up.\n",
    ),
    (
        "webhook-downtime",
        "Meta webhook downtime",
        "operations",
        "# Meta webhook downtime\n\n1. Verify Meta webhook URL and verify token.\n2. Check wa_meta_webhook_errors.\n3. Confirm gateway health.\n",
    ),
    (
        "trial-expiry",
        "Trial expiry handling",
        "billing",
        "# Trial expiry\n\n1. Confirm trial_end and subscription status.\n2. Verify paywall paths.\n",
    ),
    (
        "payment-failure",
        "Payment failure",
        "billing",
        "# Payment failure\n\n1. Review bill_events and bill_invoices.\n2. Check provider webhooks.\n",
    ),
    (
        "india-provisioning",
        "India WhatsApp provisioning",
        "onboarding",
        "# India provisioning\n\n1. WABA and wa_numbers linkage.\n2. Test inbound and outbound.\n",
    ),
    (
        "byon-number",
        "Bring your own number",
        "onboarding",
        "# BYON\n\n1. Map number to wa_numbers.\n2. Smoke routing.\n",
    ),
    (
        "ban-recovery",
        "WhatsApp ban recovery",
        "operations",
        "# Ban recovery\n\n1. Review Meta errors.\n2. Pause campaigns.\n",
    ),
    (
        "backup-drill",
        "Database backup drill",
        "operations",
        "# Backup drill\n\n1. Confirm backup schedule.\n2. Restore to staging.\n",
    ),
    (
        "key-rotation",
        "API key rotation",
        "security",
        "# Key rotation\n\n1. Rotate secrets.\n2. Deploy workers.\n",
    ),
    (
        "release-rollback",
        "Release rollback",
        "releases",
        "# Release rollback\n\n1. Use ops releases API.\n2. Verify smoke.\n",
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    for slug, title, category, body in _SOPS:
        bind.execute(
            text(
                """
                INSERT INTO ops_sops (title, slug, category, status, current_version)
                SELECT :title, :slug, :cat, 'active', 1
                WHERE NOT EXISTS (SELECT 1 FROM ops_sops WHERE slug = :slug)
                """
            ),
            {"title": title, "slug": slug, "cat": category},
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


def downgrade() -> None:
    slugs = [s[0] for s in _SOPS]
    bind = op.get_bind()
    bind.execute(
        text("DELETE FROM ops_sops WHERE slug = ANY(:slugs)"),
        {"slugs": slugs},
    )
