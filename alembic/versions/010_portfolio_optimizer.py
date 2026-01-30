"""Portfolio optimizer tables.

Revision ID: 010
Revises: 009
Create Date: 2026-01-30

Adds:
- portfolios: Saved portfolio configurations
- portfolio_holdings: Individual position weights
- optimization_runs: Optimization history
- rebalance_history: Rebalance trade log
- tax_harvest_log: Tax-loss harvesting records
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Portfolios
    op.create_table(
        "portfolios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("template", sa.String(50)),
        sa.Column("optimization_method", sa.String(30)),
        sa.Column("total_value", sa.Float()),
        sa.Column("num_positions", sa.Integer()),
        sa.Column("expected_return", sa.Float()),
        sa.Column("expected_volatility", sa.Float()),
        sa.Column("sharpe_ratio", sa.Float()),
        sa.Column("rebalance_frequency", sa.String(20)),
        sa.Column("constraints_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Portfolio holdings
    op.create_table(
        "portfolio_holdings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("shares", sa.Float()),
        sa.Column("market_value", sa.Float()),
        sa.Column("cost_basis", sa.Float()),
        sa.Column("unrealized_pnl", sa.Float()),
        sa.Column("sector", sa.String(50)),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_portfolio_holdings_portfolio", "portfolio_holdings", ["portfolio_id"])
    op.create_index("ix_portfolio_holdings_symbol", "portfolio_holdings", ["symbol"])

    # Optimization runs
    op.create_table(
        "optimization_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id")),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("objective_value", sa.Float()),
        sa.Column("expected_return", sa.Float()),
        sa.Column("expected_volatility", sa.Float()),
        sa.Column("sharpe_ratio", sa.Float()),
        sa.Column("converged", sa.Boolean()),
        sa.Column("num_assets", sa.Integer()),
        sa.Column("solve_time_ms", sa.Float()),
        sa.Column("constraints_json", sa.Text()),
        sa.Column("weights_json", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_optimization_runs_portfolio", "optimization_runs", ["portfolio_id"])

    # Rebalance history
    op.create_table(
        "rebalance_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id"), nullable=False),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("shares", sa.Float()),
        sa.Column("value", sa.Float()),
        sa.Column("old_weight", sa.Float()),
        sa.Column("new_weight", sa.Float()),
        sa.Column("tax_impact", sa.Float()),
        sa.Column("is_long_term", sa.Boolean()),
        sa.Column("executed_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_rebalance_history_portfolio", "rebalance_history", ["portfolio_id"])

    # Tax harvest log
    op.create_table(
        "tax_harvest_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id")),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("shares_sold", sa.Float()),
        sa.Column("realized_loss", sa.Float()),
        sa.Column("estimated_tax_savings", sa.Float()),
        sa.Column("replacement_symbol", sa.String(10)),
        sa.Column("wash_sale_risk", sa.Boolean()),
        sa.Column("harvested_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_tax_harvest_log_portfolio", "tax_harvest_log", ["portfolio_id"])


def downgrade() -> None:
    op.drop_table("tax_harvest_log")
    op.drop_table("rebalance_history")
    op.drop_table("optimization_runs")
    op.drop_table("portfolio_holdings")
    op.drop_table("portfolios")
