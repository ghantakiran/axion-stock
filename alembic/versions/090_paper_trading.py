"""PRD-90: Paper Trading.

Revision ID: 090
Revises: 089
"""

from alembic import op
import sqlalchemy as sa

revision = "090"
down_revision = "089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Paper trading leaderboard
    op.create_table(
        "paper_leaderboard",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("strategy_name", sa.String(100), nullable=True),
        sa.Column("total_return_pct", sa.Float(), nullable=False),
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        sa.Column("max_drawdown_pct", sa.Float(), nullable=True),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("total_trades", sa.Integer(), server_default="0"),
        sa.Column("rank", sa.Integer(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Strategy parameter change tracking
    op.create_table(
        "paper_strategy_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), nullable=False, index=True),
        sa.Column("parameter_name", sa.String(50), nullable=False),
        sa.Column("old_value", sa.String(200), nullable=True),
        sa.Column("new_value", sa.String(200), nullable=True),
        sa.Column("changed_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("paper_strategy_log")
    op.drop_table("paper_leaderboard")
