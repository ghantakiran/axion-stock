"""PRD-137: Trading Bot Dashboard & Control Center.

Revision ID: 137
Revises: 136
"""

from alembic import op
import sqlalchemy as sa

revision = "137"
down_revision = "136"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bot sessions table
    op.create_table(
        "bot_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(50), unique=True, index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("starting_equity", sa.Float(), nullable=False),
        sa.Column("ending_equity", sa.Float(), nullable=True),
        sa.Column("total_signals", sa.Integer(), server_default="0"),
        sa.Column("total_trades", sa.Integer(), server_default="0"),
        sa.Column("config_json", sa.Text(), nullable=True),
        sa.Column("errors_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Bot events table
    op.create_table(
        "bot_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(50), index=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    op.create_index("ix_bot_events_type", "bot_events", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_bot_events_type", table_name="bot_events")
    op.drop_table("bot_events")
    op.drop_table("bot_sessions")
