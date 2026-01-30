"""Backtesting engine tables.

Revision ID: 011
Revises: 010
Create Date: 2026-01-30

Adds:
- backtest_runs: Backtest execution history
- backtest_trades: Completed trades from backtests
- backtest_snapshots: Periodic portfolio snapshots
- walk_forward_results: Walk-forward optimization results
- strategy_comparisons: Strategy comparison records
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Backtest runs
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.String(64), unique=True, nullable=False),
        sa.Column("strategy_name", sa.String(128), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("initial_capital", sa.Float, nullable=False),
        sa.Column("bar_type", sa.String(16), default="1d"),
        sa.Column("rebalance_frequency", sa.String(32), default="monthly"),
        sa.Column("config_json", sa.JSON),
        # Performance metrics
        sa.Column("total_return", sa.Float),
        sa.Column("cagr", sa.Float),
        sa.Column("volatility", sa.Float),
        sa.Column("sharpe_ratio", sa.Float),
        sa.Column("sortino_ratio", sa.Float),
        sa.Column("calmar_ratio", sa.Float),
        sa.Column("max_drawdown", sa.Float),
        sa.Column("total_trades", sa.Integer),
        sa.Column("win_rate", sa.Float),
        sa.Column("profit_factor", sa.Float),
        sa.Column("total_costs", sa.Float),
        sa.Column("turnover", sa.Float),
        sa.Column("metrics_json", sa.JSON),
        # Timestamps
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("duration_seconds", sa.Float),
    )

    # Backtest trades
    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "run_id",
            sa.String(64),
            sa.ForeignKey("backtest_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("entry_date", sa.DateTime, nullable=False),
        sa.Column("exit_date", sa.DateTime, nullable=False),
        sa.Column("entry_price", sa.Float, nullable=False),
        sa.Column("exit_price", sa.Float, nullable=False),
        sa.Column("qty", sa.Integer, nullable=False),
        sa.Column("pnl", sa.Float),
        sa.Column("pnl_pct", sa.Float),
        sa.Column("hold_days", sa.Integer),
        sa.Column("sector", sa.String(64)),
    )
    op.create_index("ix_backtest_trades_run_id", "backtest_trades", ["run_id"])
    op.create_index("ix_backtest_trades_symbol", "backtest_trades", ["symbol"])

    # Backtest snapshots
    op.create_table(
        "backtest_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "run_id",
            sa.String(64),
            sa.ForeignKey("backtest_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("equity", sa.Float, nullable=False),
        sa.Column("cash", sa.Float),
        sa.Column("positions_value", sa.Float),
        sa.Column("n_positions", sa.Integer),
        sa.Column("drawdown", sa.Float),
        sa.Column("peak_equity", sa.Float),
    )
    op.create_index("ix_backtest_snapshots_run_id", "backtest_snapshots", ["run_id"])

    # Walk-forward results
    op.create_table(
        "walk_forward_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "run_id",
            sa.String(64),
            sa.ForeignKey("backtest_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("window_id", sa.Integer, nullable=False),
        sa.Column("is_start", sa.Date),
        sa.Column("is_end", sa.Date),
        sa.Column("oos_start", sa.Date),
        sa.Column("oos_end", sa.Date),
        sa.Column("is_sharpe", sa.Float),
        sa.Column("oos_sharpe", sa.Float),
        sa.Column("efficiency_ratio", sa.Float),
        sa.Column("best_params_json", sa.JSON),
    )
    op.create_index("ix_walk_forward_run_id", "walk_forward_results", ["run_id"])

    # Strategy comparisons
    op.create_table(
        "strategy_comparisons",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("comparison_id", sa.String(64), unique=True, nullable=False),
        sa.Column("strategy_names", sa.JSON, nullable=False),
        sa.Column("run_ids", sa.JSON, nullable=False),
        sa.Column("ranking_json", sa.JSON),
        sa.Column("correlation_json", sa.JSON),
        sa.Column("winners_json", sa.JSON),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("strategy_comparisons")
    op.drop_table("walk_forward_results")
    op.drop_table("backtest_snapshots")
    op.drop_table("backtest_trades")
    op.drop_table("backtest_runs")
