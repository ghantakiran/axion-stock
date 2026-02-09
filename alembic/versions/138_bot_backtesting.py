"""Bot strategy backtesting integration.

Revision ID: 138
Revises: 137
Create Date: 2025-01-30
"""

from alembic import op
import sqlalchemy as sa

revision = "138"
down_revision = "137"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bot backtest run records
    op.create_table(
        "bot_backtest_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("initial_capital", sa.Float, nullable=False),
        sa.Column("tickers_json", sa.Text),
        sa.Column("config_json", sa.Text),
        sa.Column("total_return", sa.Float),
        sa.Column("cagr", sa.Float),
        sa.Column("sharpe_ratio", sa.Float),
        sa.Column("max_drawdown", sa.Float),
        sa.Column("total_trades", sa.Integer),
        sa.Column("win_rate", sa.Float),
        sa.Column("profit_factor", sa.Float),
        sa.Column("total_signals", sa.Integer),
        sa.Column("attribution_json", sa.Text),
        sa.Column("equity_curve_json", sa.Text),
        sa.Column("metadata_json", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Signal attribution per signal type per run
    op.create_table(
        "bot_signal_attribution",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(50), index=True, nullable=False),
        sa.Column("signal_type", sa.String(50), nullable=False),
        sa.Column("total_trades", sa.Integer, nullable=False),
        sa.Column("winning_trades", sa.Integer),
        sa.Column("losing_trades", sa.Integer),
        sa.Column("win_rate", sa.Float),
        sa.Column("total_pnl", sa.Float),
        sa.Column("avg_pnl", sa.Float),
        sa.Column("profit_factor", sa.Float),
        sa.Column("avg_conviction", sa.Float),
        sa.Column("avg_hold_bars", sa.Float),
        sa.Column("metadata_json", sa.Text),
    )

    op.create_index(
        "ix_bot_signal_attribution_signal_type",
        "bot_signal_attribution",
        ["signal_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_bot_signal_attribution_signal_type", "bot_signal_attribution")
    op.drop_table("bot_signal_attribution")
    op.drop_table("bot_backtest_runs")
