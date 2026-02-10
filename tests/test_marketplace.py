"""Tests for PRD-61: Strategy Marketplace."""

import pytest
from datetime import datetime, timezone, date, timedelta

from src.marketplace.config import (
    StrategyCategory,
    RiskLevel,
    TradingStyle,
    TimeHorizon,
    PricingModel,
    SubscriptionStatus,
    SubscriptionType,
    MarketplaceConfig,
    DEFAULT_MARKETPLACE_CONFIG,
    CATEGORY_INFO,
)
from src.marketplace.models import (
    Strategy,
    StrategyVersion,
    Subscription,
    PerformanceSnapshot,
    Review,
    CreatorStats,
    LeaderboardEntry,
)
from src.marketplace.strategies import StrategyManager
from src.marketplace.subscriptions import SubscriptionManager
from src.marketplace.performance import PerformanceTracker
from src.marketplace.discovery import StrategyDiscovery


class TestMarketplaceConfig:
    """Tests for marketplace configuration."""

    def test_strategy_categories(self):
        """Test strategy category enum."""
        assert StrategyCategory.MOMENTUM.value == "momentum"
        assert StrategyCategory.VALUE.value == "value"
        assert StrategyCategory.GROWTH.value == "growth"

    def test_risk_levels(self):
        """Test risk level enum."""
        assert RiskLevel.CONSERVATIVE.value == "conservative"
        assert RiskLevel.AGGRESSIVE.value == "aggressive"

    def test_pricing_models(self):
        """Test pricing model enum."""
        assert PricingModel.FREE.value == "free"
        assert PricingModel.SUBSCRIPTION.value == "subscription"
        assert PricingModel.PERFORMANCE.value == "performance"

    def test_default_config(self):
        """Test default configuration."""
        config = DEFAULT_MARKETPLACE_CONFIG
        assert config.platform_fee_pct == 20.0
        assert config.creator_share_pct == 80.0
        assert config.max_strategies_per_creator > 0

    def test_category_info(self):
        """Test category metadata."""
        momentum_info = CATEGORY_INFO.get(StrategyCategory.MOMENTUM)
        assert momentum_info is not None
        assert "name" in momentum_info
        assert "description" in momentum_info


class TestStrategy:
    """Tests for strategy model."""

    def test_strategy_creation(self):
        """Test strategy creation."""
        strategy = Strategy(
            creator_id="user123",
            name="Test Strategy",
            category=StrategyCategory.MOMENTUM,
            risk_level=RiskLevel.MODERATE,
        )
        assert strategy.creator_id == "user123"
        assert strategy.category == StrategyCategory.MOMENTUM
        assert not strategy.is_published

    def test_strategy_slug_generation(self):
        """Test slug is auto-generated."""
        strategy = Strategy(
            creator_id="user123",
            name="My Awesome Strategy",
            category=StrategyCategory.VALUE,
            risk_level=RiskLevel.CONSERVATIVE,
        )
        assert strategy.slug == "my-awesome-strategy"

    def test_publish_strategy(self):
        """Test publishing strategy."""
        strategy = Strategy(
            creator_id="user123",
            name="Test",
            category=StrategyCategory.GROWTH,
            risk_level=RiskLevel.MODERATE,
        )
        strategy.publish()
        assert strategy.is_published
        assert strategy.published_at is not None

    def test_unpublish_strategy(self):
        """Test unpublishing strategy."""
        strategy = Strategy(
            creator_id="user123",
            name="Test",
            category=StrategyCategory.GROWTH,
            risk_level=RiskLevel.MODERATE,
        )
        strategy.publish()
        strategy.unpublish()
        assert not strategy.is_published

    def test_update_stats(self):
        """Test updating strategy stats."""
        strategy = Strategy(
            creator_id="user123",
            name="Test",
            category=StrategyCategory.MOMENTUM,
            risk_level=RiskLevel.MODERATE,
        )
        strategy.update_stats(
            subscriber_count=100,
            avg_rating=4.5,
            total_return_pct=25.5,
        )
        assert strategy.subscriber_count == 100
        assert strategy.avg_rating == 4.5
        assert strategy.total_return_pct == 25.5

    def test_get_monthly_cost(self):
        """Test getting monthly cost."""
        free_strategy = Strategy(
            creator_id="user123",
            name="Free",
            category=StrategyCategory.VALUE,
            risk_level=RiskLevel.CONSERVATIVE,
            pricing_model=PricingModel.FREE,
        )
        assert free_strategy.get_monthly_cost() == 0

        paid_strategy = Strategy(
            creator_id="user123",
            name="Paid",
            category=StrategyCategory.VALUE,
            risk_level=RiskLevel.CONSERVATIVE,
            pricing_model=PricingModel.SUBSCRIPTION,
            monthly_price=29.99,
        )
        assert paid_strategy.get_monthly_cost() == 29.99


class TestSubscription:
    """Tests for subscription model."""

    def test_subscription_creation(self):
        """Test subscription creation."""
        subscription = Subscription(
            strategy_id="strat123",
            subscriber_id="user456",
        )
        assert subscription.strategy_id == "strat123"
        assert subscription.status == SubscriptionStatus.ACTIVE
        assert subscription.is_active()

    def test_cancel_subscription(self):
        """Test cancelling subscription."""
        subscription = Subscription(
            strategy_id="strat123",
            subscriber_id="user456",
        )
        subscription.cancel("Too expensive")
        assert subscription.status == SubscriptionStatus.CANCELLED
        assert subscription.cancel_reason == "Too expensive"
        assert not subscription.is_active()

    def test_pause_resume_subscription(self):
        """Test pausing and resuming subscription."""
        subscription = Subscription(
            strategy_id="strat123",
            subscriber_id="user456",
        )
        subscription.pause()
        assert subscription.status == SubscriptionStatus.PAUSED

        subscription.resume()
        assert subscription.status == SubscriptionStatus.ACTIVE

    def test_expired_subscription(self):
        """Test expired subscription check."""
        subscription = Subscription(
            strategy_id="strat123",
            subscriber_id="user456",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        assert not subscription.is_active()


class TestReview:
    """Tests for review model."""

    def test_review_creation(self):
        """Test review creation."""
        review = Review(
            strategy_id="strat123",
            reviewer_id="user456",
            rating=4,
            title="Great strategy",
            content="Really helped my portfolio",
        )
        assert review.rating == 4
        assert review.is_approved

    def test_rating_clamping(self):
        """Test rating is clamped to 1-5."""
        review_low = Review(
            strategy_id="strat123",
            reviewer_id="user456",
            rating=0,
        )
        assert review_low.rating == 1

        review_high = Review(
            strategy_id="strat123",
            reviewer_id="user456",
            rating=10,
        )
        assert review_high.rating == 5

    def test_creator_response(self):
        """Test adding creator response."""
        review = Review(
            strategy_id="strat123",
            reviewer_id="user456",
            rating=3,
        )
        review.respond("Thank you for your feedback!")
        assert review.creator_response == "Thank you for your feedback!"
        assert review.responded_at is not None


class TestPerformanceSnapshot:
    """Tests for performance snapshot model."""

    def test_snapshot_creation(self):
        """Test snapshot creation."""
        snapshot = PerformanceSnapshot(
            strategy_id="strat123",
            snapshot_date=date.today(),
            daily_return_pct=1.5,
            cumulative_return_pct=25.0,
            sharpe_ratio=1.85,
        )
        assert snapshot.daily_return_pct == 1.5
        assert snapshot.cumulative_return_pct == 25.0

    def test_snapshot_to_dict(self):
        """Test snapshot serialization."""
        snapshot = PerformanceSnapshot(
            strategy_id="strat123",
            snapshot_date=date.today(),
            daily_return_pct=1.5,
        )
        data = snapshot.to_dict()
        assert data["strategy_id"] == "strat123"
        assert data["daily_return_pct"] == 1.5


class TestStrategyManager:
    """Tests for strategy manager."""

    def test_create_strategy(self):
        """Test creating a strategy."""
        manager = StrategyManager()
        strategy = manager.create_strategy(
            creator_id="user123",
            name="Test Strategy",
            category=StrategyCategory.MOMENTUM,
            risk_level=RiskLevel.MODERATE,
            description="A test strategy",
        )
        assert strategy.creator_id == "user123"
        assert strategy.name == "Test Strategy"

    def test_get_strategy(self):
        """Test getting strategy by ID."""
        manager = StrategyManager()
        strategy = manager.create_strategy(
            creator_id="user123",
            name="Test",
            category=StrategyCategory.VALUE,
            risk_level=RiskLevel.CONSERVATIVE,
        )
        retrieved = manager.get_strategy(strategy.strategy_id)
        assert retrieved == strategy

    def test_get_strategy_by_slug(self):
        """Test getting strategy by slug."""
        manager = StrategyManager()
        strategy = manager.create_strategy(
            creator_id="user123",
            name="My Strategy",
            category=StrategyCategory.GROWTH,
            risk_level=RiskLevel.MODERATE,
        )
        retrieved = manager.get_strategy_by_slug("my-strategy")
        assert retrieved == strategy

    def test_unique_slug(self):
        """Test slug uniqueness."""
        manager = StrategyManager()
        s1 = manager.create_strategy(
            creator_id="user1",
            name="Test Strategy",
            category=StrategyCategory.MOMENTUM,
            risk_level=RiskLevel.MODERATE,
        )
        s2 = manager.create_strategy(
            creator_id="user2",
            name="Test Strategy",
            category=StrategyCategory.MOMENTUM,
            risk_level=RiskLevel.MODERATE,
        )
        assert s1.slug != s2.slug

    def test_creator_limit(self):
        """Test creator strategy limit."""
        config = MarketplaceConfig(max_strategies_per_creator=2)
        manager = StrategyManager(config=config)

        manager.create_strategy("user123", "S1", StrategyCategory.MOMENTUM, RiskLevel.MODERATE)
        manager.create_strategy("user123", "S2", StrategyCategory.VALUE, RiskLevel.MODERATE)

        with pytest.raises(ValueError):
            manager.create_strategy("user123", "S3", StrategyCategory.GROWTH, RiskLevel.MODERATE)

    def test_pricing_validation(self):
        """Test pricing validation."""
        manager = StrategyManager()

        with pytest.raises(ValueError):
            manager.create_strategy(
                creator_id="user123",
                name="Test",
                category=StrategyCategory.MOMENTUM,
                risk_level=RiskLevel.MODERATE,
                pricing_model=PricingModel.SUBSCRIPTION,
                monthly_price=1.0,  # Below minimum
            )

    def test_publish_unpublish(self):
        """Test publishing and unpublishing."""
        manager = StrategyManager()
        strategy = manager.create_strategy(
            creator_id="user123",
            name="Test",
            category=StrategyCategory.MOMENTUM,
            risk_level=RiskLevel.MODERATE,
        )

        manager.publish_strategy(strategy.strategy_id)
        assert strategy.is_published

        manager.unpublish_strategy(strategy.strategy_id)
        assert not strategy.is_published

    def test_add_version(self):
        """Test adding strategy version."""
        manager = StrategyManager()
        strategy = manager.create_strategy(
            creator_id="user123",
            name="Test",
            category=StrategyCategory.MOMENTUM,
            risk_level=RiskLevel.MODERATE,
        )

        version = manager.add_version(
            strategy_id=strategy.strategy_id,
            version="1.1.0",
            change_notes="Added new indicator",
        )
        assert version.version == "1.1.0"

        versions = manager.get_versions(strategy.strategy_id)
        assert len(versions) == 2  # Initial + new

    def test_get_creator_stats(self):
        """Test getting creator statistics."""
        manager = StrategyManager()

        s1 = manager.create_strategy(
            creator_id="user123",
            name="Strategy 1",
            category=StrategyCategory.MOMENTUM,
            risk_level=RiskLevel.MODERATE,
        )
        s1.update_stats(subscriber_count=50, avg_rating=4.5)
        s1.is_published = True

        s2 = manager.create_strategy(
            creator_id="user123",
            name="Strategy 2",
            category=StrategyCategory.VALUE,
            risk_level=RiskLevel.CONSERVATIVE,
        )
        s2.update_stats(subscriber_count=30, avg_rating=4.2)
        s2.is_published = True

        stats = manager.get_creator_stats("user123")
        assert stats.total_strategies == 2
        assert stats.published_strategies == 2
        assert stats.total_subscribers == 80


class TestSubscriptionManager:
    """Tests for subscription manager."""

    def test_subscribe(self):
        """Test subscribing to a strategy."""
        manager = SubscriptionManager()
        strategy = Strategy(
            creator_id="creator123",
            name="Test",
            category=StrategyCategory.MOMENTUM,
            risk_level=RiskLevel.MODERATE,
        )
        strategy.publish()

        subscription = manager.subscribe(
            strategy=strategy,
            subscriber_id="user456",
        )
        assert subscription.strategy_id == strategy.strategy_id
        assert subscription.is_active()

    def test_cannot_subscribe_twice(self):
        """Test cannot subscribe to same strategy twice."""
        manager = SubscriptionManager()
        strategy = Strategy(
            creator_id="creator123",
            name="Test",
            category=StrategyCategory.MOMENTUM,
            risk_level=RiskLevel.MODERATE,
        )
        strategy.publish()

        manager.subscribe(strategy, "user456")

        with pytest.raises(ValueError):
            manager.subscribe(strategy, "user456")

    def test_cannot_subscribe_to_own_strategy(self):
        """Test cannot subscribe to own strategy."""
        manager = SubscriptionManager()
        strategy = Strategy(
            creator_id="user123",
            name="Test",
            category=StrategyCategory.MOMENTUM,
            risk_level=RiskLevel.MODERATE,
        )
        strategy.publish()

        with pytest.raises(ValueError):
            manager.subscribe(strategy, "user123")

    def test_unsubscribe(self):
        """Test unsubscribing."""
        manager = SubscriptionManager()
        strategy = Strategy(
            creator_id="creator123",
            name="Test",
            category=StrategyCategory.MOMENTUM,
            risk_level=RiskLevel.MODERATE,
        )
        strategy.publish()

        manager.subscribe(strategy, "user456")
        result = manager.unsubscribe(strategy.strategy_id, "user456", "Changed mind")
        assert result

        sub = manager.get_subscription(strategy.strategy_id, "user456")
        assert sub.status == SubscriptionStatus.CANCELLED

    def test_trial_subscription(self):
        """Test trial subscription."""
        manager = SubscriptionManager()
        strategy = Strategy(
            creator_id="creator123",
            name="Test",
            category=StrategyCategory.MOMENTUM,
            risk_level=RiskLevel.MODERATE,
        )
        strategy.publish()

        subscription = manager.subscribe(strategy, "user456", trial=True)
        assert subscription.status == SubscriptionStatus.TRIAL
        assert subscription.expires_at is not None

    def test_update_settings(self):
        """Test updating subscription settings."""
        manager = SubscriptionManager()
        strategy = Strategy(
            creator_id="creator123",
            name="Test",
            category=StrategyCategory.MOMENTUM,
            risk_level=RiskLevel.MODERATE,
        )
        strategy.publish()

        subscription = manager.subscribe(strategy, "user456")
        updated = manager.update_settings(
            subscription.subscription_id,
            position_size_pct=50.0,
            risk_multiplier=0.5,
        )
        assert updated.position_size_pct == 50.0
        assert updated.risk_multiplier == 0.5

    def test_get_stats(self):
        """Test subscription statistics."""
        manager = SubscriptionManager()
        strategy = Strategy(
            creator_id="creator123",
            name="Test",
            category=StrategyCategory.MOMENTUM,
            risk_level=RiskLevel.MODERATE,
        )
        strategy.publish()

        manager.subscribe(strategy, "user1")
        manager.subscribe(strategy, "user2")

        stats = manager.get_stats()
        assert stats["total_subscriptions"] == 2
        assert stats["active_subscriptions"] == 2


class TestMarketplacePerformanceTracker:
    """Tests for performance tracker."""

    def test_record_snapshot(self):
        """Test recording performance snapshot."""
        tracker = PerformanceTracker()
        snapshot = tracker.record_snapshot(
            strategy_id="strat123",
            snapshot_date=date.today(),
            daily_return_pct=1.5,
            cumulative_return_pct=25.0,
        )
        assert snapshot.daily_return_pct == 1.5

    def test_get_latest_snapshot(self):
        """Test getting latest snapshot."""
        tracker = PerformanceTracker()
        today = date.today()

        tracker.record_snapshot("strat123", today - timedelta(days=1), daily_return_pct=1.0)
        tracker.record_snapshot("strat123", today, daily_return_pct=1.5)

        latest = tracker.get_latest_snapshot("strat123")
        assert latest.daily_return_pct == 1.5

    def test_get_snapshots_range(self):
        """Test getting snapshots for date range."""
        tracker = PerformanceTracker()
        today = date.today()

        for i in range(10):
            tracker.record_snapshot(
                "strat123",
                today - timedelta(days=i),
                daily_return_pct=float(i),
            )

        snapshots = tracker.get_snapshots(
            "strat123",
            start_date=today - timedelta(days=5),
            end_date=today,
        )
        assert len(snapshots) == 6

    def test_get_period_return(self):
        """Test getting return over a period."""
        tracker = PerformanceTracker()
        today = date.today()

        tracker.record_snapshot("strat123", today - timedelta(days=30), cumulative_return_pct=10.0)
        tracker.record_snapshot("strat123", today, cumulative_return_pct=15.0)

        period_return = tracker.get_period_return("strat123", days=30)
        assert period_return == 5.0

    def test_get_leaderboard(self):
        """Test generating leaderboard."""
        tracker = PerformanceTracker()
        today = date.today()

        strategies = []
        for i in range(5):
            strategy = Strategy(
                creator_id=f"user{i}",
                name=f"Strategy {i}",
                category=StrategyCategory.MOMENTUM,
                risk_level=RiskLevel.MODERATE,
            )
            strategy.publish()
            strategies.append(strategy)

            # Add enough history
            for day in range(35):
                tracker.record_snapshot(
                    strategy.strategy_id,
                    today - timedelta(days=day),
                    cumulative_return_pct=float(i * 10),
                    sharpe_ratio=float(i) / 2,
                )

        leaderboard = tracker.get_leaderboard(strategies, limit=3)
        assert len(leaderboard) == 3
        assert leaderboard[0].rank == 1


class TestStrategyDiscovery:
    """Tests for strategy discovery."""

    def test_search_by_category(self):
        """Test searching by category."""
        discovery = StrategyDiscovery()

        strategies = [
            Strategy(
                creator_id="user1",
                name="Momentum 1",
                category=StrategyCategory.MOMENTUM,
                risk_level=RiskLevel.MODERATE,
            ),
            Strategy(
                creator_id="user2",
                name="Value 1",
                category=StrategyCategory.VALUE,
                risk_level=RiskLevel.CONSERVATIVE,
            ),
        ]
        for s in strategies:
            s.publish()

        results = discovery.search(strategies, category=StrategyCategory.MOMENTUM)
        assert len(results) == 1
        assert results[0].category == StrategyCategory.MOMENTUM

    def test_search_by_query(self):
        """Test text search."""
        discovery = StrategyDiscovery()

        strategies = [
            Strategy(
                creator_id="user1",
                name="Tech Growth",
                category=StrategyCategory.GROWTH,
                risk_level=RiskLevel.AGGRESSIVE,
            ),
            Strategy(
                creator_id="user2",
                name="Value Investing",
                category=StrategyCategory.VALUE,
                risk_level=RiskLevel.CONSERVATIVE,
            ),
        ]
        for s in strategies:
            s.publish()

        results = discovery.search(strategies, query="tech")
        assert len(results) == 1
        assert "Tech" in results[0].name

    def test_search_free_only(self):
        """Test filtering free strategies."""
        discovery = StrategyDiscovery()

        strategies = [
            Strategy(
                creator_id="user1",
                name="Free Strategy",
                category=StrategyCategory.MOMENTUM,
                risk_level=RiskLevel.MODERATE,
                pricing_model=PricingModel.FREE,
            ),
            Strategy(
                creator_id="user2",
                name="Paid Strategy",
                category=StrategyCategory.MOMENTUM,
                risk_level=RiskLevel.MODERATE,
                pricing_model=PricingModel.SUBSCRIPTION,
                monthly_price=29.99,
            ),
        ]
        for s in strategies:
            s.publish()

        results = discovery.search(strategies, is_free=True)
        assert len(results) == 1
        assert results[0].pricing_model == PricingModel.FREE

    def test_get_similar_strategies(self):
        """Test getting similar strategies."""
        discovery = StrategyDiscovery()

        base_strategy = Strategy(
            creator_id="user1",
            name="Base",
            category=StrategyCategory.MOMENTUM,
            risk_level=RiskLevel.MODERATE,
            trading_style=TradingStyle.TREND_FOLLOWING,
        )

        strategies = [
            base_strategy,
            Strategy(
                creator_id="user2",
                name="Similar",
                category=StrategyCategory.MOMENTUM,
                risk_level=RiskLevel.MODERATE,
                trading_style=TradingStyle.TREND_FOLLOWING,
            ),
            Strategy(
                creator_id="user3",
                name="Different",
                category=StrategyCategory.VALUE,
                risk_level=RiskLevel.CONSERVATIVE,
            ),
        ]
        for s in strategies:
            s.publish()

        similar = discovery.get_similar_strategies(base_strategy, strategies)
        assert len(similar) >= 1
        assert similar[0].name == "Similar"

    def test_add_review(self):
        """Test adding a review."""
        discovery = StrategyDiscovery()

        review = discovery.add_review(
            strategy_id="strat123",
            reviewer_id="user456",
            rating=5,
            title="Excellent!",
            content="This strategy has been amazing for my portfolio. Highly recommend!" * 2,
            is_verified_subscriber=True,
            subscription_days=30,
        )
        assert review.rating == 5
        assert review.is_verified_subscriber

    def test_review_minimum_length(self):
        """Test review minimum length validation."""
        config = MarketplaceConfig(min_review_length=50)
        discovery = StrategyDiscovery(config=config)

        with pytest.raises(ValueError):
            discovery.add_review(
                strategy_id="strat123",
                reviewer_id="user456",
                rating=4,
                content="Too short",
            )

    def test_get_reviews(self):
        """Test getting reviews."""
        discovery = StrategyDiscovery()

        # Add some reviews
        for i in range(5):
            discovery.add_review(
                strategy_id="strat123",
                reviewer_id=f"user{i}",
                rating=5 - i,
            )

        reviews = discovery.get_reviews("strat123", sort_by="rating_high")
        assert len(reviews) == 5
        assert reviews[0].rating == 5

    def test_get_average_rating(self):
        """Test getting average rating."""
        discovery = StrategyDiscovery()

        discovery.add_review("strat123", "user1", rating=5)
        discovery.add_review("strat123", "user2", rating=4)
        discovery.add_review("strat123", "user3", rating=3)

        avg, count = discovery.get_average_rating("strat123")
        assert avg == 4.0
        assert count == 3

    def test_respond_to_review(self):
        """Test creator responding to review."""
        discovery = StrategyDiscovery()

        review = discovery.add_review(
            strategy_id="strat123",
            reviewer_id="user456",
            rating=4,
        )

        result = discovery.respond_to_review(
            review.review_id,
            "strat123",
            "Thanks for the feedback!",
        )
        assert result
        assert review.creator_response == "Thanks for the feedback!"
