"""Credit risk analysis tables.

Revision ID: 039
Revises: 038
Create Date: 2026-02-02

Adds:
- credit_spreads: Credit spread observations
- default_probabilities: Default probability estimates
- credit_ratings: Credit rating snapshots
- debt_structures: Debt structure analyses
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Credit spreads
    op.create_table(
        "credit_spreads",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("spread_bps", sa.Float),
        sa.Column("z_score", sa.Float),
        sa.Column("percentile", sa.Float),
        sa.Column("term", sa.Float),
        sa.Column("spread_type", sa.String(20)),
        sa.Column("observed_at", sa.DateTime),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_credit_spreads_symbol", "credit_spreads", ["symbol"])

    # Default probabilities
    op.create_table(
        "default_probabilities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("pd_1y", sa.Float),
        sa.Column("pd_5y", sa.Float),
        sa.Column("model", sa.String(20)),
        sa.Column("distance_to_default", sa.Float),
        sa.Column("recovery_rate", sa.Float),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_default_probabilities_symbol", "default_probabilities", ["symbol"])

    # Credit ratings
    op.create_table(
        "credit_ratings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("rating", sa.String(10)),
        sa.Column("outlook", sa.String(20)),
        sa.Column("previous_rating", sa.String(10)),
        sa.Column("as_of", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_credit_ratings_symbol", "credit_ratings", ["symbol"])

    # Debt structures
    op.create_table(
        "debt_structures",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("total_debt", sa.Float),
        sa.Column("net_debt", sa.Float),
        sa.Column("leverage_ratio", sa.Float),
        sa.Column("interest_coverage", sa.Float),
        sa.Column("avg_maturity", sa.Float),
        sa.Column("avg_coupon", sa.Float),
        sa.Column("near_term_pct", sa.Float),
        sa.Column("refinancing_risk", sa.Float),
        sa.Column("credit_health", sa.Float),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_debt_structures_symbol", "debt_structures", ["symbol"])


def downgrade() -> None:
    op.drop_table("debt_structures")
    op.drop_table("credit_ratings")
    op.drop_table("default_probabilities")
    op.drop_table("credit_spreads")
