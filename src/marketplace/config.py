"""Configuration for Strategy Marketplace."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class StrategyCategory(Enum):
    """Strategy categories."""
    MOMENTUM = "momentum"
    VALUE = "value"
    GROWTH = "growth"
    DIVIDEND = "dividend"
    SWING = "swing"
    DAY_TRADING = "day_trading"
    OPTIONS = "options"
    SECTOR_ROTATION = "sector_rotation"
    QUANTITATIVE = "quantitative"
    TECHNICAL = "technical"
    FUNDAMENTAL = "fundamental"
    HYBRID = "hybrid"


class RiskLevel(Enum):
    """Strategy risk levels."""
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    VERY_AGGRESSIVE = "very_aggressive"


class TradingStyle(Enum):
    """Trading styles."""
    LONG_ONLY = "long_only"
    LONG_SHORT = "long_short"
    MARKET_NEUTRAL = "market_neutral"
    TREND_FOLLOWING = "trend_following"
    MEAN_REVERSION = "mean_reversion"
    EVENT_DRIVEN = "event_driven"


class TimeHorizon(Enum):
    """Investment time horizons."""
    INTRADAY = "intraday"
    SHORT_TERM = "short_term"  # days to weeks
    MEDIUM_TERM = "medium_term"  # weeks to months
    LONG_TERM = "long_term"  # months to years


class PricingModel(Enum):
    """Strategy pricing models."""
    FREE = "free"
    SUBSCRIPTION = "subscription"
    PERFORMANCE = "performance"
    HYBRID = "hybrid"


class SubscriptionStatus(Enum):
    """Subscription statuses."""
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    TRIAL = "trial"


class SubscriptionType(Enum):
    """Subscription types."""
    SIGNALS = "signals"  # Receive signals only
    AUTO_TRADE = "auto_trade"  # Automatic execution


class PayoutStatus(Enum):
    """Payout statuses."""
    PENDING = "pending"
    PROCESSING = "processing"
    PAID = "paid"
    FAILED = "failed"


@dataclass
class MarketplaceConfig:
    """Marketplace configuration."""

    # Revenue split
    platform_fee_pct: float = 20.0  # Platform takes 20%
    creator_share_pct: float = 80.0  # Creator gets 80%

    # Pricing limits
    min_monthly_price: float = 4.99
    max_monthly_price: float = 499.99
    min_performance_fee_pct: float = 5.0
    max_performance_fee_pct: float = 30.0

    # Strategy limits
    max_strategies_per_creator: int = 10
    max_positions_per_strategy: int = 50
    min_backtest_days: int = 180
    min_live_days_for_verification: int = 90

    # Subscription limits
    max_subscriptions_per_user: int = 20
    trial_days: int = 7

    # Review requirements
    min_subscription_days_for_review: int = 14
    min_review_length: int = 50
    max_review_length: int = 2000

    # Payout settings
    min_payout_amount: float = 50.0
    payout_frequency_days: int = 30

    # Leaderboard settings
    min_days_for_leaderboard: int = 30
    leaderboard_size: int = 100


DEFAULT_MARKETPLACE_CONFIG = MarketplaceConfig()


# Category metadata
CATEGORY_INFO: dict[StrategyCategory, dict] = {
    StrategyCategory.MOMENTUM: {
        "name": "Momentum",
        "description": "Strategies that buy winners and sell losers",
        "icon": "trending_up",
    },
    StrategyCategory.VALUE: {
        "name": "Value",
        "description": "Strategies focused on undervalued stocks",
        "icon": "savings",
    },
    StrategyCategory.GROWTH: {
        "name": "Growth",
        "description": "Strategies targeting high-growth companies",
        "icon": "show_chart",
    },
    StrategyCategory.DIVIDEND: {
        "name": "Dividend",
        "description": "Income-focused dividend strategies",
        "icon": "payments",
    },
    StrategyCategory.SWING: {
        "name": "Swing Trading",
        "description": "Multi-day to multi-week trades",
        "icon": "swap_vert",
    },
    StrategyCategory.DAY_TRADING: {
        "name": "Day Trading",
        "description": "Intraday strategies",
        "icon": "schedule",
    },
    StrategyCategory.OPTIONS: {
        "name": "Options",
        "description": "Options-based strategies",
        "icon": "toll",
    },
    StrategyCategory.SECTOR_ROTATION: {
        "name": "Sector Rotation",
        "description": "Rotating between sectors based on conditions",
        "icon": "donut_large",
    },
    StrategyCategory.QUANTITATIVE: {
        "name": "Quantitative",
        "description": "Data-driven algorithmic strategies",
        "icon": "analytics",
    },
    StrategyCategory.TECHNICAL: {
        "name": "Technical Analysis",
        "description": "Chart pattern and indicator-based strategies",
        "icon": "candlestick_chart",
    },
    StrategyCategory.FUNDAMENTAL: {
        "name": "Fundamental Analysis",
        "description": "Financial statement-based strategies",
        "icon": "account_balance",
    },
    StrategyCategory.HYBRID: {
        "name": "Hybrid",
        "description": "Combination of multiple approaches",
        "icon": "layers",
    },
}
