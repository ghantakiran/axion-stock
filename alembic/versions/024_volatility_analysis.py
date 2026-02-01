"""Volatility analysis system tables.

Revision ID: 024
Revises: 023
Create Date: 2026-01-31

Adds:
- vol_estimates: Historical volatility computations
- vol_surfaces: Stored surface snapshots
- vol_regimes: Regime history
- vol_term_structures: Term structure snapshots
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Volatility estimates
    op.create_table(
        "vol_estimates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("method", sa.String(16)),
        sa.Column("window", sa.Integer),
        sa.Column("value", sa.Float),
        sa.Column("annualized", sa.Boolean, default=True),
        sa.Column("percentile", sa.Float),
        sa.Column("date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_vol_estimates_symbol_date", "vol_estimates", ["symbol", "date"])
    op.create_index("ix_vol_estimates_method", "vol_estimates", ["method"])

    # Volatility surfaces
    op.create_table(
        "vol_surfaces",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("surface_id", sa.String(32), unique=True, nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("spot", sa.Float),
        sa.Column("n_tenors", sa.Integer),
        sa.Column("tenors_json", sa.JSON),
        sa.Column("surface_data", sa.JSON),
        sa.Column("date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_vol_surfaces_symbol_date", "vol_surfaces", ["symbol", "date"])

    # Volatility regimes
    op.create_table(
        "vol_regimes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("regime_id", sa.String(32), unique=True, nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("regime", sa.String(16)),
        sa.Column("current_vol", sa.Float),
        sa.Column("avg_vol", sa.Float),
        sa.Column("z_score", sa.Float),
        sa.Column("percentile", sa.Float),
        sa.Column("prev_regime", sa.String(16)),
        sa.Column("regime_changed", sa.Boolean),
        sa.Column("days_in_regime", sa.Integer),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_vol_regimes_date", "vol_regimes", ["date"])

    # Term structures
    op.create_table(
        "vol_term_structures",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("structure_id", sa.String(32), unique=True, nullable=False),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("points_json", sa.JSON),
        sa.Column("is_contango", sa.Boolean),
        sa.Column("slope", sa.Float),
        sa.Column("date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_vol_term_structures_symbol_date", "vol_term_structures", ["symbol", "date"])


def downgrade() -> None:
    op.drop_table("vol_term_structures")
    op.drop_table("vol_regimes")
    op.drop_table("vol_surfaces")
    op.drop_table("vol_estimates")
