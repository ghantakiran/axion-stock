"""Social Trading data models.

Dataclasses for profiles, strategies, copy trading, leaderboards, and feed.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
import uuid

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
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


@dataclass
class PerformanceStats:
    """Trader/strategy performance statistics.

    Attributes:
        total_return: Cumulative return as fraction.
        annualized_return: Annualized return.
        sharpe_ratio: Sharpe ratio.
        max_drawdown: Maximum drawdown as negative fraction.
        win_rate: Fraction of profitable trades.
        profit_factor: Gross profit / gross loss.
        total_trades: Total number of trades.
        avg_trade_return: Average return per trade.
        volatility: Annualized volatility.
        calmar_ratio: Annualized return / max drawdown.
    """
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    avg_trade_return: float = 0.0
    volatility: float = 0.0
    calmar_ratio: float = 0.0

    @property
    def is_qualified_for_leaderboard(self) -> bool:
        """Check if stats meet leaderboard minimums."""
        from src.social.config import LEADERBOARD_MINIMUMS
        return self.total_trades >= LEADERBOARD_MINIMUMS["min_trades"]


@dataclass
class TraderProfile:
    """Public trader profile.

    Attributes:
        profile_id: Unique profile identifier.
        user_id: Platform user ID.
        display_name: Public display name.
        bio: Profile biography.
        trading_style: Primary trading style.
        visibility: Profile visibility level.
        badges: Earned badges.
        is_verified: Whether identity is verified.
        stats: Performance statistics.
        followers_count: Number of followers.
        following_count: Number of traders being followed.
        strategies_count: Number of published strategies.
        rating: Average community rating (1-5).
        rating_count: Number of ratings received.
        joined_at: Profile creation date.
        updated_at: Last update timestamp.
    """
    profile_id: str = field(default_factory=_new_id)
    user_id: str = ""
    display_name: str = ""
    bio: str = ""
    trading_style: TradingStyle = TradingStyle.SWING_TRADING
    visibility: ProfileVisibility = ProfileVisibility.PUBLIC
    badges: list[Badge] = field(default_factory=list)
    is_verified: bool = False
    stats: PerformanceStats = field(default_factory=PerformanceStats)
    followers_count: int = 0
    following_count: int = 0
    strategies_count: int = 0
    rating: float = 0.0
    rating_count: int = 0
    joined_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def add_badge(self, badge: Badge) -> None:
        """Add a badge if not already earned."""
        if badge not in self.badges:
            self.badges.append(badge)

    def update_rating(self, new_rating: float) -> None:
        """Update average rating with a new rating.

        Args:
            new_rating: New rating value (1-5).
        """
        new_rating = max(1.0, min(5.0, new_rating))
        total = self.rating * self.rating_count + new_rating
        self.rating_count += 1
        self.rating = total / self.rating_count


@dataclass
class Strategy:
    """Published trading strategy.

    Attributes:
        strategy_id: Unique strategy identifier.
        user_id: Owner user ID.
        name: Strategy name.
        description: Strategy description.
        category: Strategy category.
        status: Publication status.
        tags: Searchable tags.
        asset_universe: List of symbols or asset classes.
        stats: Performance statistics.
        copiers_count: Number of active copiers.
        min_capital: Minimum capital to copy.
        risk_level: Risk level 1-5.
        version: Strategy version number.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """
    strategy_id: str = field(default_factory=_new_id)
    user_id: str = ""
    name: str = ""
    description: str = ""
    category: StrategyCategory = StrategyCategory.EQUITY_LONG
    status: StrategyStatus = StrategyStatus.DRAFT
    tags: list[str] = field(default_factory=list)
    asset_universe: list[str] = field(default_factory=list)
    stats: PerformanceStats = field(default_factory=PerformanceStats)
    copiers_count: int = 0
    min_capital: float = 1000.0
    risk_level: int = 3
    version: int = 1
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def publish(self) -> None:
        """Publish the strategy."""
        self.status = StrategyStatus.PUBLISHED
        self.updated_at = _utc_now()

    def archive(self) -> None:
        """Archive the strategy."""
        self.status = StrategyStatus.ARCHIVED
        self.updated_at = _utc_now()

    def increment_version(self) -> None:
        """Bump the strategy version."""
        self.version += 1
        self.updated_at = _utc_now()


@dataclass
class StrategyPerformance:
    """Daily strategy performance snapshot.

    Attributes:
        strategy_id: Reference to strategy.
        date: Snapshot date.
        daily_return: Daily return.
        cumulative_return: Cumulative return from inception.
        nav: Net asset value (normalized to 100 at inception).
        drawdown: Current drawdown from peak.
        num_positions: Number of open positions.
    """
    strategy_id: str = ""
    date: datetime = field(default_factory=_utc_now)
    daily_return: float = 0.0
    cumulative_return: float = 0.0
    nav: float = 100.0
    drawdown: float = 0.0
    num_positions: int = 0


@dataclass
class CopyRelationship:
    """Copy trading relationship between a copier and a leader.

    Attributes:
        copy_id: Unique copy relationship ID.
        copier_user_id: User copying trades.
        leader_user_id: User being copied.
        strategy_id: Strategy being copied.
        status: Copy relationship status.
        mode: Allocation mode.
        allocation_amount: Fixed USD amount or percentage.
        max_loss_pct: Max loss before auto-stop.
        copy_delay_seconds: Delay before copying (for review).
        total_pnl: Total P&L from this copy relationship.
        total_trades_copied: Number of trades copied.
        started_at: When copying started.
        stopped_at: When copying stopped.
        updated_at: Last update.
    """
    copy_id: str = field(default_factory=_new_id)
    copier_user_id: str = ""
    leader_user_id: str = ""
    strategy_id: str = ""
    status: CopyStatus = CopyStatus.ACTIVE
    mode: CopyMode = CopyMode.FIXED_AMOUNT
    allocation_amount: float = 1000.0
    max_loss_pct: float = 0.20
    copy_delay_seconds: int = 0
    total_pnl: float = 0.0
    total_trades_copied: int = 0
    started_at: datetime = field(default_factory=_utc_now)
    stopped_at: Optional[datetime] = None
    updated_at: datetime = field(default_factory=_utc_now)

    def pause(self) -> None:
        """Pause copy trading."""
        self.status = CopyStatus.PAUSED
        self.updated_at = _utc_now()

    def resume(self) -> None:
        """Resume copy trading."""
        self.status = CopyStatus.ACTIVE
        self.updated_at = _utc_now()

    def stop(self) -> None:
        """Stop copy trading."""
        self.status = CopyStatus.STOPPED
        self.stopped_at = _utc_now()
        self.updated_at = _utc_now()

    def check_max_loss(self) -> bool:
        """Check if max loss has been hit.

        Returns:
            True if max loss exceeded.
        """
        if self.allocation_amount <= 0:
            return False
        loss_pct = -self.total_pnl / self.allocation_amount
        if loss_pct >= self.max_loss_pct:
            self.status = CopyStatus.MAX_LOSS_HIT
            self.stopped_at = _utc_now()
            self.updated_at = _utc_now()
            return True
        return False

    def record_trade(self, pnl: float) -> None:
        """Record a copied trade.

        Args:
            pnl: P&L from the trade.
        """
        self.total_trades_copied += 1
        self.total_pnl += pnl
        self.updated_at = _utc_now()


@dataclass
class LeaderboardEntry:
    """Single entry in a leaderboard.

    Attributes:
        rank: Current rank position.
        user_id: Trader user ID.
        display_name: Trader display name.
        metric_value: Value of the ranking metric.
        stats: Full performance stats.
        badges: Trader badges.
        followers_count: Number of followers.
        previous_rank: Rank in previous period (for trend).
    """
    rank: int = 0
    user_id: str = ""
    display_name: str = ""
    metric_value: float = 0.0
    stats: PerformanceStats = field(default_factory=PerformanceStats)
    badges: list[Badge] = field(default_factory=list)
    followers_count: int = 0
    previous_rank: Optional[int] = None

    @property
    def rank_change(self) -> Optional[int]:
        """Rank change from previous period (positive = moved up)."""
        if self.previous_rank is None:
            return None
        return self.previous_rank - self.rank


@dataclass
class Leaderboard:
    """Leaderboard with ranked entries.

    Attributes:
        metric: Ranking metric.
        period: Time period.
        entries: Ranked entries.
        updated_at: Last computation timestamp.
    """
    metric: LeaderboardMetric = LeaderboardMetric.TOTAL_RETURN
    period: LeaderboardPeriod = LeaderboardPeriod.THREE_MONTHS
    entries: list[LeaderboardEntry] = field(default_factory=list)
    updated_at: datetime = field(default_factory=_utc_now)

    @property
    def top_n(self) -> list[LeaderboardEntry]:
        """Return top 10 entries."""
        return self.entries[:10]


@dataclass
class SocialPost:
    """Social feed post.

    Attributes:
        post_id: Unique post identifier.
        user_id: Author user ID.
        display_name: Author display name.
        post_type: Type of post.
        content: Post text content.
        symbol: Related symbol (optional).
        target_price: Target price for trade ideas.
        stop_loss: Stop loss for trade ideas.
        direction: 'long' or 'short' for trade ideas.
        likes_count: Number of likes.
        comments_count: Number of comments.
        bookmarks_count: Number of bookmarks.
        is_trending: Whether post is trending.
        created_at: Creation timestamp.
    """
    post_id: str = field(default_factory=_new_id)
    user_id: str = ""
    display_name: str = ""
    post_type: PostType = PostType.COMMENTARY
    content: str = ""
    symbol: Optional[str] = None
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    direction: Optional[str] = None
    likes_count: int = 0
    comments_count: int = 0
    bookmarks_count: int = 0
    is_trending: bool = False
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class SocialInteraction:
    """Social interaction (like, comment, bookmark).

    Attributes:
        interaction_id: Unique interaction identifier.
        post_id: Reference to post.
        user_id: User performing the interaction.
        interaction_type: Type of interaction.
        comment_text: Comment text (for comments).
        created_at: Interaction timestamp.
    """
    interaction_id: str = field(default_factory=_new_id)
    post_id: str = ""
    user_id: str = ""
    interaction_type: InteractionType = InteractionType.LIKE
    comment_text: Optional[str] = None
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class FollowRelationship:
    """Follow relationship between users.

    Attributes:
        follower_id: User who is following.
        following_id: User being followed.
        created_at: When the follow started.
    """
    follower_id: str = ""
    following_id: str = ""
    created_at: datetime = field(default_factory=_utc_now)
