"""Risk decomposition and performance contribution tables.

Revision ID: 037
Revises: 036
Create Date: 2026-02-02

Adds:
- risk_decompositions: Position-level risk contribution
- performance_contributions: Position return contributions
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Risk decompositions
    op.create_table(
        "risk_decompositions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("portfolio_id", sa.String(50)),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("weight", sa.Float),
        sa.Column("volatility", sa.Float),
        sa.Column("component_risk", sa.Float),
        sa.Column("marginal_risk", sa.Float),
        sa.Column("pct_contribution", sa.Float),
        sa.Column("level", sa.String(20)),  # position or sector
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_risk_decompositions_portfolio",
        "risk_decompositions",
        ["portfolio_id"],
    )

    # Performance contributions
    op.create_table(
        "performance_contributions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("portfolio_id", sa.String(50)),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("weight", sa.Float),
        sa.Column("return_value", sa.Float),
        sa.Column("contribution", sa.Float),
        sa.Column("pct_of_total", sa.Float),
        sa.Column("sector", sa.String(50)),
        sa.Column("contribution_type", sa.String(20)),  # absolute or relative
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_performance_contributions_portfolio",
        "performance_contributions",
        ["portfolio_id"],
    )


def downgrade() -> None:
    op.drop_table("performance_contributions")
    op.drop_table("risk_decompositions")
