"""PRD-65: Portfolio Stress Testing.

Revision ID: 051
Revises: 050
"""

from alembic import op
import sqlalchemy as sa

revision = "051"
down_revision = "050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Shock propagation results
    op.create_table(
        "shock_propagation_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("scenario_name", sa.String(100), nullable=False),
        sa.Column("total_impact_pct", sa.Float(), nullable=True),
        sa.Column("total_impact_usd", sa.Float(), nullable=True),
        sa.Column("amplification_factor", sa.Float(), nullable=True),
        sa.Column("worst_position", sa.String(30), nullable=True),
        sa.Column("worst_impact", sa.Float(), nullable=True),
        sa.Column("n_positions_affected", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Drawdown metrics snapshots
    op.create_table(
        "drawdown_metrics_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("max_drawdown", sa.Float(), nullable=True),
        sa.Column("current_drawdown", sa.Float(), nullable=True),
        sa.Column("avg_duration", sa.Float(), nullable=True),
        sa.Column("pct_time_underwater", sa.Float(), nullable=True),
        sa.Column("calmar_ratio", sa.Float(), nullable=True),
        sa.Column("ulcer_index", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Recovery estimates
    op.create_table(
        "recovery_estimates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("current_drawdown", sa.Float(), nullable=True),
        sa.Column("expected_days", sa.Float(), nullable=True),
        sa.Column("probability_30d", sa.Float(), nullable=True),
        sa.Column("probability_90d", sa.Float(), nullable=True),
        sa.Column("method", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Custom scenarios
    op.create_table(
        "custom_stress_scenarios",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scenario_type", sa.String(30), nullable=True),
        sa.Column("market_shock", sa.Float(), nullable=True),
        sa.Column("volatility_multiplier", sa.Float(), nullable=True),
        sa.Column("severity_score", sa.Float(), nullable=True),
        sa.Column("created_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("custom_stress_scenarios")
    op.drop_table("recovery_estimates")
    op.drop_table("drawdown_metrics_snapshots")
    op.drop_table("shock_propagation_results")
