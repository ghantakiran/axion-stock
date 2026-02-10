"""Alert & notification network integration.

Revision ID: 142
Revises: 141
Create Date: 2025-02-02
"""

from alembic import op
import sqlalchemy as sa

revision = "142"
down_revision = "141"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alert rules
    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("rule_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("trigger_type", sa.String(30), nullable=False),
        sa.Column("symbol", sa.String(20), index=True),
        sa.Column("threshold", sa.Float),
        sa.Column("channels_json", sa.Text),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("cooldown_minutes", sa.Integer, server_default="30"),
        sa.Column("max_daily_alerts", sa.Integer, server_default="10"),
        sa.Column("user_id", sa.String(50), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Notification delivery log
    op.create_table(
        "notification_delivery_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("delivery_id", sa.String(50), index=True),
        sa.Column("rule_id", sa.String(50), index=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("symbol", sa.String(20), index=True),
        sa.Column("message", sa.Text),
        sa.Column("error", sa.Text),
        sa.Column("attempts", sa.Integer, server_default="1"),
        sa.Column("user_id", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Alert network notification preferences
    op.create_table(
        "alert_network_preferences",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(50), unique=True, nullable=False),
        sa.Column("quiet_hours_enabled", sa.Boolean, server_default="false"),
        sa.Column("quiet_hours_start", sa.Integer, server_default="22"),
        sa.Column("quiet_hours_end", sa.Integer, server_default="7"),
        sa.Column("max_per_hour", sa.Integer, server_default="20"),
        sa.Column("max_per_day", sa.Integer, server_default="100"),
        sa.Column("batch_enabled", sa.Boolean, server_default="false"),
        sa.Column("enabled_channels_json", sa.Text),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("alert_network_preferences")
    op.drop_table("notification_delivery_log")
    op.drop_table("alert_rules")
