"""Strategy publishing and management.

Strategy CRUD, publishing lifecycle, and performance tracking.
"""

import logging
from typing import Optional

from src.social.config import (
    StrategyStatus,
    StrategyCategory,
    SocialConfig,
    DEFAULT_SOCIAL_CONFIG,
)
from src.social.models import (
    Strategy,
    StrategyPerformance,
    PerformanceStats,
    _utc_now,
)

logger = logging.getLogger(__name__)


class StrategyManager:
    """Manages strategy publishing, versioning, and performance tracking."""

    def __init__(self, config: Optional[SocialConfig] = None) -> None:
        self.config = config or DEFAULT_SOCIAL_CONFIG
        self._strategies: dict[str, Strategy] = {}
        self._performance: dict[str, list[StrategyPerformance]] = {}

    def create_strategy(
        self,
        user_id: str,
        name: str,
        description: str = "",
        category: StrategyCategory = StrategyCategory.EQUITY_LONG,
        tags: Optional[list[str]] = None,
        asset_universe: Optional[list[str]] = None,
        min_capital: float = 1000.0,
        risk_level: int = 3,
    ) -> Strategy:
        """Create a new strategy (as draft).

        Args:
            user_id: Owner user ID.
            name: Strategy name.
            description: Strategy description.
            category: Strategy category.
            tags: Searchable tags.
            asset_universe: List of symbols.
            min_capital: Minimum capital to copy.
            risk_level: Risk level 1-5.

        Returns:
            Created Strategy.
        """
        user_strategies = [
            s for s in self._strategies.values()
            if s.user_id == user_id
        ]
        if len(user_strategies) >= self.config.max_strategies_per_user:
            raise ValueError(
                f"User has reached max strategies ({self.config.max_strategies_per_user})"
            )

        strategy = Strategy(
            user_id=user_id,
            name=name,
            description=description,
            category=category,
            tags=tags or [],
            asset_universe=asset_universe or [],
            min_capital=min_capital,
            risk_level=max(1, min(5, risk_level)),
        )

        self._strategies[strategy.strategy_id] = strategy
        self._performance[strategy.strategy_id] = []
        logger.info(
            "Created strategy '%s' for user %s", name, user_id,
        )
        return strategy

    def get_strategy(self, strategy_id: str) -> Optional[Strategy]:
        """Get a strategy by ID."""
        return self._strategies.get(strategy_id)

    def publish_strategy(self, strategy_id: str) -> Optional[Strategy]:
        """Publish a draft strategy.

        Args:
            strategy_id: Strategy to publish.

        Returns:
            Published strategy, or None if not found.
        """
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            return None

        strategy.publish()
        logger.info("Published strategy %s: %s", strategy_id, strategy.name)
        return strategy

    def archive_strategy(self, strategy_id: str) -> Optional[Strategy]:
        """Archive a strategy.

        Args:
            strategy_id: Strategy to archive.

        Returns:
            Archived strategy, or None if not found.
        """
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            return None

        strategy.archive()
        return strategy

    def update_strategy(
        self,
        strategy_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        risk_level: Optional[int] = None,
    ) -> Optional[Strategy]:
        """Update a strategy (creates a new version).

        Args:
            strategy_id: Strategy to update.
            name: New name.
            description: New description.
            tags: New tags.
            risk_level: New risk level.

        Returns:
            Updated strategy, or None if not found.
        """
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            return None

        if name is not None:
            strategy.name = name
        if description is not None:
            strategy.description = description
        if tags is not None:
            strategy.tags = tags
        if risk_level is not None:
            strategy.risk_level = max(1, min(5, risk_level))

        strategy.increment_version()
        return strategy

    def record_performance(
        self,
        strategy_id: str,
        daily_return: float,
        nav: float,
        num_positions: int = 0,
    ) -> Optional[StrategyPerformance]:
        """Record a daily performance snapshot.

        Args:
            strategy_id: Strategy ID.
            daily_return: Daily return.
            nav: Current NAV.
            num_positions: Number of open positions.

        Returns:
            Performance record, or None if strategy not found.
        """
        if strategy_id not in self._strategies:
            return None

        history = self._performance.get(strategy_id, [])

        # Compute cumulative return from NAV
        cumulative = (nav / 100.0) - 1.0 if nav > 0 else 0.0

        # Compute drawdown
        peak_nav = max((p.nav for p in history), default=100.0)
        peak_nav = max(peak_nav, nav)
        drawdown = (nav - peak_nav) / peak_nav if peak_nav > 0 else 0.0

        perf = StrategyPerformance(
            strategy_id=strategy_id,
            daily_return=daily_return,
            cumulative_return=cumulative,
            nav=nav,
            drawdown=drawdown,
            num_positions=num_positions,
        )

        history.append(perf)
        self._performance[strategy_id] = history
        return perf

    def get_performance(
        self,
        strategy_id: str,
        limit: int = 252,
    ) -> list[StrategyPerformance]:
        """Get performance history for a strategy.

        Args:
            strategy_id: Strategy ID.
            limit: Max records to return.

        Returns:
            List of performance snapshots.
        """
        history = self._performance.get(strategy_id, [])
        return history[-limit:]

    def update_strategy_stats(
        self,
        strategy_id: str,
        stats: PerformanceStats,
    ) -> Optional[Strategy]:
        """Update strategy aggregate statistics.

        Args:
            strategy_id: Strategy ID.
            stats: Performance stats.

        Returns:
            Updated strategy, or None if not found.
        """
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            return None

        strategy.stats = stats
        strategy.updated_at = _utc_now()
        return strategy

    def search_strategies(
        self,
        category: Optional[StrategyCategory] = None,
        tags: Optional[list[str]] = None,
        min_sharpe: Optional[float] = None,
        max_risk_level: Optional[int] = None,
        limit: int = 20,
    ) -> list[Strategy]:
        """Search published strategies.

        Args:
            category: Filter by category.
            tags: Filter by tags (any match).
            min_sharpe: Minimum Sharpe ratio.
            max_risk_level: Maximum risk level.
            limit: Max results.

        Returns:
            List of matching strategies.
        """
        results = [
            s for s in self._strategies.values()
            if s.status == StrategyStatus.PUBLISHED
        ]

        if category:
            results = [s for s in results if s.category == category]

        if tags:
            tag_set = set(tags)
            results = [
                s for s in results
                if tag_set & set(s.tags)
            ]

        if min_sharpe is not None:
            results = [
                s for s in results
                if s.stats.sharpe_ratio >= min_sharpe
            ]

        if max_risk_level is not None:
            results = [
                s for s in results
                if s.risk_level <= max_risk_level
            ]

        # Sort by copiers count (most popular first)
        results.sort(key=lambda s: s.copiers_count, reverse=True)
        return results[:limit]

    def get_user_strategies(self, user_id: str) -> list[Strategy]:
        """Get all strategies for a user.

        Args:
            user_id: User ID.

        Returns:
            List of strategies.
        """
        return [
            s for s in self._strategies.values()
            if s.user_id == user_id
        ]
