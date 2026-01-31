"""Paper trading system tables.

Revision ID: 020
Revises: 019
Create Date: 2026-01-30

Adds:
- paper_sessions: Session configurations and state
- paper_trades: Individual trade records per session
- paper_snapshots: Periodic portfolio snapshots
- paper_session_metrics: Final session performance metrics
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Paper trading sessions
    op.create_table(
        "paper_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.String(32), unique=True, nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("strategy_type", sa.String(32)),
        sa.Column("initial_capital", sa.Float),
        sa.Column("final_equity", sa.Float),
        sa.Column("symbols_json", sa.JSON),
        sa.Column("benchmark", sa.String(16)),
        sa.Column("config_json", sa.JSON),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime),
        sa.Column("completed_at", sa.DateTime),
    )
    op.create_index("ix_paper_sessions_status", "paper_sessions", ["status"])

    # Paper trades
    op.create_table(
        "paper_trades",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("trade_id", sa.String(32), unique=True, nullable=False),
        sa.Column("session_id", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("qty", sa.Integer),
        sa.Column("price", sa.Float),
        sa.Column("notional", sa.Float),
        sa.Column("commission", sa.Float),
        sa.Column("slippage", sa.Float),
        sa.Column("pnl", sa.Float),
        sa.Column("pnl_pct", sa.Float),
        sa.Column("reason", sa.String(32)),
        sa.Column("timestamp", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_paper_trades_session", "paper_trades", ["session_id"])
    op.create_index("ix_paper_trades_symbol", "paper_trades", ["symbol"])

    # Paper snapshots
    op.create_table(
        "paper_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("snapshot_id", sa.String(32), unique=True, nullable=False),
        sa.Column("session_id", sa.String(32), nullable=False),
        sa.Column("timestamp", sa.DateTime, nullable=False),
        sa.Column("equity", sa.Float),
        sa.Column("cash", sa.Float),
        sa.Column("positions_value", sa.Float),
        sa.Column("n_positions", sa.Integer),
        sa.Column("drawdown", sa.Float),
        sa.Column("peak_equity", sa.Float),
        sa.Column("daily_return", sa.Float),
    )
    op.create_index(
        "ix_paper_snapshots_session_time",
        "paper_snapshots", ["session_id", "timestamp"],
    )

    # Paper session metrics
    op.create_table(
        "paper_session_metrics",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.String(32), unique=True, nullable=False),
        sa.Column("total_return", sa.Float),
        sa.Column("annualized_return", sa.Float),
        sa.Column("benchmark_return", sa.Float),
        sa.Column("volatility", sa.Float),
        sa.Column("sharpe_ratio", sa.Float),
        sa.Column("sortino_ratio", sa.Float),
        sa.Column("calmar_ratio", sa.Float),
        sa.Column("max_drawdown", sa.Float),
        sa.Column("total_trades", sa.Integer),
        sa.Column("win_rate", sa.Float),
        sa.Column("profit_factor", sa.Float),
        sa.Column("total_costs", sa.Float),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("paper_session_metrics")
    op.drop_table("paper_snapshots")
    op.drop_table("paper_trades")
    op.drop_table("paper_sessions")
