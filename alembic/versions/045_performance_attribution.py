"""PRD-59: Performance Attribution Extensions.

Revision ID: 045
Revises: 044
"""

from alembic import op
import sqlalchemy as sa

revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Multi-period linked attribution
    op.create_table(
        "linked_attribution",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("linking_method", sa.String(20), nullable=False),
        sa.Column("n_periods", sa.Integer(), nullable=False),
        sa.Column("total_portfolio_return", sa.Float(), nullable=False),
        sa.Column("total_benchmark_return", sa.Float(), nullable=False),
        sa.Column("total_active_return", sa.Float(), nullable=False),
        sa.Column("linked_allocation", sa.Float(), nullable=False),
        sa.Column("linked_selection", sa.Float(), nullable=False),
        sa.Column("linked_interaction", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Fama-French model results
    op.create_table(
        "ff_model_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("model_name", sa.String(10), nullable=False),
        sa.Column("alpha", sa.Float(), nullable=False),
        sa.Column("alpha_annualized", sa.Float(), nullable=True),
        sa.Column("alpha_t_stat", sa.Float(), nullable=True),
        sa.Column("r_squared", sa.Float(), nullable=False),
        sa.Column("adjusted_r_squared", sa.Float(), nullable=True),
        sa.Column("residual_volatility", sa.Float(), nullable=True),
        sa.Column("n_observations", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Geographic attribution
    op.create_table(
        "geographic_attribution",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("country", sa.String(10), nullable=False),
        sa.Column("region", sa.String(30), nullable=True),
        sa.Column("portfolio_weight", sa.Float(), nullable=False),
        sa.Column("benchmark_weight", sa.Float(), nullable=False),
        sa.Column("portfolio_return", sa.Float(), nullable=False),
        sa.Column("benchmark_return", sa.Float(), nullable=False),
        sa.Column("allocation_effect", sa.Float(), nullable=True),
        sa.Column("selection_effect", sa.Float(), nullable=True),
        sa.Column("interaction_effect", sa.Float(), nullable=True),
        sa.Column("currency_effect", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Risk-adjusted metrics
    op.create_table(
        "risk_adjusted_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("strategy_name", sa.String(50), nullable=True),
        sa.Column("sharpe_ratio", sa.Float(), nullable=True),
        sa.Column("sortino_ratio", sa.Float(), nullable=True),
        sa.Column("calmar_ratio", sa.Float(), nullable=True),
        sa.Column("m_squared", sa.Float(), nullable=True),
        sa.Column("omega_ratio", sa.Float(), nullable=True),
        sa.Column("sterling_ratio", sa.Float(), nullable=True),
        sa.Column("burke_ratio", sa.Float(), nullable=True),
        sa.Column("ulcer_index", sa.Float(), nullable=True),
        sa.Column("tail_ratio", sa.Float(), nullable=True),
        sa.Column("composite_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("risk_adjusted_metrics")
    op.drop_table("geographic_attribution")
    op.drop_table("ff_model_results")
    op.drop_table("linked_attribution")
