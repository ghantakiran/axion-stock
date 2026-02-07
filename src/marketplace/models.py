"""Data models for Strategy Marketplace."""

from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from typing import Optional, Any
import uuid
import re

from src.marketplace.config import (
    StrategyCategory,
    RiskLevel,
    TradingStyle,
    TimeHorizon,
    PricingModel,
    SubscriptionStatus,
    SubscriptionType,
)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slugify(text: str) -> str:
    """Convert text to URL-safe slug."""
    slug = text.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    return slug[:100]


@dataclass
class Strategy:
    """A marketplace trading strategy."""

    creator_id: str
    name: str
    category: StrategyCategory
    risk_level: RiskLevel
    strategy_id: str = field(default_factory=_new_id)
    slug: str = ""
    description: str = ""
    short_description: str = ""
    asset_classes: list[str] = field(default_factory=lambda: ["stocks"])
    trading_style: Optional[TradingStyle] = None
    time_horizon: Optional[TimeHorizon] = None
    min_capital: float = 1000.0
    max_positions: int = 10

    # Pricing
    pricing_model: PricingModel = PricingModel.FREE
    monthly_price: float = 0.0
    performance_fee_pct: float = 0.0

    # Status
    is_published: bool = False
    is_featured: bool = False
    is_verified: bool = False

    # Stats (updated by system)
    subscriber_count: int = 0
    avg_rating: float = 0.0
    review_count: int = 0
    total_return_pct: float = 0.0

    # Timestamps
    created_at: datetime = field(default_factory=_now)
    published_at: Optional[datetime] = None

    def __post_init__(self):
        if not self.slug:
            self.slug = _slugify(self.name)

    def publish(self) -> None:
        """Publish the strategy."""
        self.is_published = True
        self.published_at = _now()

    def unpublish(self) -> None:
        """Unpublish the strategy."""
        self.is_published = False

    def update_stats(
        self,
        subscriber_count: Optional[int] = None,
        avg_rating: Optional[float] = None,
        review_count: Optional[int] = None,
        total_return_pct: Optional[float] = None,
    ) -> None:
        """Update strategy statistics."""
        if subscriber_count is not None:
            self.subscriber_count = subscriber_count
        if avg_rating is not None:
            self.avg_rating = avg_rating
        if review_count is not None:
            self.review_count = review_count
        if total_return_pct is not None:
            self.total_return_pct = total_return_pct

    def get_monthly_cost(self) -> float:
        """Get fixed monthly cost."""
        if self.pricing_model in [PricingModel.SUBSCRIPTION, PricingModel.HYBRID]:
            return self.monthly_price
        return 0.0

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "creator_id": self.creator_id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "short_description": self.short_description,
            "category": self.category.value,
            "risk_level": self.risk_level.value,
            "asset_classes": self.asset_classes,
            "trading_style": self.trading_style.value if self.trading_style else None,
            "time_horizon": self.time_horizon.value if self.time_horizon else None,
            "min_capital": self.min_capital,
            "max_positions": self.max_positions,
            "pricing_model": self.pricing_model.value,
            "monthly_price": self.monthly_price,
            "performance_fee_pct": self.performance_fee_pct,
            "is_published": self.is_published,
            "is_featured": self.is_featured,
            "is_verified": self.is_verified,
            "subscriber_count": self.subscriber_count,
            "avg_rating": self.avg_rating,
            "review_count": self.review_count,
            "total_return_pct": self.total_return_pct,
            "created_at": self.created_at.isoformat(),
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }


@dataclass
class StrategyVersion:
    """A version of a strategy's parameters."""

    strategy_id: str
    version: str
    change_notes: str = ""
    parameters: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "version": self.version,
            "change_notes": self.change_notes,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class Subscription:
    """A subscription to a strategy."""

    strategy_id: str
    subscriber_id: str
    subscription_id: str = field(default_factory=_new_id)
    subscription_type: SubscriptionType = SubscriptionType.SIGNALS
    auto_trade_enabled: bool = False
    position_size_pct: float = 100.0
    max_position_value: Optional[float] = None
    risk_multiplier: float = 1.0
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    started_at: datetime = field(default_factory=_now)
    expires_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancel_reason: Optional[str] = None
    total_paid: float = 0.0

    def is_active(self) -> bool:
        """Check if subscription is active."""
        if self.status != SubscriptionStatus.ACTIVE:
            return False
        if self.expires_at and _now() > self.expires_at:
            return False
        return True

    def cancel(self, reason: Optional[str] = None) -> None:
        """Cancel the subscription."""
        self.status = SubscriptionStatus.CANCELLED
        self.cancelled_at = _now()
        self.cancel_reason = reason

    def pause(self) -> None:
        """Pause the subscription."""
        self.status = SubscriptionStatus.PAUSED

    def resume(self) -> None:
        """Resume the subscription."""
        self.status = SubscriptionStatus.ACTIVE

    def to_dict(self) -> dict:
        return {
            "subscription_id": self.subscription_id,
            "strategy_id": self.strategy_id,
            "subscriber_id": self.subscriber_id,
            "subscription_type": self.subscription_type.value,
            "auto_trade_enabled": self.auto_trade_enabled,
            "position_size_pct": self.position_size_pct,
            "risk_multiplier": self.risk_multiplier,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "total_paid": self.total_paid,
        }


@dataclass
class PerformanceSnapshot:
    """Daily performance snapshot for a strategy."""

    strategy_id: str
    snapshot_date: date
    daily_return_pct: float = 0.0
    cumulative_return_pct: float = 0.0
    benchmark_return_pct: float = 0.0
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    max_drawdown_pct: float = 0.0
    current_drawdown_pct: float = 0.0
    volatility_pct: Optional[float] = None
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    avg_win_pct: Optional[float] = None
    avg_loss_pct: Optional[float] = None
    trade_count: int = 0
    open_positions: int = 0
    portfolio_value: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "date": self.snapshot_date.isoformat(),
            "daily_return_pct": self.daily_return_pct,
            "cumulative_return_pct": self.cumulative_return_pct,
            "benchmark_return_pct": self.benchmark_return_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "max_drawdown_pct": self.max_drawdown_pct,
            "current_drawdown_pct": self.current_drawdown_pct,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "trade_count": self.trade_count,
        }


@dataclass
class Review:
    """A user review of a strategy."""

    strategy_id: str
    reviewer_id: str
    rating: int  # 1-5
    review_id: str = field(default_factory=_new_id)
    title: str = ""
    content: str = ""
    is_verified_subscriber: bool = False
    subscription_days: Optional[int] = None
    subscriber_return_pct: Optional[float] = None
    is_approved: bool = True
    is_featured: bool = False
    creator_response: Optional[str] = None
    responded_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=_now)

    def __post_init__(self):
        if self.rating < 1:
            self.rating = 1
        elif self.rating > 5:
            self.rating = 5

    def respond(self, response: str) -> None:
        """Add creator response."""
        self.creator_response = response
        self.responded_at = _now()

    def to_dict(self) -> dict:
        return {
            "review_id": self.review_id,
            "strategy_id": self.strategy_id,
            "reviewer_id": self.reviewer_id,
            "rating": self.rating,
            "title": self.title,
            "content": self.content,
            "is_verified_subscriber": self.is_verified_subscriber,
            "subscription_days": self.subscription_days,
            "subscriber_return_pct": self.subscriber_return_pct,
            "is_featured": self.is_featured,
            "creator_response": self.creator_response,
            "responded_at": self.responded_at.isoformat() if self.responded_at else None,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class CreatorStats:
    """Statistics for a strategy creator."""

    creator_id: str
    total_strategies: int = 0
    published_strategies: int = 0
    total_subscribers: int = 0
    total_revenue: float = 0.0
    avg_rating: float = 0.0
    total_reviews: int = 0
    best_strategy_return_pct: float = 0.0
    avg_strategy_return_pct: float = 0.0

    def to_dict(self) -> dict:
        return {
            "creator_id": self.creator_id,
            "total_strategies": self.total_strategies,
            "published_strategies": self.published_strategies,
            "total_subscribers": self.total_subscribers,
            "total_revenue": self.total_revenue,
            "avg_rating": self.avg_rating,
            "total_reviews": self.total_reviews,
            "best_strategy_return_pct": self.best_strategy_return_pct,
            "avg_strategy_return_pct": self.avg_strategy_return_pct,
        }


@dataclass
class LeaderboardEntry:
    """Entry in the strategy leaderboard."""

    rank: int
    strategy: Strategy
    performance: PerformanceSnapshot
    score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "rank": self.rank,
            "strategy": self.strategy.to_dict(),
            "performance": self.performance.to_dict(),
            "score": self.score,
        }
