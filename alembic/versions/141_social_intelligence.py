"""Social signal intelligence integration.

Revision ID: 141
Revises: 140
Create Date: 2025-02-02
"""

from alembic import op
import sqlalchemy as sa

revision = "141"
down_revision = "140"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Social signal scores
    op.create_table(
        "social_signal_scores",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("strength", sa.String(20)),
        sa.Column("direction", sa.String(20)),
        sa.Column("sentiment_score", sa.Float),
        sa.Column("engagement_score", sa.Float),
        sa.Column("velocity_score", sa.Float),
        sa.Column("freshness_score", sa.Float),
        sa.Column("credibility_score", sa.Float),
        sa.Column("mention_count", sa.Integer),
        sa.Column("platforms_json", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Volume anomalies
    op.create_table(
        "social_volume_anomalies",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("current_volume", sa.Integer, nullable=False),
        sa.Column("baseline_mean", sa.Float),
        sa.Column("baseline_std", sa.Float),
        sa.Column("z_score", sa.Float),
        sa.Column("volume_ratio", sa.Float),
        sa.Column("severity", sa.String(20)),
        sa.Column("is_extreme", sa.Boolean, server_default="false"),
        sa.Column("is_sustained", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Influencer profiles
    op.create_table(
        "social_influencer_profiles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("author_id", sa.String(100), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("tier", sa.String(20)),
        sa.Column("total_posts", sa.Integer, server_default="0"),
        sa.Column("total_upvotes", sa.Integer, server_default="0"),
        sa.Column("accuracy_rate", sa.Float),
        sa.Column("impact_score", sa.Float),
        sa.Column("top_tickers_json", sa.Text),
        sa.Column("last_seen", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index(
        "ix_social_influencer_platform_author",
        "social_influencer_profiles",
        ["platform", "author_id"],
        unique=True,
    )

    # Social trading signals
    op.create_table(
        "social_trading_signals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("symbol", sa.String(20), nullable=False, index=True),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("confidence", sa.Float),
        sa.Column("direction", sa.String(20)),
        sa.Column("final_score", sa.Float),
        sa.Column("has_volume_anomaly", sa.Boolean, server_default="false"),
        sa.Column("has_influencer_signal", sa.Boolean, server_default="false"),
        sa.Column("is_consensus", sa.Boolean, server_default="false"),
        sa.Column("reasons_json", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("social_trading_signals")
    op.drop_index("ix_social_influencer_platform_author", "social_influencer_profiles")
    op.drop_table("social_influencer_profiles")
    op.drop_table("social_volume_anomalies")
    op.drop_table("social_signal_scores")
