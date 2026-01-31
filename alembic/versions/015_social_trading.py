"""Social trading platform tables.

Revision ID: 015
Revises: 014
Create Date: 2026-01-30

Adds:
- trader_profiles: Public profile and settings
- strategies: Published strategy definitions
- strategy_performance: Daily performance snapshots
- copy_relationships: Active copy trading links
- social_posts: Feed items (trade ideas, commentary)
- social_interactions: Likes, comments, bookmarks
- leaderboard_snapshots: Periodic leaderboard captures
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Trader profiles
    op.create_table(
        "trader_profiles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("profile_id", sa.String(32), unique=True, nullable=False),
        sa.Column("user_id", sa.String(64), unique=True, nullable=False),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("bio", sa.Text),
        sa.Column("trading_style", sa.String(32)),
        sa.Column("visibility", sa.String(16), default="public"),
        sa.Column("badges_json", sa.JSON),
        sa.Column("is_verified", sa.Boolean, default=False),
        sa.Column("stats_json", sa.JSON),
        sa.Column("followers_count", sa.Integer, default=0),
        sa.Column("following_count", sa.Integer, default=0),
        sa.Column("strategies_count", sa.Integer, default=0),
        sa.Column("rating", sa.Float, default=0),
        sa.Column("rating_count", sa.Integer, default=0),
        sa.Column("joined_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_profiles_display_name", "trader_profiles", ["display_name"])
    op.create_index("ix_profiles_trading_style", "trader_profiles", ["trading_style"])

    # Strategies
    op.create_table(
        "strategies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("strategy_id", sa.String(32), unique=True, nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("category", sa.String(32)),
        sa.Column("status", sa.String(16), default="draft"),
        sa.Column("tags_json", sa.JSON),
        sa.Column("asset_universe_json", sa.JSON),
        sa.Column("stats_json", sa.JSON),
        sa.Column("copiers_count", sa.Integer, default=0),
        sa.Column("min_capital", sa.Float, default=1000),
        sa.Column("risk_level", sa.Integer, default=3),
        sa.Column("version", sa.Integer, default=1),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_strategies_user", "strategies", ["user_id"])
    op.create_index("ix_strategies_status", "strategies", ["status"])
    op.create_index("ix_strategies_category", "strategies", ["category"])

    # Strategy performance
    op.create_table(
        "strategy_performance",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("strategy_id", sa.String(32), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("daily_return", sa.Float),
        sa.Column("cumulative_return", sa.Float),
        sa.Column("nav", sa.Float),
        sa.Column("drawdown", sa.Float),
        sa.Column("num_positions", sa.Integer),
    )
    op.create_index(
        "ix_strat_perf_strategy_date",
        "strategy_performance", ["strategy_id", "date"],
    )

    # Copy relationships
    op.create_table(
        "copy_relationships",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("copy_id", sa.String(32), unique=True, nullable=False),
        sa.Column("copier_user_id", sa.String(64), nullable=False),
        sa.Column("leader_user_id", sa.String(64), nullable=False),
        sa.Column("strategy_id", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), default="active"),
        sa.Column("mode", sa.String(16), default="fixed_amount"),
        sa.Column("allocation_amount", sa.Float),
        sa.Column("max_loss_pct", sa.Float, default=0.20),
        sa.Column("copy_delay_seconds", sa.Integer, default=0),
        sa.Column("total_pnl", sa.Float, default=0),
        sa.Column("total_trades_copied", sa.Integer, default=0),
        sa.Column("started_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("stopped_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_copy_copier", "copy_relationships", ["copier_user_id"])
    op.create_index("ix_copy_leader", "copy_relationships", ["leader_user_id"])
    op.create_index("ix_copy_status", "copy_relationships", ["status"])

    # Social posts
    op.create_table(
        "social_posts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("post_id", sa.String(32), unique=True, nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(128)),
        sa.Column("post_type", sa.String(32), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=True),
        sa.Column("target_price", sa.Float, nullable=True),
        sa.Column("stop_loss", sa.Float, nullable=True),
        sa.Column("direction", sa.String(8), nullable=True),
        sa.Column("likes_count", sa.Integer, default=0),
        sa.Column("comments_count", sa.Integer, default=0),
        sa.Column("bookmarks_count", sa.Integer, default=0),
        sa.Column("is_trending", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_posts_user", "social_posts", ["user_id"])
    op.create_index("ix_posts_type", "social_posts", ["post_type"])
    op.create_index("ix_posts_symbol", "social_posts", ["symbol"])
    op.create_index("ix_posts_created", "social_posts", ["created_at"])

    # Social interactions
    op.create_table(
        "social_interactions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("interaction_id", sa.String(32), unique=True, nullable=False),
        sa.Column("post_id", sa.String(32), nullable=False),
        sa.Column("user_id", sa.String(64), nullable=False),
        sa.Column("interaction_type", sa.String(16), nullable=False),
        sa.Column("comment_text", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_interactions_post", "social_interactions", ["post_id"])
    op.create_index("ix_interactions_user", "social_interactions", ["user_id"])

    # Leaderboard snapshots
    op.create_table(
        "leaderboard_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("metric", sa.String(32), nullable=False),
        sa.Column("period", sa.String(16), nullable=False),
        sa.Column("entries_json", sa.JSON),
        sa.Column("computed_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_leaderboard_metric_period",
        "leaderboard_snapshots", ["metric", "period"],
    )


def downgrade() -> None:
    op.drop_table("leaderboard_snapshots")
    op.drop_table("social_interactions")
    op.drop_table("social_posts")
    op.drop_table("copy_relationships")
    op.drop_table("strategy_performance")
    op.drop_table("strategies")
    op.drop_table("trader_profiles")
