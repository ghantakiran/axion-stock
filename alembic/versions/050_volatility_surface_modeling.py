"""PRD-64: Volatility Surface Modeling.

Revision ID: 050
Revises: 049
"""

from alembic import op
import sqlalchemy as sa

revision = "050"
down_revision = "049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SVI calibration results
    op.create_table(
        "svi_calibration_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("tenor_days", sa.Integer(), nullable=False),
        sa.Column("a", sa.Float(), nullable=True),
        sa.Column("b", sa.Float(), nullable=True),
        sa.Column("rho", sa.Float(), nullable=True),
        sa.Column("m", sa.Float(), nullable=True),
        sa.Column("sigma", sa.Float(), nullable=True),
        sa.Column("rmse", sa.Float(), nullable=True),
        sa.Column("atm_vol", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Skew analytics snapshots
    op.create_table(
        "skew_analytics_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("tenor_days", sa.Integer(), nullable=True),
        sa.Column("risk_reversal", sa.Float(), nullable=True),
        sa.Column("butterfly", sa.Float(), nullable=True),
        sa.Column("skew_z_score", sa.Float(), nullable=True),
        sa.Column("skew_regime", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Term structure fits
    op.create_table(
        "vol_term_structure_fits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("beta0", sa.Float(), nullable=True),
        sa.Column("beta1", sa.Float(), nullable=True),
        sa.Column("beta2", sa.Float(), nullable=True),
        sa.Column("tau", sa.Float(), nullable=True),
        sa.Column("shape", sa.String(20), nullable=True),
        sa.Column("rmse", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Vol regime signal snapshots
    op.create_table(
        "vol_regime_signal_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("vol_of_vol", sa.Float(), nullable=True),
        sa.Column("vov_percentile", sa.Float(), nullable=True),
        sa.Column("mr_z_score", sa.Float(), nullable=True),
        sa.Column("mr_signal", sa.String(20), nullable=True),
        sa.Column("composite_signal", sa.String(30), nullable=True),
        sa.Column("composite_strength", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("vol_regime_signal_snapshots")
    op.drop_table("vol_term_structure_fits")
    op.drop_table("skew_analytics_snapshots")
    op.drop_table("svi_calibration_results")
