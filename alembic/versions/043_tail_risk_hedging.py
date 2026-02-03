"""PRD-57: Tail Risk Hedging.

Revision ID: 043
Revises: 042
"""

from alembic import op
import sqlalchemy as sa

revision = "043"
down_revision = "042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # CVaR results
    op.create_table(
        "cvar_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("horizon_days", sa.Integer(), nullable=False),
        sa.Column("var_pct", sa.Float(), nullable=False),
        sa.Column("cvar_pct", sa.Float(), nullable=False),
        sa.Column("var_dollar", sa.Float(), nullable=True),
        sa.Column("cvar_dollar", sa.Float(), nullable=True),
        sa.Column("portfolio_value", sa.Float(), nullable=True),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("tail_ratio", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Tail dependence
    op.create_table(
        "tail_dependence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("asset_a", sa.String(30), nullable=False),
        sa.Column("asset_b", sa.String(30), nullable=False),
        sa.Column("lower_tail", sa.Float(), nullable=False),
        sa.Column("upper_tail", sa.Float(), nullable=False),
        sa.Column("normal_correlation", sa.Float(), nullable=True),
        sa.Column("tail_correlation", sa.Float(), nullable=True),
        sa.Column("contagion_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Hedge recommendations
    op.create_table(
        "hedge_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("instrument", sa.String(20), nullable=False),
        sa.Column("notional", sa.Float(), nullable=False),
        sa.Column("cost_pct", sa.Float(), nullable=False),
        sa.Column("cost_dollar", sa.Float(), nullable=True),
        sa.Column("protection_pct", sa.Float(), nullable=False),
        sa.Column("hedge_ratio", sa.Float(), nullable=True),
        sa.Column("effectiveness", sa.Float(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Drawdown budgets
    op.create_table(
        "drawdown_budgets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("asset", sa.String(30), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("max_drawdown", sa.Float(), nullable=False),
        sa.Column("allocated_budget", sa.Float(), nullable=False),
        sa.Column("current_usage", sa.Float(), nullable=False),
        sa.Column("remaining_budget", sa.Float(), nullable=False),
        sa.Column("recommended_weight", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("drawdown_budgets")
    op.drop_table("hedge_recommendations")
    op.drop_table("tail_dependence")
    op.drop_table("cvar_results")
