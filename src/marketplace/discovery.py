"""Strategy discovery for marketplace."""

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
from src.marketplace.models import Strategy, Review


class StrategyDiscovery:
    """Handles strategy discovery, search, and recommendations."""

    def __init__(self, config: Optional[MarketplaceConfig] = None):
        self.config = config or DEFAULT_MARKETPLACE_CONFIG
        self._reviews: dict[str, list[Review]] = defaultdict(list)

    def search(
        self,
        strategies: list[Strategy],
        query: Optional[str] = None,
        category: Optional[StrategyCategory] = None,
        risk_level: Optional[RiskLevel] = None,
        pricing_model: Optional[PricingModel] = None,
        trading_style: Optional[TradingStyle] = None,
        time_horizon: Optional[TimeHorizon] = None,
        min_return_pct: Optional[float] = None,
        max_drawdown_pct: Optional[float] = None,
        min_rating: Optional[float] = None,
        is_free: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        sort_by: str = "subscribers",
        limit: int = 50,
    ) -> list[Strategy]:
        """Search and filter strategies."""
        results = []

        for strategy in strategies:
            # Only include published strategies
            if not strategy.is_published:
                continue

            # Text search
            if query:
                query_lower = query.lower()
                if not any([
                    query_lower in strategy.name.lower(),
                    query_lower in strategy.description.lower(),
                    query_lower in strategy.short_description.lower(),
                ]):
                    continue

            # Category filter
            if category and strategy.category != category:
                continue

            # Risk level filter
            if risk_level and strategy.risk_level != risk_level:
                continue

            # Pricing model filter
            if pricing_model and strategy.pricing_model != pricing_model:
                continue

            # Trading style filter
            if trading_style and strategy.trading_style != trading_style:
                continue

            # Time horizon filter
            if time_horizon and strategy.time_horizon != time_horizon:
                continue

            # Return filter
            if min_return_pct is not None and strategy.total_return_pct < min_return_pct:
                continue

            # Rating filter
            if min_rating is not None and strategy.avg_rating < min_rating:
                continue

            # Free filter
            if is_free is not None:
                is_strategy_free = strategy.pricing_model == PricingModel.FREE
                if is_free != is_strategy_free:
                    continue

            # Verified filter
            if is_verified is not None and strategy.is_verified != is_verified:
                continue

            results.append(strategy)

        # Sort
        if sort_by == "subscribers":
            results.sort(key=lambda s: s.subscriber_count, reverse=True)
        elif sort_by == "rating":
            results.sort(key=lambda s: s.avg_rating, reverse=True)
        elif sort_by == "return":
            results.sort(key=lambda s: s.total_return_pct, reverse=True)
        elif sort_by == "newest":
            results.sort(key=lambda s: s.created_at, reverse=True)
        elif sort_by == "price_low":
            results.sort(key=lambda s: s.monthly_price)
        elif sort_by == "price_high":
            results.sort(key=lambda s: s.monthly_price, reverse=True)

        return results[:limit]

    def get_similar_strategies(
        self,
        strategy: Strategy,
        all_strategies: list[Strategy],
        limit: int = 5,
    ) -> list[Strategy]:
        """Get similar strategies based on category and style."""
        similar = []

        for other in all_strategies:
            if other.strategy_id == strategy.strategy_id:
                continue
            if not other.is_published:
                continue

            score = 0

            # Same category
            if other.category == strategy.category:
                score += 3

            # Same risk level
            if other.risk_level == strategy.risk_level:
                score += 2

            # Same trading style
            if other.trading_style == strategy.trading_style:
                score += 2

            # Same time horizon
            if other.time_horizon == strategy.time_horizon:
                score += 1

            # Overlapping asset classes
            overlap = set(other.asset_classes) & set(strategy.asset_classes)
            score += len(overlap)

            if score > 0:
                similar.append((score, other))

        similar.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in similar[:limit]]

    def get_trending(
        self,
        strategies: list[Strategy],
        days: int = 7,
        limit: int = 10,
    ) -> list[Strategy]:
        """Get trending strategies (recent subscriber growth)."""
        # For now, use subscriber count as proxy
        published = [s for s in strategies if s.is_published]
        published.sort(key=lambda s: s.subscriber_count, reverse=True)
        return published[:limit]

    def get_top_rated(
        self,
        strategies: list[Strategy],
        min_reviews: int = 5,
        limit: int = 10,
    ) -> list[Strategy]:
        """Get top rated strategies."""
        rated = [
            s for s in strategies
            if s.is_published and s.review_count >= min_reviews
        ]
        rated.sort(key=lambda s: s.avg_rating, reverse=True)
        return rated[:limit]

    def get_by_category(
        self,
        strategies: list[Strategy],
        category: StrategyCategory,
        limit: int = 20,
    ) -> list[Strategy]:
        """Get strategies in a category."""
        in_category = [
            s for s in strategies
            if s.is_published and s.category == category
        ]
        in_category.sort(key=lambda s: s.subscriber_count, reverse=True)
        return in_category[:limit]

    def add_review(
        self,
        strategy_id: str,
        reviewer_id: str,
        rating: int,
        title: str = "",
        content: str = "",
        is_verified_subscriber: bool = False,
        subscription_days: Optional[int] = None,
        subscriber_return_pct: Optional[float] = None,
    ) -> Review:
        """Add a review for a strategy."""
        # Validate content length
        if content and len(content) < self.config.min_review_length:
            raise ValueError(f"Review must be at least {self.config.min_review_length} characters")
        if content and len(content) > self.config.max_review_length:
            raise ValueError(f"Review must be at most {self.config.max_review_length} characters")

        # Check if verified subscriber meets minimum days
        if is_verified_subscriber:
            if subscription_days and subscription_days < self.config.min_subscription_days_for_review:
                is_verified_subscriber = False

        review = Review(
            strategy_id=strategy_id,
            reviewer_id=reviewer_id,
            rating=rating,
            title=title,
            content=content,
            is_verified_subscriber=is_verified_subscriber,
            subscription_days=subscription_days,
            subscriber_return_pct=subscriber_return_pct,
        )

        self._reviews[strategy_id].append(review)
        return review

    def get_reviews(
        self,
        strategy_id: str,
        verified_only: bool = False,
        sort_by: str = "newest",
        limit: int = 50,
    ) -> list[Review]:
        """Get reviews for a strategy."""
        reviews = self._reviews.get(strategy_id, [])

        if verified_only:
            reviews = [r for r in reviews if r.is_verified_subscriber]

        # Filter approved only
        reviews = [r for r in reviews if r.is_approved]

        # Sort
        if sort_by == "newest":
            reviews.sort(key=lambda r: r.created_at, reverse=True)
        elif sort_by == "oldest":
            reviews.sort(key=lambda r: r.created_at)
        elif sort_by == "rating_high":
            reviews.sort(key=lambda r: r.rating, reverse=True)
        elif sort_by == "rating_low":
            reviews.sort(key=lambda r: r.rating)
        elif sort_by == "helpful":
            # Sort by verified + rating
            reviews.sort(key=lambda r: (r.is_verified_subscriber, r.rating), reverse=True)

        return reviews[:limit]

    def get_average_rating(self, strategy_id: str) -> tuple[float, int]:
        """Get average rating and review count for a strategy."""
        reviews = [r for r in self._reviews.get(strategy_id, []) if r.is_approved]

        if not reviews:
            return 0.0, 0

        avg = sum(r.rating for r in reviews) / len(reviews)
        return round(avg, 2), len(reviews)

    def get_rating_distribution(self, strategy_id: str) -> dict[int, int]:
        """Get rating distribution for a strategy."""
        reviews = [r for r in self._reviews.get(strategy_id, []) if r.is_approved]

        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for review in reviews:
            distribution[review.rating] += 1

        return distribution

    def respond_to_review(
        self,
        review_id: str,
        strategy_id: str,
        response: str,
    ) -> bool:
        """Add creator response to a review."""
        reviews = self._reviews.get(strategy_id, [])

        for review in reviews:
            if review.review_id == review_id:
                review.respond(response)
                return True

        return False

    def get_category_stats(self, strategies: list[Strategy]) -> dict[str, dict]:
        """Get statistics per category."""
        stats: dict[str, dict] = {}

        for category in StrategyCategory:
            in_category = [s for s in strategies if s.is_published and s.category == category]

            if not in_category:
                continue

            stats[category.value] = {
                "count": len(in_category),
                "total_subscribers": sum(s.subscriber_count for s in in_category),
                "avg_return": sum(s.total_return_pct for s in in_category) / len(in_category),
                "avg_rating": sum(s.avg_rating for s in in_category) / len(in_category),
            }

        return stats
