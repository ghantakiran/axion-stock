"""PRD-121: Event-Driven Architecture & Message Bus.

Revision ID: 121
Revises: 120
"""
from alembic import op
import sqlalchemy as sa

revision = "121"
down_revision = "120"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(32), nullable=False, unique=True, index=True),
        sa.Column("event_type", sa.String(128), nullable=False, index=True),
        sa.Column("category", sa.String(32), nullable=False, index=True),
        sa.Column("source", sa.String(128), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("data", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("aggregate_id", sa.String(128), nullable=True, index=True),
        sa.Column("aggregate_type", sa.String(64), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True, index=True),
        sa.Column("sequence_number", sa.BigInteger, nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "subscriber_state",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("subscriber_id", sa.String(32), nullable=False, unique=True, index=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("topic_pattern", sa.String(256), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="active"),
        sa.Column("last_event_id", sa.String(32), nullable=True),
        sa.Column("last_sequence", sa.BigInteger, default=0),
        sa.Column("events_processed", sa.BigInteger, default=0),
        sa.Column("events_failed", sa.BigInteger, default=0),
        sa.Column("last_processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("subscriber_state")
    op.drop_table("event_log")
