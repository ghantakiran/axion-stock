"""PRD-166: Signal Feedback.

Revision ID: 166
Revises: 165
Create Date: 2025-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "166"
down_revision = "165"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Signal source performance: rolling accuracy and P&L stats per source
    op.create_table(
        "signal_source_performance",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("record_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("source", sa.String(30), nullable=False, index=True),
        sa.Column("trade_count", sa.Integer),
        sa.Column("win_count", sa.Integer),
        sa.Column("win_rate", sa.Float),
        sa.Column("total_pnl", sa.Float),
        sa.Column("avg_pnl", sa.Float),
        sa.Column("sharpe_ratio", sa.Float),
        sa.Column("profit_factor", sa.Float),
        sa.Column("avg_conviction", sa.Float),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Weight adjustments: log of fusion-weight changes driven by feedback
    op.create_table(
        "weight_adjustments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("adjustment_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("old_weights", sa.Text),
        sa.Column("new_weights", sa.Text),
        sa.Column("adjustments_detail", sa.Text),
        sa.Column("adjusted_at", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("weight_adjustments")
    op.drop_table("signal_source_performance")
