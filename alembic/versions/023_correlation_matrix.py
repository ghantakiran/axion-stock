"""Correlation analysis system tables.

Revision ID: 023
Revises: 022
Create Date: 2026-01-31

Adds:
- correlation_matrices: Stored correlation matrix metadata
- correlation_pairs: Individual pair correlations
- correlation_regimes: Regime detection history
- diversification_scores: Portfolio diversification assessments
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Correlation matrices
    op.create_table(
        "correlation_matrices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("matrix_id", sa.String(32), unique=True, nullable=False),
        sa.Column("symbols_json", sa.JSON),
        sa.Column("method", sa.String(16)),
        sa.Column("n_assets", sa.Integer),
        sa.Column("n_periods", sa.Integer),
        sa.Column("avg_correlation", sa.Float),
        sa.Column("max_correlation", sa.Float),
        sa.Column("min_correlation", sa.Float),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
        sa.Column("matrix_data", sa.JSON),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_correlation_matrices_end_date", "correlation_matrices", ["end_date"])

    # Correlation pairs
    op.create_table(
        "correlation_pairs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("matrix_id", sa.String(32), nullable=False),
        sa.Column("symbol_a", sa.String(16), nullable=False),
        sa.Column("symbol_b", sa.String(16), nullable=False),
        sa.Column("correlation", sa.Float),
        sa.Column("method", sa.String(16)),
        sa.Column("stability", sa.Float),
    )
    op.create_index("ix_correlation_pairs_matrix", "correlation_pairs", ["matrix_id"])
    op.create_index("ix_correlation_pairs_symbols", "correlation_pairs", ["symbol_a", "symbol_b"])

    # Correlation regimes
    op.create_table(
        "correlation_regimes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("regime_id", sa.String(32), unique=True, nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("regime", sa.String(16)),
        sa.Column("avg_correlation", sa.Float),
        sa.Column("dispersion", sa.Float),
        sa.Column("prev_regime", sa.String(16)),
        sa.Column("regime_changed", sa.Boolean),
        sa.Column("days_in_regime", sa.Integer),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_correlation_regimes_date", "correlation_regimes", ["date"])

    # Diversification scores
    op.create_table(
        "diversification_scores",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("score_id", sa.String(32), unique=True, nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("diversification_ratio", sa.Float),
        sa.Column("effective_n_bets", sa.Float),
        sa.Column("avg_pair_correlation", sa.Float),
        sa.Column("max_pair_correlation", sa.Float),
        sa.Column("max_pair_json", sa.JSON),
        sa.Column("level", sa.String(16)),
        sa.Column("n_assets", sa.Integer),
        sa.Column("n_highly_correlated", sa.Integer),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_diversification_scores_date", "diversification_scores", ["date"])


def downgrade() -> None:
    op.drop_table("diversification_scores")
    op.drop_table("correlation_regimes")
    op.drop_table("correlation_pairs")
    op.drop_table("correlation_matrices")
