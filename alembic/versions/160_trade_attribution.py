"""PRD-160: Live Trade Attribution.

Revision ID: 160
Revises: 159
Create Date: 2025-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "160"
down_revision = "159"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Linked trades: maps executed trades to originating signals
    op.create_table(
        "trade_attribution_links",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("link_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("trade_id", sa.String(50), nullable=False, index=True),
        sa.Column("signal_id", sa.String(50), index=True),
        sa.Column("signal_type", sa.String(30), index=True),
        sa.Column("signal_conviction", sa.Integer),
        sa.Column("signal_direction", sa.String(10)),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("entry_price", sa.Float),
        sa.Column("exit_price", sa.Float),
        sa.Column("entry_shares", sa.Float),
        sa.Column("realized_pnl", sa.Float),
        sa.Column("realized_pnl_pct", sa.Float),
        sa.Column("hold_duration_seconds", sa.Integer),
        sa.Column("exit_reason", sa.String(30)),
        sa.Column("regime_at_entry", sa.String(20)),
        sa.Column("regime_at_exit", sa.String(20)),
        sa.Column("broker", sa.String(20)),
        sa.Column("entry_time", sa.DateTime(timezone=True)),
        sa.Column("exit_time", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # P&L decomposition per trade
    op.create_table(
        "trade_pnl_decomposition",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("decomp_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("trade_id", sa.String(50), nullable=False, index=True),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("total_pnl", sa.Float),
        sa.Column("entry_quality", sa.Float),
        sa.Column("market_movement", sa.Float),
        sa.Column("exit_timing", sa.Float),
        sa.Column("transaction_costs", sa.Float),
        sa.Column("residual", sa.Float),
        sa.Column("entry_score", sa.Float),
        sa.Column("exit_score", sa.Float),
        sa.Column("method", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Rolling signal performance snapshots
    op.create_table(
        "signal_performance_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("snapshot_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("signal_type", sa.String(30), nullable=False, index=True),
        sa.Column("window", sa.String(20), nullable=False),
        sa.Column("trade_count", sa.Integer),
        sa.Column("win_rate", sa.Float),
        sa.Column("total_pnl", sa.Float),
        sa.Column("avg_pnl", sa.Float),
        sa.Column("profit_factor", sa.Float),
        sa.Column("sharpe_ratio", sa.Float),
        sa.Column("avg_entry_score", sa.Float),
        sa.Column("avg_exit_score", sa.Float),
        sa.Column("regime", sa.String(20)),
        sa.Column("snapshot_time", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("signal_performance_snapshots")
    op.drop_table("trade_pnl_decomposition")
    op.drop_table("trade_attribution_links")
