"""Social Trading configuration.

Enums, constants, and configuration dataclasses.
"""

import enum
from dataclasses import dataclass, field


class ProfileVisibility(enum.Enum):
    """Profile visibility levels."""
    PUBLIC = "public"
    FOLLOWERS_ONLY = "followers_only"
    PRIVATE = "private"


class TradingStyle(enum.Enum):
    """Trading style categories."""
    DAY_TRADING = "day_trading"
    SWING_TRADING = "swing_trading"
    POSITION_TRADING = "position_trading"
    SCALPING = "scalping"
    VALUE_INVESTING = "value_investing"
    GROWTH_INVESTING = "growth_investing"
    MOMENTUM = "momentum"
    QUANTITATIVE = "quantitative"


class Badge(enum.Enum):
    """Achievement badges."""
    TOP_PERFORMER = "top_performer"
    CONSISTENT = "consistent"
    RISING_STAR = "rising_star"
    VETERAN = "veteran"
    RISK_MASTER = "risk_master"
    DIVERSIFIED = "diversified"
    COMMUNITY_LEADER = "community_leader"
    VERIFIED = "verified"


class StrategyStatus(enum.Enum):
    """Strategy publication status."""
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    SUSPENDED = "suspended"


class StrategyCategory(enum.Enum):
    """Strategy categories."""
    EQUITY_LONG = "equity_long"
    EQUITY_LONG_SHORT = "equity_long_short"
    OPTIONS = "options"
    CRYPTO = "crypto"
    FUTURES = "futures"
    MULTI_ASSET = "multi_asset"
    INCOME = "income"
    MOMENTUM = "momentum"
    VALUE = "value"
    QUANTITATIVE = "quantitative"


class CopyStatus(enum.Enum):
    """Copy relationship status."""
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"
    MAX_LOSS_HIT = "max_loss_hit"


class CopyMode(enum.Enum):
    """Copy trading allocation mode."""
    FIXED_AMOUNT = "fixed_amount"
    PERCENTAGE = "percentage"
    PROPORTIONAL = "proportional"


class LeaderboardMetric(enum.Enum):
    """Leaderboard ranking metrics."""
    TOTAL_RETURN = "total_return"
    SHARPE_RATIO = "sharpe_ratio"
    WIN_RATE = "win_rate"
    CONSISTENCY = "consistency"
    RISK_ADJUSTED = "risk_adjusted"
    PROFIT_FACTOR = "profit_factor"


class LeaderboardPeriod(enum.Enum):
    """Leaderboard time periods."""
    ONE_MONTH = "1M"
    THREE_MONTHS = "3M"
    SIX_MONTHS = "6M"
    ONE_YEAR = "1Y"
    ALL_TIME = "all_time"


class PostType(enum.Enum):
    """Social feed post types."""
    TRADE_IDEA = "trade_idea"
    POSITION_UPDATE = "position_update"
    MARKET_ANALYSIS = "market_analysis"
    STRATEGY_UPDATE = "strategy_update"
    COMMENTARY = "commentary"


class InteractionType(enum.Enum):
    """Social interaction types."""
    LIKE = "like"
    COMMENT = "comment"
    BOOKMARK = "bookmark"
    SHARE = "share"


# Badge requirements
BADGE_REQUIREMENTS: dict[Badge, dict] = {
    Badge.TOP_PERFORMER: {
        "description": "Top 10% returns over 6 months",
        "min_return_percentile": 90,
        "min_history_days": 180,
    },
    Badge.CONSISTENT: {
        "description": "Positive returns 8 of last 12 months",
        "min_positive_months": 8,
        "lookback_months": 12,
    },
    Badge.RISING_STAR: {
        "description": "Top 20% returns in first 3 months",
        "min_return_percentile": 80,
        "max_history_days": 90,
    },
    Badge.VETERAN: {
        "description": "Active trader for 1+ year with 100+ trades",
        "min_history_days": 365,
        "min_trades": 100,
    },
    Badge.RISK_MASTER: {
        "description": "Sharpe > 1.5 with max drawdown < 10%",
        "min_sharpe": 1.5,
        "max_drawdown": 0.10,
    },
    Badge.DIVERSIFIED: {
        "description": "Trades across 3+ asset classes",
        "min_asset_classes": 3,
    },
    Badge.COMMUNITY_LEADER: {
        "description": "50+ followers with 4+ star rating",
        "min_followers": 50,
        "min_rating": 4.0,
    },
    Badge.VERIFIED: {
        "description": "Identity and track record verified",
        "requires_verification": True,
    },
}

# Leaderboard minimum requirements (anti-gaming)
LEADERBOARD_MINIMUMS = {
    "min_trades": 10,
    "min_history_days": 30,
    "min_unique_symbols": 3,
}


@dataclass
class CopyConfig:
    """Copy trading configuration."""
    max_allocation_pct: float = 0.25
    min_allocation_usd: float = 100.0
    max_concurrent_copies: int = 10
    default_stop_loss_pct: float = 0.20
    copy_delay_seconds: int = 0
    allow_partial_copy: bool = True


@dataclass
class LeaderboardConfig:
    """Leaderboard configuration."""
    update_interval_hours: int = 1
    max_entries: int = 100
    min_trades: int = 10
    min_history_days: int = 30


@dataclass
class FeedConfig:
    """Social feed configuration."""
    max_post_length: int = 2000
    max_posts_per_day: int = 20
    max_comments_per_post: int = 100
    trending_window_hours: int = 24
    trending_min_interactions: int = 5


@dataclass
class SocialConfig:
    """Top-level social trading configuration."""
    copy: CopyConfig = field(default_factory=CopyConfig)
    leaderboard: LeaderboardConfig = field(default_factory=LeaderboardConfig)
    feed: FeedConfig = field(default_factory=FeedConfig)
    max_followers: int = 10000
    max_following: int = 500
    max_strategies_per_user: int = 10


DEFAULT_SOCIAL_CONFIG = SocialConfig()
