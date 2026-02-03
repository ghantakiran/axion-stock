"""PRD-56: Cross-Asset Signals.

Revision ID: 042
Revises: 041
"""

from alembic import op
import sqlalchemy as sa

revision = "042"
down_revision = "041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Asset pair correlations
    op.create_table(
        "cross_asset_correlations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("asset_a", sa.String(30), nullable=False),
        sa.Column("asset_b", sa.String(30), nullable=False),
        sa.Column("correlation", sa.Float(), nullable=False),
        sa.Column("long_term_correlation", sa.Float(), nullable=True),
        sa.Column("z_score", sa.Float(), nullable=True),
        sa.Column("regime", sa.String(20), nullable=True),
        sa.Column("beta", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Lead-lag results
    op.create_table(
        "cross_asset_leadlag",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("leader", sa.String(30), nullable=False),
        sa.Column("lagger", sa.String(30), nullable=False),
        sa.Column("optimal_lag", sa.Integer(), nullable=False),
        sa.Column("correlation_at_lag", sa.Float(), nullable=False),
        sa.Column("is_significant", sa.Boolean(), nullable=False),
        sa.Column("stability", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Momentum signals
    op.create_table(
        "cross_asset_momentum",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("asset", sa.String(30), nullable=False),
        sa.Column("asset_class", sa.String(20), nullable=True),
        sa.Column("ts_momentum", sa.Float(), nullable=False),
        sa.Column("xs_rank", sa.Float(), nullable=True),
        sa.Column("z_score", sa.Float(), nullable=True),
        sa.Column("trend_strength", sa.Float(), nullable=True),
        sa.Column("signal", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Composite signals
    op.create_table(
        "cross_asset_signals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("asset", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("strength", sa.String(20), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("intermarket_component", sa.Float(), nullable=True),
        sa.Column("leadlag_component", sa.Float(), nullable=True),
        sa.Column("momentum_component", sa.Float(), nullable=True),
        sa.Column("mean_reversion_component", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("cross_asset_signals")
    op.drop_table("cross_asset_momentum")
    op.drop_table("cross_asset_leadlag")
    op.drop_table("cross_asset_correlations")
