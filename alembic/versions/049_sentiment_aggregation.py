"""PRD-63: Sentiment Aggregation.

Revision ID: 049
Revises: 048
"""

from alembic import op
import sqlalchemy as sa

revision = "049"
down_revision = "048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Decay-weighted sentiment snapshots
    op.create_table(
        "decay_weighted_sentiment",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("weighted_score", sa.Float(), nullable=True),
        sa.Column("unweighted_score", sa.Float(), nullable=True),
        sa.Column("avg_age_hours", sa.Float(), nullable=True),
        sa.Column("freshness_ratio", sa.Float(), nullable=True),
        sa.Column("effective_sources", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Sentiment fusion results
    op.create_table(
        "sentiment_fusion_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("fused_score", sa.Float(), nullable=True),
        sa.Column("fused_confidence", sa.Float(), nullable=True),
        sa.Column("agreement_ratio", sa.Float(), nullable=True),
        sa.Column("conflict_level", sa.Float(), nullable=True),
        sa.Column("dominant_source", sa.String(30), nullable=True),
        sa.Column("n_sources", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Consensus snapshots
    op.create_table(
        "sentiment_consensus_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("consensus_direction", sa.String(20), nullable=True),
        sa.Column("consensus_score", sa.Float(), nullable=True),
        sa.Column("consensus_strength", sa.Float(), nullable=True),
        sa.Column("unanimity", sa.Float(), nullable=True),
        sa.Column("n_bullish", sa.Integer(), nullable=True),
        sa.Column("n_bearish", sa.Integer(), nullable=True),
        sa.Column("n_neutral", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Sentiment momentum snapshots
    op.create_table(
        "sentiment_momentum_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(30), nullable=False),
        sa.Column("current_score", sa.Float(), nullable=True),
        sa.Column("momentum", sa.Float(), nullable=True),
        sa.Column("acceleration", sa.Float(), nullable=True),
        sa.Column("trend_direction", sa.String(20), nullable=True),
        sa.Column("trend_strength", sa.Float(), nullable=True),
        sa.Column("is_inflecting", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("sentiment_momentum_snapshots")
    op.drop_table("sentiment_consensus_snapshots")
    op.drop_table("sentiment_fusion_results")
    op.drop_table("decay_weighted_sentiment")
