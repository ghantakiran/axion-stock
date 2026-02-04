"""PRD-62: Liquidity Risk Analytics.

Revision ID: 048
Revises: 047
"""

from alembic import op
import sqlalchemy as sa

revision = "048"
down_revision = "047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Spread model results
    op.create_table(
        "spread_model_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("roll_spread", sa.Float(), nullable=True),
        sa.Column("adverse_selection_pct", sa.Float(), nullable=True),
        sa.Column("order_processing_pct", sa.Float(), nullable=True),
        sa.Column("inventory_pct", sa.Float(), nullable=True),
        sa.Column("forecast_spread_bps", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Market depth snapshots
    op.create_table(
        "market_depth_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("mid_price", sa.Float(), nullable=True),
        sa.Column("bid_depth_10bps", sa.Float(), nullable=True),
        sa.Column("ask_depth_10bps", sa.Float(), nullable=True),
        sa.Column("depth_imbalance", sa.Float(), nullable=True),
        sa.Column("resilience_score", sa.Float(), nullable=True),
        sa.Column("depth_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Illiquidity premium estimates
    op.create_table(
        "illiquidity_premium_estimates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("amihud_ratio", sa.Float(), nullable=False),
        sa.Column("premium_annual_pct", sa.Float(), nullable=True),
        sa.Column("liquidity_beta", sa.Float(), nullable=True),
        sa.Column("liquidity_quintile", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Liquidity concentration reports
    op.create_table(
        "liquidity_concentration_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("n_positions", sa.Integer(), nullable=True),
        sa.Column("hhi_liquidity", sa.Float(), nullable=True),
        sa.Column("pct_liquid_1d", sa.Float(), nullable=True),
        sa.Column("pct_liquid_5d", sa.Float(), nullable=True),
        sa.Column("weighted_avg_dtl", sa.Float(), nullable=True),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("risk_level", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("liquidity_concentration_reports")
    op.drop_table("illiquidity_premium_estimates")
    op.drop_table("market_depth_snapshots")
    op.drop_table("spread_model_results")
