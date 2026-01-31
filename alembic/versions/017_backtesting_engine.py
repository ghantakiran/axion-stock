"""Backtesting engine tables.

Revision ID: 017
Revises: 016
Create Date: 2026-01-30

Adds:
- backtest_runs: Stored backtest configurations and results
- backtest_trades: Individual trade records
- walk_forward_results: Walk-forward optimization outputs
- strategy_definitions: Saved strategy configurations
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Strategy definitions
    op.create_table(
        "strategy_definitions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("strategy_id", sa.String(32), unique=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("strategy_type", sa.String(32)),
        sa.Column("params_json", sa.JSON),
        sa.Column("rebalance_frequency", sa.String(16)),
        sa.Column("universe", sa.String(32)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Backtest runs
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.String(32), unique=True, nullable=False),
        sa.Column("strategy_id", sa.String(32)),
        sa.Column("config_json", sa.JSON),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("initial_capital", sa.Float),
        sa.Column("final_equity", sa.Float),
        sa.Column("total_return", sa.Float),
        sa.Column("cagr", sa.Float),
        sa.Column("sharpe_ratio", sa.Float),
        sa.Column("max_drawdown", sa.Float),
        sa.Column("total_trades", sa.Integer),
        sa.Column("metrics_json", sa.JSON),
        sa.Column("equity_curve_json", sa.JSON),
        sa.Column("status", sa.String(16), server_default="completed"),
        sa.Column("executed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_backtest_runs_strategy", "backtest_runs", ["strategy_id"])
    op.create_index("ix_backtest_runs_dates", "backtest_runs", ["start_date", "end_date"])

    # Backtest trades
    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("side", sa.String(8)),
        sa.Column("entry_date", sa.DateTime),
        sa.Column("exit_date", sa.DateTime),
        sa.Column("entry_price", sa.Float),
        sa.Column("exit_price", sa.Float),
        sa.Column("qty", sa.Integer),
        sa.Column("pnl", sa.Float),
        sa.Column("pnl_pct", sa.Float),
        sa.Column("hold_days", sa.Integer),
        sa.Column("sector", sa.String(64)),
        sa.Column("factor_signal", sa.String(32)),
    )
    op.create_index("ix_backtest_trades_run", "backtest_trades", ["run_id"])
    op.create_index("ix_backtest_trades_symbol", "backtest_trades", ["symbol"])

    # Walk-forward results
    op.create_table(
        "walk_forward_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("result_id", sa.String(32), unique=True, nullable=False),
        sa.Column("strategy_id", sa.String(32)),
        sa.Column("n_windows", sa.Integer),
        sa.Column("in_sample_sharpe_avg", sa.Float),
        sa.Column("out_of_sample_sharpe", sa.Float),
        sa.Column("efficiency_ratio", sa.Float),
        sa.Column("windows_json", sa.JSON),
        sa.Column("param_stability_json", sa.JSON),
        sa.Column("combined_metrics_json", sa.JSON),
        sa.Column("executed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_wf_results_strategy", "walk_forward_results", ["strategy_id"])


def downgrade() -> None:
    op.drop_table("walk_forward_results")
    op.drop_table("backtest_trades")
    op.drop_table("backtest_runs")
    op.drop_table("strategy_definitions")
