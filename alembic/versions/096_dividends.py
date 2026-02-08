"""PRD-96: Dividend Tracker.

Revision ID: 096
Revises: 095
"""

from alembic import op
import sqlalchemy as sa

revision = "096"
down_revision = "095"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Income forecast snapshots
    op.create_table(
        "dividend_income_projections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("portfolio_id", sa.String(36), nullable=True, index=True),
        sa.Column("total_annual_income", sa.Float(), nullable=False),
        sa.Column("weighted_yield", sa.Float(), nullable=True),
        sa.Column("monthly_breakdown", sa.JSON(), nullable=True),
        sa.Column("sector_breakdown", sa.JSON(), nullable=True),
        sa.Column("n_holdings", sa.Integer(), nullable=False),
        sa.Column("projected_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # Safety assessment history
    op.create_table(
        "dividend_safety_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("safety_score", sa.Float(), nullable=False),
        sa.Column("safety_rating", sa.String(20), nullable=False),
        sa.Column("payout_ratio_earnings", sa.Float(), nullable=True),
        sa.Column("payout_ratio_cash", sa.Float(), nullable=True),
        sa.Column("debt_to_ebitda", sa.Float(), nullable=True),
        sa.Column("red_flags", sa.JSON(), nullable=True),
        sa.Column("assessed_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("dividend_safety_scores")
    op.drop_table("dividend_income_projections")
