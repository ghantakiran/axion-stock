"""PRD-171: Bot Lifecycle Hardening.

Revision ID: 171
Revises: 170
Create Date: 2025-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "171"
down_revision = "170"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bot lifecycle events: signal guard rejections, exits, emergency close
    op.create_table(
        "bot_lifecycle_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False, index=True),
        sa.Column("ticker", sa.String(20), index=True),
        sa.Column("direction", sa.String(10)),
        sa.Column("details_json", sa.Text),
        sa.Column("pipeline_run_id", sa.String(50)),
        sa.Column("event_time", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("bot_lifecycle_events")
