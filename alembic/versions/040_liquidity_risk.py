"""PRD-54: Liquidity Risk Management.

Revision ID: 040
Revises: 039
"""

from alembic import op
import sqlalchemy as sa

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Redemption scenarios
    op.create_table(
        "redemption_scenarios",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("scenario_name", sa.String(50), nullable=False),
        sa.Column("redemption_pct", sa.Float(), nullable=False),
        sa.Column("redemption_amount", sa.Float(), nullable=False),
        sa.Column("liquid_assets", sa.Float(), nullable=False),
        sa.Column("coverage_ratio", sa.Float(), nullable=False),
        sa.Column("shortfall", sa.Float(), nullable=False),
        sa.Column("days_to_meet", sa.Integer(), nullable=False),
        sa.Column("total_aum", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Liquidity buffer snapshots
    op.create_table(
        "liquidity_buffers",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("total_aum", sa.Float(), nullable=False),
        sa.Column("cash_on_hand", sa.Float(), nullable=False),
        sa.Column("liquid_assets", sa.Float(), nullable=False),
        sa.Column("expected_redemption", sa.Float(), nullable=False),
        sa.Column("required_buffer", sa.Float(), nullable=False),
        sa.Column("coverage_ratio", sa.Float(), nullable=False),
        sa.Column("buffer_deficit", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Liquidation schedule items
    op.create_table(
        "liquidation_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("position_value", sa.Float(), nullable=False),
        sa.Column("avg_daily_volume_usd", sa.Float(), nullable=False),
        sa.Column("max_daily_liquidation", sa.Float(), nullable=False),
        sa.Column("days_to_liquidate", sa.Float(), nullable=False),
        sa.Column("liquidation_cost_bps", sa.Float(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # LaVaR results
    op.create_table(
        "lavar_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("portfolio_value", sa.Float(), nullable=False),
        sa.Column("var_pct", sa.Float(), nullable=False),
        sa.Column("var_dollar", sa.Float(), nullable=False),
        sa.Column("liquidity_cost_pct", sa.Float(), nullable=False),
        sa.Column("liquidity_cost_dollar", sa.Float(), nullable=False),
        sa.Column("lavar_pct", sa.Float(), nullable=False),
        sa.Column("lavar_dollar", sa.Float(), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("lavar_results")
    op.drop_table("liquidation_items")
    op.drop_table("liquidity_buffers")
    op.drop_table("redemption_scenarios")
