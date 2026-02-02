"""Macro regime analysis system tables.

Revision ID: 034
Revises: 033
Create Date: 2026-02-01

Adds:
- macro_indicators: Economic indicator snapshots
- yield_curve_snapshots: Yield curve data points
- macro_regimes: Detected regime records
- macro_factors: Factor model outputs
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Macro indicators
    op.create_table(
        "macro_indicators",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("value", sa.Float),
        sa.Column("previous", sa.Float),
        sa.Column("consensus", sa.Float),
        sa.Column("surprise", sa.Float),
        sa.Column("indicator_type", sa.String(20)),
        sa.Column("date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_macro_indicators_name", "macro_indicators", ["name"])
    op.create_index("ix_macro_indicators_date", "macro_indicators", ["date"])

    # Yield curve snapshots
    op.create_table(
        "yield_curve_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("shape", sa.String(20)),
        sa.Column("term_spread", sa.Float),
        sa.Column("level", sa.Float),
        sa.Column("slope", sa.Float),
        sa.Column("curvature", sa.Float),
        sa.Column("is_inverted", sa.Boolean),
        sa.Column("inversion_depth", sa.Float),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_yield_curve_snapshots_date", "yield_curve_snapshots", ["date"])

    # Macro regimes
    op.create_table(
        "macro_regimes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("regime", sa.String(20), nullable=False),
        sa.Column("probability", sa.Float),
        sa.Column("duration", sa.Integer),
        sa.Column("indicator_consensus", sa.Float),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_macro_regimes_regime", "macro_regimes", ["regime"])

    # Macro factors
    op.create_table(
        "macro_factors",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("factor_name", sa.String(30), nullable=False),
        sa.Column("factor_return", sa.Float),
        sa.Column("exposure", sa.Float),
        sa.Column("momentum", sa.Float),
        sa.Column("dominant", sa.Boolean),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_macro_factors_name", "macro_factors", ["factor_name"])


def downgrade() -> None:
    op.drop_table("macro_factors")
    op.drop_table("macro_regimes")
    op.drop_table("yield_curve_snapshots")
    op.drop_table("macro_indicators")
