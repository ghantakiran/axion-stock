"""PRD-77: ESG Scoring & Impact Tracking.

Revision ID: 077
Revises: 076
"""

from alembic import op
import sqlalchemy as sa

revision = "077"
down_revision = "076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ESG scores per security
    op.create_table(
        "esg_scores",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("environmental_score", sa.Float(), nullable=False),
        sa.Column("social_score", sa.Float(), nullable=False),
        sa.Column("governance_score", sa.Float(), nullable=False),
        sa.Column("composite_score", sa.Float(), nullable=False),
        sa.Column("rating", sa.String(5), nullable=False),
        sa.Column("controversy_score", sa.Float(), server_default="0"),
        sa.Column("controversies", sa.JSON(), nullable=True),
        sa.Column("sector", sa.String(50), nullable=True),
        sa.Column("sector_rank", sa.Integer(), nullable=True),
        sa.Column("pillar_scores", sa.JSON(), nullable=True),
        sa.Column("data_source", sa.String(50), nullable=True),
        sa.Column("as_of_date", sa.Date(), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Impact metrics tracking
    op.create_table(
        "esg_impact_metrics",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(30), nullable=True),
        sa.Column("benchmark", sa.Float(), nullable=True),
        sa.Column("percentile", sa.Float(), nullable=True),
        sa.Column("trend", sa.String(20), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table("esg_impact_metrics")
    op.drop_table("esg_scores")
