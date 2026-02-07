"""PRD-59: Real-time WebSocket API.

Revision ID: 059
Revises: 058
"""

from alembic import op
import sqlalchemy as sa

revision = "059"
down_revision = "058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # WebSocket connections
    op.create_table(
        "websocket_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_token", sa.String(64), nullable=False, unique=True),
        # Connection info
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("client_version", sa.String(50), nullable=True),
        # Status
        sa.Column("status", sa.String(20), nullable=False),  # connected, disconnected, error
        sa.Column("disconnect_reason", sa.String(100), nullable=True),
        # Metrics
        sa.Column("messages_sent", sa.BigInteger(), server_default="0"),
        sa.Column("messages_received", sa.BigInteger(), server_default="0"),
        sa.Column("bytes_sent", sa.BigInteger(), server_default="0"),
        sa.Column("bytes_received", sa.BigInteger(), server_default="0"),
        # Timestamps
        sa.Column("connected_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_heartbeat", sa.DateTime(), nullable=True),
        sa.Column("disconnected_at", sa.DateTime(), nullable=True),
    )

    # WebSocket subscriptions
    op.create_table(
        "websocket_subscriptions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("connection_id", sa.String(36), sa.ForeignKey("websocket_connections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", sa.String(36), nullable=False),
        # Subscription details
        sa.Column("channel", sa.String(30), nullable=False),  # quotes, trades, orders, portfolio, alerts, news
        sa.Column("symbols", sa.JSON(), nullable=True),  # Array of symbols
        sa.Column("throttle_ms", sa.Integer(), server_default="100"),
        # Filters
        sa.Column("filters", sa.JSON(), nullable=True),  # Additional filter criteria
        # Status
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        # Timestamps
        sa.Column("subscribed_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("unsubscribed_at", sa.DateTime(), nullable=True),
    )

    # WebSocket metrics (time-series)
    op.create_table(
        "websocket_metrics",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False, index=True),
        # Aggregate metrics
        sa.Column("active_connections", sa.Integer(), nullable=False),
        sa.Column("total_subscriptions", sa.Integer(), nullable=False),
        sa.Column("messages_per_second", sa.Float(), nullable=True),
        sa.Column("bytes_per_second", sa.Float(), nullable=True),
        # Latency
        sa.Column("avg_latency_ms", sa.Float(), nullable=True),
        sa.Column("p95_latency_ms", sa.Float(), nullable=True),
        sa.Column("p99_latency_ms", sa.Float(), nullable=True),
        # Errors
        sa.Column("error_count", sa.Integer(), server_default="0"),
        sa.Column("disconnect_count", sa.Integer(), server_default="0"),
        # Channel breakdown
        sa.Column("channel_stats", sa.JSON(), nullable=True),
    )

    # Rate limit tracking
    op.create_table(
        "websocket_rate_limits",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), nullable=False),
        sa.Column("request_count", sa.Integer(), server_default="0"),
        sa.Column("message_count", sa.Integer(), server_default="0"),
        sa.Column("is_limited", sa.Boolean(), server_default="false"),
    )

    # Indexes
    op.create_index("ix_ws_connections_user_id", "websocket_connections", ["user_id"])
    op.create_index("ix_ws_connections_status", "websocket_connections", ["status"])
    op.create_index("ix_ws_connections_connected_at", "websocket_connections", ["connected_at"])
    op.create_index("ix_ws_subscriptions_connection", "websocket_subscriptions", ["connection_id"])
    op.create_index("ix_ws_subscriptions_channel", "websocket_subscriptions", ["channel"])
    op.create_index("ix_ws_metrics_timestamp", "websocket_metrics", ["timestamp"])
    op.create_index("ix_ws_rate_limits_user_window", "websocket_rate_limits", ["user_id", "window_start"])


def downgrade() -> None:
    op.drop_index("ix_ws_rate_limits_user_window")
    op.drop_index("ix_ws_metrics_timestamp")
    op.drop_index("ix_ws_subscriptions_channel")
    op.drop_index("ix_ws_subscriptions_connection")
    op.drop_index("ix_ws_connections_connected_at")
    op.drop_index("ix_ws_connections_status")
    op.drop_index("ix_ws_connections_user_id")
    op.drop_table("websocket_rate_limits")
    op.drop_table("websocket_metrics")
    op.drop_table("websocket_subscriptions")
    op.drop_table("websocket_connections")
