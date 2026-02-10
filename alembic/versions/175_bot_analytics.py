"""PRD-175: Live Bot Analytics.

Revision ID: 175
Revises: 174
Create Date: 2025-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "175"
down_revision = "174"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bot_performance_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("snapshot_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("total_trades", sa.Integer),
        sa.Column("winning_trades", sa.Integer),
        sa.Column("losing_trades", sa.Integer),
        sa.Column("win_rate", sa.Float),
        sa.Column("total_pnl", sa.Float),
        sa.Column("sharpe", sa.Float),
        sa.Column("sortino", sa.Float),
        sa.Column("calmar", sa.Float),
        sa.Column("max_drawdown", sa.Float),
        sa.Column("by_signal_json", sa.Text),
        sa.Column("by_strategy_json", sa.Text),
        sa.Column("snapshot_time", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "bot_trade_metrics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("trade_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("ticker", sa.String(20), index=True, nullable=False),
        sa.Column("direction", sa.String(10)),
        sa.Column("pnl", sa.Float),
        sa.Column("signal_type", sa.String(30), index=True),
        sa.Column("strategy", sa.String(30), index=True),
        sa.Column("entry_price", sa.Float),
        sa.Column("exit_price", sa.Float),
        sa.Column("shares", sa.Float),
        sa.Column("exit_reason", sa.String(50)),
        sa.Column("closed_at", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("bot_trade_metrics")
    op.drop_table("bot_performance_snapshots")
