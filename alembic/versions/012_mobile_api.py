"""Mobile app & public API tables.

Revision ID: 012
Revises: 011
Create Date: 2026-01-30

Adds:
- api_keys: API key storage
- webhooks: Webhook registrations
- webhook_deliveries: Delivery history
- rate_limit_log: Rate limit tracking
- api_usage: Usage analytics
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # API keys
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key_id", sa.String(32), unique=True, nullable=False),
        sa.Column("key_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("scopes", sa.JSON, default=[]),
        sa.Column("tier", sa.String(16), default="free"),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("last_used", sa.DateTime, nullable=True),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])

    # Webhooks
    op.create_table(
        "webhooks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("webhook_id", sa.String(32), unique=True, nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("events", sa.JSON, nullable=False),
        sa.Column("secret_hash", sa.String(64)),
        sa.Column("description", sa.Text, default=""),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_delivery", sa.DateTime, nullable=True),
        sa.Column("total_deliveries", sa.Integer, default=0),
        sa.Column("successful_deliveries", sa.Integer, default=0),
    )
    op.create_index("ix_webhooks_user_id", "webhooks", ["user_id"])

    # Webhook deliveries
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("delivery_id", sa.String(32), unique=True, nullable=False),
        sa.Column(
            "webhook_id",
            sa.String(32),
            sa.ForeignKey("webhooks.webhook_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("response_time_ms", sa.Float, nullable=True),
        sa.Column("success", sa.Boolean, default=False),
        sa.Column("attempts", sa.Integer, default=1),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_webhook_deliveries_webhook_id", "webhook_deliveries", ["webhook_id"])

    # Rate limit log
    op.create_table(
        "rate_limit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("key_id", sa.String(32), nullable=True),
        sa.Column("endpoint", sa.String(256)),
        sa.Column("method", sa.String(8)),
        sa.Column("status_code", sa.Integer),
        sa.Column("was_limited", sa.Boolean, default=False),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_rate_limit_log_user_id", "rate_limit_log", ["user_id"])
    op.create_index("ix_rate_limit_log_timestamp", "rate_limit_log", ["timestamp"])

    # API usage analytics
    op.create_table(
        "api_usage",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("endpoint", sa.String(256)),
        sa.Column("method", sa.String(8)),
        sa.Column("request_count", sa.Integer, default=0),
        sa.Column("avg_response_ms", sa.Float, default=0),
        sa.Column("error_count", sa.Integer, default=0),
    )
    op.create_index("ix_api_usage_user_date", "api_usage", ["user_id", "date"])


def downgrade() -> None:
    op.drop_table("api_usage")
    op.drop_table("rate_limit_log")
    op.drop_table("webhook_deliveries")
    op.drop_table("webhooks")
    op.drop_table("api_keys")
