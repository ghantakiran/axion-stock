"""Liquidity analysis system tables.

Revision ID: 025
Revises: 024
Create Date: 2026-01-31

Adds:
- spread_analyses: Historical spread computations
- volume_analyses: Volume statistics history
- market_impacts: Impact estimations
- liquidity_scores: Composite scores over time
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Spread analyses
    op.create_table(
        "spread_analyses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("avg_spread", sa.Float),
        sa.Column("median_spread", sa.Float),
        sa.Column("spread_volatility", sa.Float),
        sa.Column("relative_spread", sa.Float),
        sa.Column("effective_spread", sa.Float),
        sa.Column("n_observations", sa.Integer),
        sa.Column("date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_spread_analyses_symbol_date", "spread_analyses", ["symbol", "date"])

    # Volume analyses
    op.create_table(
        "volume_analyses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("avg_volume", sa.Float),
        sa.Column("median_volume", sa.Float),
        sa.Column("volume_ratio", sa.Float),
        sa.Column("avg_dollar_volume", sa.Float),
        sa.Column("vwap", sa.Float),
        sa.Column("n_observations", sa.Integer),
        sa.Column("date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_volume_analyses_symbol_date", "volume_analyses", ["symbol", "date"])

    # Market impacts
    op.create_table(
        "market_impacts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("trade_size", sa.Integer),
        sa.Column("avg_volume", sa.Float),
        sa.Column("participation_rate", sa.Float),
        sa.Column("spread_cost", sa.Float),
        sa.Column("impact_cost", sa.Float),
        sa.Column("total_cost", sa.Float),
        sa.Column("total_cost_bps", sa.Float),
        sa.Column("model", sa.String(16)),
        sa.Column("max_safe_size", sa.Integer),
        sa.Column("execution_days", sa.Integer),
        sa.Column("date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_market_impacts_symbol", "market_impacts", ["symbol"])

    # Liquidity scores
    op.create_table(
        "liquidity_scores",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("symbol", sa.String(16), nullable=False),
        sa.Column("score", sa.Float),
        sa.Column("level", sa.String(16)),
        sa.Column("spread_score", sa.Float),
        sa.Column("volume_score", sa.Float),
        sa.Column("impact_score", sa.Float),
        sa.Column("max_safe_shares", sa.Integer),
        sa.Column("max_safe_dollars", sa.Float),
        sa.Column("date", sa.Date),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_liquidity_scores_symbol_date", "liquidity_scores", ["symbol", "date"])
    op.create_index("ix_liquidity_scores_level", "liquidity_scores", ["level"])


def downgrade() -> None:
    op.drop_table("liquidity_scores")
    op.drop_table("market_impacts")
    op.drop_table("volume_analyses")
    op.drop_table("spread_analyses")
