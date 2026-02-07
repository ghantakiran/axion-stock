"""PRD-60: Mobile Push Notifications.

Revision ID: 060
Revises: 059
Create Date: 2025-01-15

"""
from alembic import op
import sqlalchemy as sa


revision = "060"
down_revision = "059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # notification_devices - Device registration for push notifications
    op.create_table(
        "notification_devices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("device_token", sa.String(500), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),  # ios, android, web
        sa.Column("device_name", sa.String(100), nullable=True),
        sa.Column("device_model", sa.String(100), nullable=True),
        sa.Column("app_version", sa.String(20), nullable=True),
        sa.Column("os_version", sa.String(20), nullable=True),
        sa.Column("push_token_type", sa.String(20), nullable=False),  # fcm, apns, web_push
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("token_refreshed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_notification_devices_token", "notification_devices", ["device_token"])

    # notification_preferences - User notification preferences
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("category", sa.String(30), nullable=False),  # price_alerts, trades, portfolio, news, system
        sa.Column("enabled", sa.Boolean(), default=True),
        sa.Column("priority", sa.String(20), default="normal"),  # urgent, normal, low
        sa.Column("channels", sa.Text(), nullable=True),  # JSON: ["push", "email", "sms"]
        sa.Column("quiet_hours_enabled", sa.Boolean(), default=False),
        sa.Column("quiet_hours_start", sa.String(10), nullable=True),  # HH:MM format
        sa.Column("quiet_hours_end", sa.String(10), nullable=True),
        sa.Column("timezone", sa.String(50), default="UTC"),
        sa.Column("max_per_hour", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now()),
        sa.UniqueConstraint("user_id", "category", name="uq_notification_prefs_user_category"),
    )

    # notification_queue - Queued notifications for delivery
    op.create_table(
        "notification_queue",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("device_id", sa.String(36), nullable=True),  # null = all devices
        sa.Column("category", sa.String(30), nullable=False, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("data", sa.Text(), nullable=True),  # JSON payload
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("action_url", sa.String(500), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, default="normal"),
        sa.Column("status", sa.String(20), nullable=False, default="pending", index=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("retry_count", sa.Integer(), default=0),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_notification_queue_scheduled", "notification_queue", ["status", "scheduled_at"])

    # notification_history - Delivery history and analytics
    op.create_table(
        "notification_history",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("notification_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("device_id", sa.String(36), nullable=True),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("platform", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),  # sent, delivered, opened, failed
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=True),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("notification_history")
    op.drop_table("notification_queue")
    op.drop_table("notification_preferences")
    op.drop_table("notification_devices")
