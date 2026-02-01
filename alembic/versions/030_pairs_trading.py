"""Pairs trading system tables.

Revision ID: 030
Revises: 029
Create Date: 2026-02-01

Adds:
- cointegration_tests: Cointegration test results
- spread_snapshots: Spread analysis snapshots
- pair_scores: Pair quality scores
- pair_signals: Generated trading signals
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cointegration tests
    op.create_table(
        "cointegration_tests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("asset_a", sa.String(16), nullable=False),
        sa.Column("asset_b", sa.String(16), nullable=False),
        sa.Column("test_statistic", sa.Float),
        sa.Column("pvalue", sa.Float),
        sa.Column("hedge_ratio", sa.Float),
        sa.Column("intercept", sa.Float),
        sa.Column("correlation", sa.Float),
        sa.Column("status", sa.String(20)),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_cointegration_tests_pair", "cointegration_tests", ["asset_a", "asset_b"])

    # Spread snapshots
    op.create_table(
        "spread_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("asset_a", sa.String(16), nullable=False),
        sa.Column("asset_b", sa.String(16), nullable=False),
        sa.Column("current_spread", sa.Float),
        sa.Column("spread_mean", sa.Float),
        sa.Column("spread_std", sa.Float),
        sa.Column("zscore", sa.Float),
        sa.Column("half_life", sa.Float),
        sa.Column("hurst_exponent", sa.Float),
        sa.Column("signal", sa.String(20)),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_spread_snapshots_pair", "spread_snapshots", ["asset_a", "asset_b"])

    # Pair scores
    op.create_table(
        "pair_scores",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("asset_a", sa.String(16), nullable=False),
        sa.Column("asset_b", sa.String(16), nullable=False),
        sa.Column("total_score", sa.Float),
        sa.Column("cointegration_score", sa.Float),
        sa.Column("half_life_score", sa.Float),
        sa.Column("correlation_score", sa.Float),
        sa.Column("hurst_score", sa.Float),
        sa.Column("rank", sa.Integer),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_pair_scores_pair", "pair_scores", ["asset_a", "asset_b"])

    # Pair signals
    op.create_table(
        "pair_signals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("asset_a", sa.String(16), nullable=False),
        sa.Column("asset_b", sa.String(16), nullable=False),
        sa.Column("signal", sa.String(20)),
        sa.Column("zscore", sa.Float),
        sa.Column("hedge_ratio", sa.Float),
        sa.Column("spread", sa.Float),
        sa.Column("confidence", sa.Float),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_pair_signals_pair", "pair_signals", ["asset_a", "asset_b"])


def downgrade() -> None:
    op.drop_table("pair_signals")
    op.drop_table("pair_scores")
    op.drop_table("spread_snapshots")
    op.drop_table("cointegration_tests")
