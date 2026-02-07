"""Strategy management for marketplace."""

from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict

from src.marketplace.config import (
    StrategyCategory,
    RiskLevel,
    PricingModel,
    TradingStyle,
    TimeHorizon,
    MarketplaceConfig,
    DEFAULT_MARKETPLACE_CONFIG,
)
from src.marketplace.models import Strategy, StrategyVersion, CreatorStats


class StrategyManager:
    """Manages marketplace strategies."""

    def __init__(self, config: Optional[MarketplaceConfig] = None):
        self.config = config or DEFAULT_MARKETPLACE_CONFIG
        self._strategies: dict[str, Strategy] = {}
        self._by_creator: dict[str, list[str]] = defaultdict(list)
        self._by_slug: dict[str, str] = {}
        self._versions: dict[str, list[StrategyVersion]] = defaultdict(list)

    def create_strategy(
        self,
        creator_id: str,
        name: str,
        category: StrategyCategory,
        risk_level: RiskLevel,
        description: str = "",
        short_description: str = "",
        asset_classes: Optional[list[str]] = None,
        trading_style: Optional[TradingStyle] = None,
        time_horizon: Optional[TimeHorizon] = None,
        min_capital: float = 1000.0,
        max_positions: int = 10,
        pricing_model: PricingModel = PricingModel.FREE,
        monthly_price: float = 0.0,
        performance_fee_pct: float = 0.0,
    ) -> Strategy:
        """Create a new strategy."""
        # Check creator limit
        creator_strategies = self._by_creator.get(creator_id, [])
        if len(creator_strategies) >= self.config.max_strategies_per_creator:
            raise ValueError(f"Max {self.config.max_strategies_per_creator} strategies per creator")

        # Validate pricing
        if pricing_model in [PricingModel.SUBSCRIPTION, PricingModel.HYBRID]:
            if monthly_price < self.config.min_monthly_price:
                raise ValueError(f"Min monthly price: ${self.config.min_monthly_price}")
            if monthly_price > self.config.max_monthly_price:
                raise ValueError(f"Max monthly price: ${self.config.max_monthly_price}")

        if pricing_model in [PricingModel.PERFORMANCE, PricingModel.HYBRID]:
            if performance_fee_pct < self.config.min_performance_fee_pct:
                raise ValueError(f"Min performance fee: {self.config.min_performance_fee_pct}%")
            if performance_fee_pct > self.config.max_performance_fee_pct:
                raise ValueError(f"Max performance fee: {self.config.max_performance_fee_pct}%")

        strategy = Strategy(
            creator_id=creator_id,
            name=name,
            category=category,
            risk_level=risk_level,
            description=description,
            short_description=short_description or description[:200],
            asset_classes=asset_classes or ["stocks"],
            trading_style=trading_style,
            time_horizon=time_horizon,
            min_capital=min_capital,
            max_positions=min(max_positions, self.config.max_positions_per_strategy),
            pricing_model=pricing_model,
            monthly_price=monthly_price,
            performance_fee_pct=performance_fee_pct,
        )

        # Ensure unique slug
        base_slug = strategy.slug
        counter = 1
        while strategy.slug in self._by_slug:
            strategy.slug = f"{base_slug}-{counter}"
            counter += 1

        # Store
        self._strategies[strategy.strategy_id] = strategy
        self._by_creator[creator_id].append(strategy.strategy_id)
        self._by_slug[strategy.slug] = strategy.strategy_id

        # Create initial version
        self._versions[strategy.strategy_id].append(
            StrategyVersion(
                strategy_id=strategy.strategy_id,
                version="1.0.0",
                change_notes="Initial version",
            )
        )

        return strategy

    def get_strategy(self, strategy_id: str) -> Optional[Strategy]:
        """Get strategy by ID."""
        return self._strategies.get(strategy_id)

    def get_strategy_by_slug(self, slug: str) -> Optional[Strategy]:
        """Get strategy by slug."""
        strategy_id = self._by_slug.get(slug)
        if strategy_id:
            return self._strategies.get(strategy_id)
        return None

    def get_creator_strategies(self, creator_id: str) -> list[Strategy]:
        """Get all strategies for a creator."""
        strategy_ids = self._by_creator.get(creator_id, [])
        return [self._strategies[sid] for sid in strategy_ids if sid in self._strategies]

    def update_strategy(
        self,
        strategy_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        short_description: Optional[str] = None,
        min_capital: Optional[float] = None,
        max_positions: Optional[int] = None,
        monthly_price: Optional[float] = None,
        performance_fee_pct: Optional[float] = None,
    ) -> Optional[Strategy]:
        """Update strategy details."""
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            return None

        if name:
            strategy.name = name
        if description:
            strategy.description = description
        if short_description:
            strategy.short_description = short_description
        if min_capital is not None:
            strategy.min_capital = min_capital
        if max_positions is not None:
            strategy.max_positions = min(max_positions, self.config.max_positions_per_strategy)
        if monthly_price is not None:
            strategy.monthly_price = monthly_price
        if performance_fee_pct is not None:
            strategy.performance_fee_pct = performance_fee_pct

        return strategy

    def publish_strategy(self, strategy_id: str) -> bool:
        """Publish a strategy."""
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            return False

        strategy.publish()
        return True

    def unpublish_strategy(self, strategy_id: str) -> bool:
        """Unpublish a strategy."""
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            return False

        strategy.unpublish()
        return True

    def delete_strategy(self, strategy_id: str) -> bool:
        """Delete a strategy."""
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            return False

        # Can't delete if has subscribers
        if strategy.subscriber_count > 0:
            raise ValueError("Cannot delete strategy with active subscribers")

        # Remove from all indexes
        del self._strategies[strategy_id]
        if strategy.slug in self._by_slug:
            del self._by_slug[strategy.slug]

        creator_strategies = self._by_creator.get(strategy.creator_id, [])
        if strategy_id in creator_strategies:
            creator_strategies.remove(strategy_id)

        return True

    def add_version(
        self,
        strategy_id: str,
        version: str,
        change_notes: str,
        parameters: Optional[dict] = None,
    ) -> Optional[StrategyVersion]:
        """Add a new version to a strategy."""
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            return None

        new_version = StrategyVersion(
            strategy_id=strategy_id,
            version=version,
            change_notes=change_notes,
            parameters=parameters or {},
        )

        self._versions[strategy_id].append(new_version)
        return new_version

    def get_versions(self, strategy_id: str) -> list[StrategyVersion]:
        """Get all versions for a strategy."""
        return self._versions.get(strategy_id, [])

    def get_latest_version(self, strategy_id: str) -> Optional[StrategyVersion]:
        """Get the latest version of a strategy."""
        versions = self._versions.get(strategy_id, [])
        return versions[-1] if versions else None

    def feature_strategy(self, strategy_id: str) -> bool:
        """Mark strategy as featured."""
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            return False

        strategy.is_featured = True
        return True

    def verify_strategy(self, strategy_id: str) -> bool:
        """Mark strategy as verified."""
        strategy = self._strategies.get(strategy_id)
        if not strategy:
            return False

        strategy.is_verified = True
        return True

    def get_published_strategies(self) -> list[Strategy]:
        """Get all published strategies."""
        return [s for s in self._strategies.values() if s.is_published]

    def get_featured_strategies(self) -> list[Strategy]:
        """Get featured strategies."""
        return [s for s in self._strategies.values() if s.is_published and s.is_featured]

    def get_creator_stats(self, creator_id: str) -> CreatorStats:
        """Get statistics for a creator."""
        strategies = self.get_creator_strategies(creator_id)

        stats = CreatorStats(creator_id=creator_id)
        stats.total_strategies = len(strategies)
        stats.published_strategies = sum(1 for s in strategies if s.is_published)
        stats.total_subscribers = sum(s.subscriber_count for s in strategies)

        ratings = [s.avg_rating for s in strategies if s.review_count > 0]
        if ratings:
            stats.avg_rating = sum(ratings) / len(ratings)

        stats.total_reviews = sum(s.review_count for s in strategies)

        returns = [s.total_return_pct for s in strategies if s.total_return_pct != 0]
        if returns:
            stats.best_strategy_return_pct = max(returns)
            stats.avg_strategy_return_pct = sum(returns) / len(returns)

        return stats

    def get_stats(self) -> dict:
        """Get marketplace statistics."""
        published = self.get_published_strategies()

        by_category = defaultdict(int)
        by_risk = defaultdict(int)
        by_pricing = defaultdict(int)

        for strategy in published:
            by_category[strategy.category.value] += 1
            by_risk[strategy.risk_level.value] += 1
            by_pricing[strategy.pricing_model.value] += 1

        return {
            "total_strategies": len(self._strategies),
            "published_strategies": len(published),
            "total_creators": len(self._by_creator),
            "by_category": dict(by_category),
            "by_risk_level": dict(by_risk),
            "by_pricing_model": dict(by_pricing),
        }
