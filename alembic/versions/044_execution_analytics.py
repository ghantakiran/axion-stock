"""PRD-58: Execution Analytics.

Revision ID: 044
Revises: 043
"""

from alembic import op
import sqlalchemy as sa

revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # TCA results
    op.create_table(
        "tca_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("decision_price", sa.Float(), nullable=False),
        sa.Column("arrival_price", sa.Float(), nullable=False),
        sa.Column("execution_price", sa.Float(), nullable=False),
        sa.Column("benchmark_vwap", sa.Float(), nullable=True),
        sa.Column("total_cost_bps", sa.Float(), nullable=False),
        sa.Column("spread_cost_bps", sa.Float(), nullable=True),
        sa.Column("timing_cost_bps", sa.Float(), nullable=True),
        sa.Column("impact_cost_bps", sa.Float(), nullable=True),
        sa.Column("opportunity_cost_bps", sa.Float(), nullable=True),
        sa.Column("commission_bps", sa.Float(), nullable=True),
        sa.Column("fill_rate", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Execution schedules
    op.create_table(
        "execution_schedules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("strategy", sa.String(20), nullable=False),
        sa.Column("total_quantity", sa.Float(), nullable=False),
        sa.Column("n_slices", sa.Integer(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("estimated_impact_bps", sa.Float(), nullable=True),
        sa.Column("urgency", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Broker stats
    op.create_table(
        "broker_stats",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("broker", sa.String(50), nullable=False),
        sa.Column("n_orders", sa.Integer(), nullable=False),
        sa.Column("n_filled", sa.Integer(), nullable=False),
        sa.Column("total_notional", sa.Float(), nullable=True),
        sa.Column("fill_rate", sa.Float(), nullable=True),
        sa.Column("avg_slippage_bps", sa.Float(), nullable=True),
        sa.Column("avg_commission_bps", sa.Float(), nullable=True),
        sa.Column("avg_total_cost_bps", sa.Float(), nullable=True),
        sa.Column("price_improvement_rate", sa.Float(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Fill quality
    op.create_table(
        "fill_quality",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("fill_price", sa.Float(), nullable=False),
        sa.Column("midpoint", sa.Float(), nullable=True),
        sa.Column("effective_spread_bps", sa.Float(), nullable=True),
        sa.Column("price_improvement_bps", sa.Float(), nullable=True),
        sa.Column("adverse_selection_bps", sa.Float(), nullable=True),
        sa.Column("fill_rate", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("fill_quality")
    op.drop_table("broker_stats")
    op.drop_table("execution_schedules")
    op.drop_table("tca_results")
