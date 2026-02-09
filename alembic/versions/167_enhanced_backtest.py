"""PRD-167: Enhanced Backtest.

Revision ID: 167
Revises: 166
Create Date: 2025-02-09
"""

from alembic import op
import sqlalchemy as sa

revision = "167"
down_revision = "166"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Monte Carlo simulation runs: statistical distribution of strategy outcomes
    op.create_table(
        "monte_carlo_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("strategy", sa.String(30), nullable=False, index=True),
        sa.Column("num_simulations", sa.Integer),
        sa.Column("initial_equity", sa.Float),
        sa.Column("median_final_equity", sa.Float),
        sa.Column("worst_case_drawdown", sa.Float),
        sa.Column("probability_of_profit", sa.Float),
        sa.Column("probability_of_ruin", sa.Float),
        sa.Column("ci_return_low", sa.Float),
        sa.Column("ci_return_high", sa.Float),
        sa.Column("percentiles_json", sa.Text),
        sa.Column("run_time", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Backtest impact analysis: market-impact estimates for historical trades
    op.create_table(
        "backtest_impact_analysis",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("analysis_id", sa.String(50), unique=True, index=True, nullable=False),
        sa.Column("ticker", sa.String(20), nullable=False, index=True),
        sa.Column("order_size", sa.Float),
        sa.Column("daily_volume", sa.Float),
        sa.Column("participation_rate", sa.Float),
        sa.Column("total_impact_bps", sa.Float),
        sa.Column("temporary_impact_bps", sa.Float),
        sa.Column("permanent_impact_bps", sa.Float),
        sa.Column("effective_price", sa.Float),
        sa.Column("slippage_dollars", sa.Float),
        sa.Column("analyzed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("backtest_impact_analysis")
    op.drop_table("monte_carlo_runs")
