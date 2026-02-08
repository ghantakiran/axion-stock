"""PRD-94: Earnings Intelligence.

Revision ID: 094
Revises: 093
"""

from alembic import op
import sqlalchemy as sa

revision = "094"
down_revision = "093"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Earnings quality assessment history
    op.create_table(
        "earnings_quality_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("fiscal_quarter", sa.String(10), nullable=False),
        sa.Column("m_score", sa.Float(), nullable=True),
        sa.Column("accruals_ratio", sa.Float(), nullable=True),
        sa.Column("cash_conversion", sa.Float(), nullable=True),
        sa.Column("quality_rating", sa.String(20), nullable=False),
        sa.Column("red_flags", sa.JSON(), nullable=True),
        sa.Column("assessed_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    # Price reaction tracking
    op.create_table(
        "earnings_reaction_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("earnings_date", sa.DateTime(), nullable=False),
        sa.Column("eps_surprise_pct", sa.Float(), nullable=True),
        sa.Column("gap_pct", sa.Float(), nullable=True),
        sa.Column("day1_return_pct", sa.Float(), nullable=True),
        sa.Column("day5_drift_pct", sa.Float(), nullable=True),
        sa.Column("day20_drift_pct", sa.Float(), nullable=True),
        sa.Column("pre_earnings_vol", sa.Float(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("earnings_reaction_history")
    op.drop_table("earnings_quality_scores")
