"""Alerting & notifications system tables.

Revision ID: 014
Revises: 013
Create Date: 2026-01-30

Adds:
- alerts: Alert definitions with conditions
- alert_history: Triggered alert event records
- notifications: Delivery records per channel
- notification_preferences: Per-user notification settings
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Alerts
    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("alert_id", sa.String(32), unique=True, nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("alert_type", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=True),
        sa.Column("conditions_json", sa.JSON, nullable=False),
        sa.Column("priority", sa.String(16), default="medium"),
        sa.Column("status", sa.String(16), default="active"),
        sa.Column("channels_json", sa.JSON),
        sa.Column("cooldown_seconds", sa.Integer, default=1800),
        sa.Column("message_template", sa.Text, nullable=True),
        sa.Column("last_triggered_at", sa.DateTime, nullable=True),
        sa.Column("snooze_until", sa.DateTime, nullable=True),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("trigger_count", sa.Integer, default=0),
        sa.Column("max_triggers", sa.Integer, default=0),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_alerts_user", "alerts", ["user_id"])
    op.create_index("ix_alerts_status", "alerts", ["status"])
    op.create_index("ix_alerts_type", "alerts", ["alert_type"])
    op.create_index("ix_alerts_symbol", "alerts", ["symbol"])

    # Alert history
    op.create_table(
        "alert_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("event_id", sa.String(32), unique=True, nullable=False),
        sa.Column("alert_id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("triggered_at", sa.DateTime, nullable=False),
        sa.Column("values_json", sa.JSON),
        sa.Column("message", sa.Text),
        sa.Column("priority", sa.String(16)),
    )
    op.create_index("ix_alert_history_alert", "alert_history", ["alert_id"])
    op.create_index("ix_alert_history_user", "alert_history", ["user_id"])
    op.create_index(
        "ix_alert_history_triggered",
        "alert_history", ["triggered_at"],
    )

    # Notifications
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("notification_id", sa.String(32), unique=True, nullable=False),
        sa.Column("event_id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), default="pending"),
        sa.Column("message", sa.Text),
        sa.Column("subject", sa.String(200)),
        sa.Column("recipient", sa.String(256)),
        sa.Column("attempts", sa.Integer, default=0),
        sa.Column("delivered_at", sa.DateTime, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("is_read", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_user", "notifications", ["user_id"])
    op.create_index("ix_notifications_event", "notifications", ["event_id"])
    op.create_index("ix_notifications_status", "notifications", ["status"])
    op.create_index("ix_notifications_channel", "notifications", ["channel"])

    # Notification preferences
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.String(64), unique=True, nullable=False),
        sa.Column("enabled_channels_json", sa.JSON),
        sa.Column("channel_settings_json", sa.JSON),
        sa.Column("quiet_hours_enabled", sa.Boolean, default=False),
        sa.Column("quiet_start_hour", sa.Integer, default=22),
        sa.Column("quiet_end_hour", sa.Integer, default=7),
        sa.Column("digest_frequency", sa.String(16), default="immediate"),
        sa.Column("priority_overrides_json", sa.JSON, nullable=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_table("notifications")
    op.drop_table("alert_history")
    op.drop_table("alerts")
