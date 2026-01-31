"""Social Trading Platform.

Community-driven social trading with strategy sharing, copy trading,
leaderboards, and a social feed for trade ideas and commentary.

Example:
    from src.social import ProfileManager, StrategyManager, CopyTradingEngine

    # Create profiles
    profiles = ProfileManager()
    profiles.create_profile("u1", "TraderJoe", bio="Swing trader")

    # Publish strategies
    strategies = StrategyManager()
    strategy = strategies.create_strategy("u1", "Momentum Alpha")
    strategies.publish_strategy(strategy.strategy_id)

    # Copy trading
    copy_engine = CopyTradingEngine()
    rel = copy_engine.start_copying("u2", "u1", strategy.strategy_id)
"""

from src.social.config import (
    ProfileVisibility,
    TradingStyle,
    Badge,
    StrategyStatus,
    StrategyCategory,
    CopyStatus,
    CopyMode,
    LeaderboardMetric,
    LeaderboardPeriod,
    PostType,
    InteractionType,
    BADGE_REQUIREMENTS,
    LEADERBOARD_MINIMUMS,
    CopyConfig,
    LeaderboardConfig,
    FeedConfig,
    SocialConfig,
    DEFAULT_SOCIAL_CONFIG,
)

from src.social.models import (
    PerformanceStats,
    TraderProfile,
    Strategy,
    StrategyPerformance,
    CopyRelationship,
    LeaderboardEntry,
    Leaderboard,
    SocialPost,
    SocialInteraction,
    FollowRelationship,
)

from src.social.profiles import ProfileManager
from src.social.strategies import StrategyManager
from src.social.copy_trading import CopyTradingEngine
from src.social.leaderboard import LeaderboardManager
from src.social.feed import FeedManager

__all__ = [
    # Config
    "ProfileVisibility",
    "TradingStyle",
    "Badge",
    "StrategyStatus",
    "StrategyCategory",
    "CopyStatus",
    "CopyMode",
    "LeaderboardMetric",
    "LeaderboardPeriod",
    "PostType",
    "InteractionType",
    "BADGE_REQUIREMENTS",
    "LEADERBOARD_MINIMUMS",
    "CopyConfig",
    "LeaderboardConfig",
    "FeedConfig",
    "SocialConfig",
    "DEFAULT_SOCIAL_CONFIG",
    # Models
    "PerformanceStats",
    "TraderProfile",
    "Strategy",
    "StrategyPerformance",
    "CopyRelationship",
    "LeaderboardEntry",
    "Leaderboard",
    "SocialPost",
    "SocialInteraction",
    "FollowRelationship",
    # Managers
    "ProfileManager",
    "StrategyManager",
    "CopyTradingEngine",
    "LeaderboardManager",
    "FeedManager",
]
