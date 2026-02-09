"""PRD-153: Real-Time Signal Streaming tables.

Revision ID: 153
Revises: 152
"""

from alembic import op
import sqlalchemy as sa

revision = "153"
down_revision = "152"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Streaming event log (for debugging / replay)
    op.create_table(
        "stream_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("channel", sa.String(30), nullable=False, index=True),
        sa.Column("ticker", sa.String(20), index=True),
        sa.Column("message_type", sa.String(30), nullable=False),
        sa.Column("data_json", sa.Text),
        sa.Column("sequence", sa.Integer),
        sa.Column("latency_ms", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Stream health snapshots
    op.create_table(
        "stream_health_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("snapshot_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("messages_in", sa.Integer),
        sa.Column("messages_out", sa.Integer),
        sa.Column("messages_filtered", sa.Integer),
        sa.Column("messages_errored", sa.Integer),
        sa.Column("avg_latency_ms", sa.Float),
        sa.Column("max_latency_ms", sa.Float),
        sa.Column("throughput_per_min", sa.Float),
        sa.Column("error_rate", sa.Float),
        sa.Column("active_tickers", sa.Integer),
        sa.Column("queue_depth", sa.Integer),
        sa.Column("issues_json", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("stream_health_snapshots")
    op.drop_table("stream_events")
