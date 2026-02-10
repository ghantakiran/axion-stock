"""Rename notification_preferences to alert_network_preferences.

Fixes duplicate table name conflict: PRD-60 already defined
notification_preferences. The PRD-142 alert network version is
renamed to alert_network_preferences.

Idempotent: skips if the old table doesn't exist (fresh deploys
that ran the corrected migration 142 directly).

Revision ID: 178
Revises: 177
Create Date: 2026-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "178"
down_revision = "177"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # Only rename if old table exists and new one doesn't
    if "notification_preferences" in tables and "alert_network_preferences" not in tables:
        # Check if this is the PRD-142 version (has max_per_day column)
        # vs the PRD-60 version (has category column)
        columns = [c["name"] for c in inspector.get_columns("notification_preferences")]
        if "max_per_day" in columns and "category" not in columns:
            op.rename_table("notification_preferences", "alert_network_preferences")


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "alert_network_preferences" in tables:
        op.rename_table("alert_network_preferences", "notification_preferences")
