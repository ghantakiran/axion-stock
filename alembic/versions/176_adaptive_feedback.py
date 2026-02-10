"""PRD-176: Adaptive Feedback Loop.

Revision ID: 176
Revises: 175
Create Date: 2025-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "176"
down_revision = "175"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal_weight_history",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("snapshot_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("weights_json", sa.Text, nullable=False),
        sa.Column("trigger", sa.String(20)),
        sa.Column("trade_count", sa.Integer),
        sa.Column("recorded_at", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("signal_weight_history")
