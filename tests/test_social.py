"""Tests for PRD-14: Social Trading Platform."""

import pytest
from datetime import datetime, timezone

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
    SocialConfig,
    CopyConfig,
    FeedConfig,
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


class TestSocialConfig:
    """Test configuration."""

    def test_profile_visibility(self):
        assert len(ProfileVisibility) == 3
        assert ProfileVisibility.PUBLIC.value == "public"

    def test_trading_styles(self):
        assert len(TradingStyle) == 8
        assert TradingStyle.QUANTITATIVE.value == "quantitative"

    def test_badges(self):
        assert len(Badge) == 8
        assert Badge.TOP_PERFORMER.value == "top_performer"

    def test_strategy_categories(self):
        assert len(StrategyCategory) == 10
        assert StrategyCategory.MULTI_ASSET.value == "multi_asset"

    def test_copy_modes(self):
        assert len(CopyMode) == 3
        assert CopyMode.PROPORTIONAL.value == "proportional"

    def test_leaderboard_metrics(self):
        assert len(LeaderboardMetric) == 6
        assert LeaderboardMetric.SHARPE_RATIO.value == "sharpe_ratio"

    def test_badge_requirements(self):
        assert len(BADGE_REQUIREMENTS) == 8
        assert BADGE_REQUIREMENTS[Badge.RISK_MASTER]["min_sharpe"] == 1.5

    def test_social_config_defaults(self):
        config = SocialConfig()
        assert config.max_followers == 10000
        assert config.max_following == 500
        assert config.max_strategies_per_user == 10
        assert config.copy.max_concurrent_copies == 10


class TestPerformanceStats:
    """Test performance stats model."""

    def test_defaults(self):
        stats = PerformanceStats()
        assert stats.total_return == 0.0
        assert stats.total_trades == 0

    def test_qualified_for_leaderboard(self):
        stats = PerformanceStats(total_trades=15)
        assert stats.is_qualified_for_leaderboard is True

        stats = PerformanceStats(total_trades=5)
        assert stats.is_qualified_for_leaderboard is False


class TestTraderProfile:
    """Test trader profile model."""

    def test_add_badge(self):
        profile = TraderProfile()
        profile.add_badge(Badge.TOP_PERFORMER)
        assert Badge.TOP_PERFORMER in profile.badges
        # No duplicate
        profile.add_badge(Badge.TOP_PERFORMER)
        assert len(profile.badges) == 1

    def test_update_rating(self):
        profile = TraderProfile()
        profile.update_rating(5.0)
        assert profile.rating == 5.0
        assert profile.rating_count == 1

        profile.update_rating(3.0)
        assert profile.rating == 4.0
        assert profile.rating_count == 2

    def test_rating_clamped(self):
        profile = TraderProfile()
        profile.update_rating(10.0)  # Should clamp to 5
        assert profile.rating == 5.0


class TestStrategy:
    """Test strategy model."""

    def test_publish(self):
        s = Strategy(status=StrategyStatus.DRAFT)
        s.publish()
        assert s.status == StrategyStatus.PUBLISHED

    def test_archive(self):
        s = Strategy(status=StrategyStatus.PUBLISHED)
        s.archive()
        assert s.status == StrategyStatus.ARCHIVED

    def test_increment_version(self):
        s = Strategy(version=1)
        s.increment_version()
        assert s.version == 2


class TestCopyRelationship:
    """Test copy relationship model."""

    def test_pause_resume(self):
        rel = CopyRelationship()
        rel.pause()
        assert rel.status == CopyStatus.PAUSED
        rel.resume()
        assert rel.status == CopyStatus.ACTIVE

    def test_stop(self):
        rel = CopyRelationship()
        rel.stop()
        assert rel.status == CopyStatus.STOPPED
        assert rel.stopped_at is not None

    def test_record_trade(self):
        rel = CopyRelationship()
        rel.record_trade(50.0)
        assert rel.total_trades_copied == 1
        assert rel.total_pnl == 50.0
        rel.record_trade(-20.0)
        assert rel.total_trades_copied == 2
        assert rel.total_pnl == 30.0

    def test_max_loss_check(self):
        rel = CopyRelationship(allocation_amount=1000.0, max_loss_pct=0.10)
        rel.record_trade(-50.0)
        assert rel.check_max_loss() is False

        rel.record_trade(-60.0)  # total = -110, 11% > 10%
        assert rel.check_max_loss() is True
        assert rel.status == CopyStatus.MAX_LOSS_HIT


class TestLeaderboardEntry:
    """Test leaderboard entry model."""

    def test_rank_change(self):
        entry = LeaderboardEntry(rank=3, previous_rank=5)
        assert entry.rank_change == 2  # Moved up 2

        entry = LeaderboardEntry(rank=5, previous_rank=3)
        assert entry.rank_change == -2  # Moved down 2

    def test_rank_change_none(self):
        entry = LeaderboardEntry(rank=1)
        assert entry.rank_change is None


class TestLeaderboard:
    """Test leaderboard model."""

    def test_top_n(self):
        entries = [LeaderboardEntry(rank=i+1) for i in range(20)]
        board = Leaderboard(entries=entries)
        assert len(board.top_n) == 10


class TestProfileManager:
    """Test profile manager."""

    def test_create_profile(self):
        mgr = ProfileManager()
        profile = mgr.create_profile("u1", "TraderJoe", bio="Swing trader")
        assert profile.display_name == "TraderJoe"
        assert profile.bio == "Swing trader"
        assert profile.user_id == "u1"

    def test_get_profile(self):
        mgr = ProfileManager()
        mgr.create_profile("u1", "TraderJoe")
        assert mgr.get_profile("u1") is not None
        assert mgr.get_profile("u2") is None

    def test_update_profile(self):
        mgr = ProfileManager()
        mgr.create_profile("u1", "TraderJoe")
        updated = mgr.update_profile("u1", display_name="JoePro")
        assert updated.display_name == "JoePro"

    def test_update_stats_awards_badges(self):
        mgr = ProfileManager()
        mgr.create_profile("u1", "TraderJoe")
        stats = PerformanceStats(
            total_return=0.25,
            sharpe_ratio=2.0,
            max_drawdown=-0.05,
            win_rate=0.60,
            total_trades=150,
        )
        profile = mgr.update_stats("u1", stats)
        assert Badge.TOP_PERFORMER in profile.badges
        assert Badge.VETERAN in profile.badges
        assert Badge.RISK_MASTER in profile.badges
        assert Badge.CONSISTENT in profile.badges

    def test_follow_unfollow(self):
        mgr = ProfileManager()
        mgr.create_profile("u1", "Trader1")
        mgr.create_profile("u2", "Trader2")

        assert mgr.follow("u1", "u2") is True
        assert mgr.is_following("u1", "u2") is True
        assert mgr.get_profile("u1").following_count == 1
        assert mgr.get_profile("u2").followers_count == 1

        assert mgr.unfollow("u1", "u2") is True
        assert mgr.is_following("u1", "u2") is False
        assert mgr.get_profile("u1").following_count == 0

    def test_cannot_follow_self(self):
        mgr = ProfileManager()
        mgr.create_profile("u1", "Trader1")
        assert mgr.follow("u1", "u1") is False

    def test_no_duplicate_follow(self):
        mgr = ProfileManager()
        mgr.create_profile("u1", "Trader1")
        mgr.create_profile("u2", "Trader2")
        assert mgr.follow("u1", "u2") is True
        assert mgr.follow("u1", "u2") is False

    def test_get_followers_following(self):
        mgr = ProfileManager()
        mgr.create_profile("u1", "T1")
        mgr.create_profile("u2", "T2")
        mgr.create_profile("u3", "T3")
        mgr.follow("u2", "u1")
        mgr.follow("u3", "u1")

        assert set(mgr.get_followers("u1")) == {"u2", "u3"}
        assert mgr.get_following("u2") == ["u1"]

    def test_search_profiles(self):
        mgr = ProfileManager()
        mgr.create_profile("u1", "SwingTrader", trading_style=TradingStyle.SWING_TRADING)
        mgr.create_profile("u2", "DayTrader", trading_style=TradingStyle.DAY_TRADING)
        mgr.create_profile("u3", "SwingPro", trading_style=TradingStyle.SWING_TRADING)

        results = mgr.search_profiles(trading_style=TradingStyle.SWING_TRADING)
        assert len(results) == 2

        results = mgr.search_profiles(query="swing")
        assert len(results) == 2

    def test_rate_trader(self):
        mgr = ProfileManager()
        mgr.create_profile("u1", "Trader")
        profile = mgr.rate_trader("u1", 4.5)
        assert profile.rating == 4.5
        assert profile.rating_count == 1


class TestStrategyManager:
    """Test strategy manager."""

    def test_create_strategy(self):
        mgr = StrategyManager()
        s = mgr.create_strategy("u1", "Momentum Alpha", category=StrategyCategory.MOMENTUM)
        assert s.name == "Momentum Alpha"
        assert s.status == StrategyStatus.DRAFT

    def test_publish_strategy(self):
        mgr = StrategyManager()
        s = mgr.create_strategy("u1", "Test")
        published = mgr.publish_strategy(s.strategy_id)
        assert published.status == StrategyStatus.PUBLISHED

    def test_archive_strategy(self):
        mgr = StrategyManager()
        s = mgr.create_strategy("u1", "Test")
        archived = mgr.archive_strategy(s.strategy_id)
        assert archived.status == StrategyStatus.ARCHIVED

    def test_update_strategy_versions(self):
        mgr = StrategyManager()
        s = mgr.create_strategy("u1", "Test")
        assert s.version == 1
        updated = mgr.update_strategy(s.strategy_id, name="Test v2")
        assert updated.version == 2
        assert updated.name == "Test v2"

    def test_max_strategies_limit(self):
        config = SocialConfig(max_strategies_per_user=2)
        mgr = StrategyManager(config=config)
        mgr.create_strategy("u1", "S1")
        mgr.create_strategy("u1", "S2")
        with pytest.raises(ValueError, match="max strategies"):
            mgr.create_strategy("u1", "S3")

    def test_record_performance(self):
        mgr = StrategyManager()
        s = mgr.create_strategy("u1", "Test")
        perf = mgr.record_performance(s.strategy_id, 0.01, 101.0, 5)
        assert perf.daily_return == 0.01
        assert perf.nav == 101.0

    def test_get_performance_history(self):
        mgr = StrategyManager()
        s = mgr.create_strategy("u1", "Test")
        for i in range(5):
            mgr.record_performance(s.strategy_id, 0.01, 100 + i, i)
        history = mgr.get_performance(s.strategy_id)
        assert len(history) == 5

    def test_search_strategies(self):
        mgr = StrategyManager()
        s1 = mgr.create_strategy("u1", "Momentum", category=StrategyCategory.MOMENTUM, tags=["momentum"])
        s2 = mgr.create_strategy("u1", "Value", category=StrategyCategory.VALUE, tags=["value"])
        mgr.publish_strategy(s1.strategy_id)
        mgr.publish_strategy(s2.strategy_id)

        results = mgr.search_strategies(category=StrategyCategory.MOMENTUM)
        assert len(results) == 1
        assert results[0].name == "Momentum"

        results = mgr.search_strategies(tags=["value"])
        assert len(results) == 1

    def test_get_user_strategies(self):
        mgr = StrategyManager()
        mgr.create_strategy("u1", "S1")
        mgr.create_strategy("u2", "S2")
        assert len(mgr.get_user_strategies("u1")) == 1

    def test_risk_level_clamped(self):
        mgr = StrategyManager()
        s = mgr.create_strategy("u1", "Test", risk_level=10)
        assert s.risk_level == 5


class TestCopyTradingEngine:
    """Test copy trading engine."""

    def test_start_copying(self):
        engine = CopyTradingEngine()
        rel = engine.start_copying("u2", "u1", "s1")
        assert rel.copier_user_id == "u2"
        assert rel.leader_user_id == "u1"
        assert rel.status == CopyStatus.ACTIVE

    def test_cannot_copy_self(self):
        engine = CopyTradingEngine()
        with pytest.raises(ValueError, match="Cannot copy yourself"):
            engine.start_copying("u1", "u1", "s1")

    def test_duplicate_copy_blocked(self):
        engine = CopyTradingEngine()
        engine.start_copying("u2", "u1", "s1")
        with pytest.raises(ValueError, match="Already copying"):
            engine.start_copying("u2", "u1", "s1")

    def test_max_concurrent_copies(self):
        config = SocialConfig(copy=CopyConfig(max_concurrent_copies=2))
        engine = CopyTradingEngine(config=config)
        engine.start_copying("u2", "u1", "s1")
        engine.start_copying("u2", "u3", "s2")
        with pytest.raises(ValueError, match="max concurrent"):
            engine.start_copying("u2", "u4", "s3")

    def test_min_allocation(self):
        engine = CopyTradingEngine()
        with pytest.raises(ValueError, match="below minimum"):
            engine.start_copying("u2", "u1", "s1", allocation_amount=10.0)

    def test_stop_pause_resume(self):
        engine = CopyTradingEngine()
        rel = engine.start_copying("u2", "u1", "s1")

        paused = engine.pause_copying(rel.copy_id)
        assert paused.status == CopyStatus.PAUSED

        resumed = engine.resume_copying(rel.copy_id)
        assert resumed.status == CopyStatus.ACTIVE

        stopped = engine.stop_copying(rel.copy_id)
        assert stopped.status == CopyStatus.STOPPED

    def test_record_trade_and_max_loss(self):
        engine = CopyTradingEngine()
        rel = engine.start_copying(
            "u2", "u1", "s1",
            allocation_amount=1000.0,
            max_loss_pct=0.10,
        )

        engine.record_copied_trade(rel.copy_id, 50.0)
        assert rel.total_pnl == 50.0

        engine.record_copied_trade(rel.copy_id, -160.0)
        # Total PNL = -110, loss = 11% > 10%
        assert rel.status == CopyStatus.MAX_LOSS_HIT

    def test_get_active_copies(self):
        engine = CopyTradingEngine()
        engine.start_copying("u2", "u1", "s1")
        engine.start_copying("u2", "u3", "s2")
        rel3 = engine.start_copying("u2", "u4", "s3")
        engine.stop_copying(rel3.copy_id)

        active = engine.get_active_copies("u2")
        assert len(active) == 2

    def test_get_copiers(self):
        engine = CopyTradingEngine()
        engine.start_copying("u2", "u1", "s1")
        engine.start_copying("u3", "u1", "s1")
        copiers = engine.get_copiers("u1")
        assert len(copiers) == 2

    def test_compute_copy_size_fixed(self):
        engine = CopyTradingEngine()
        rel = engine.start_copying(
            "u2", "u1", "s1",
            mode=CopyMode.FIXED_AMOUNT,
            allocation_amount=2000.0,
        )
        size = engine.compute_copy_size(rel.copy_id, 0.05, 100000.0)
        assert size == 100.0  # 2000 * 0.05

    def test_compute_copy_size_percentage(self):
        engine = CopyTradingEngine()
        rel = engine.start_copying(
            "u2", "u1", "s1",
            mode=CopyMode.PERCENTAGE,
            allocation_amount=10.0,  # 10%
        )
        size = engine.compute_copy_size(rel.copy_id, 0.05, 100000.0)
        assert size == 500.0  # 10% * 100000 * 0.05

    def test_get_stats(self):
        engine = CopyTradingEngine()
        engine.start_copying("u2", "u1", "s1")
        rel = engine.start_copying("u2", "u3", "s2")
        engine.stop_copying(rel.copy_id)

        stats = engine.get_stats()
        assert stats["total_relationships"] == 2
        assert stats["active"] == 1
        assert stats["stopped"] == 1


class TestLeaderboardManager:
    """Test leaderboard manager."""

    def _make_profiles(self) -> list[TraderProfile]:
        """Create test profiles with stats."""
        profiles = []
        for i, (name, ret, sharpe, wr, trades) in enumerate([
            ("Alpha", 0.35, 2.1, 0.62, 50),
            ("Beta", 0.20, 1.5, 0.58, 40),
            ("Gamma", 0.45, 1.8, 0.55, 30),
            ("Delta", 0.10, 0.9, 0.70, 20),
            ("Epsilon", 0.05, 0.5, 0.45, 5),  # Below min trades
        ]):
            p = TraderProfile(
                user_id=f"u{i+1}",
                display_name=name,
                stats=PerformanceStats(
                    total_return=ret,
                    sharpe_ratio=sharpe,
                    win_rate=wr,
                    total_trades=trades,
                    max_drawdown=-0.08,
                    calmar_ratio=ret / 0.08,
                ),
            )
            profiles.append(p)
        return profiles

    def test_compute_leaderboard_by_return(self):
        mgr = LeaderboardManager()
        profiles = self._make_profiles()
        board = mgr.compute_leaderboard(profiles, LeaderboardMetric.TOTAL_RETURN)

        assert len(board.entries) == 4  # Epsilon excluded (< min trades)
        assert board.entries[0].display_name == "Gamma"  # Highest return
        assert board.entries[0].rank == 1

    def test_compute_leaderboard_by_sharpe(self):
        mgr = LeaderboardManager()
        profiles = self._make_profiles()
        board = mgr.compute_leaderboard(profiles, LeaderboardMetric.SHARPE_RATIO)

        assert board.entries[0].display_name == "Alpha"  # Highest Sharpe

    def test_compute_leaderboard_by_win_rate(self):
        mgr = LeaderboardManager()
        profiles = self._make_profiles()
        board = mgr.compute_leaderboard(profiles, LeaderboardMetric.WIN_RATE)

        assert board.entries[0].display_name == "Delta"  # Highest win rate

    def test_rank_change_tracking(self):
        mgr = LeaderboardManager()
        profiles = self._make_profiles()

        # First computation
        mgr.compute_leaderboard(profiles, LeaderboardMetric.TOTAL_RETURN)

        # Second computation (same data — ranks should match)
        board = mgr.compute_leaderboard(profiles, LeaderboardMetric.TOTAL_RETURN)
        assert board.entries[0].previous_rank == 1
        assert board.entries[0].rank_change == 0

    def test_get_user_rank(self):
        mgr = LeaderboardManager()
        profiles = self._make_profiles()
        mgr.compute_leaderboard(profiles, LeaderboardMetric.TOTAL_RETURN)

        entry = mgr.get_user_rank("u3", LeaderboardMetric.TOTAL_RETURN)
        assert entry is not None
        assert entry.rank == 1  # Gamma has highest return

    def test_unqualified_excluded(self):
        mgr = LeaderboardManager()
        profiles = self._make_profiles()
        board = mgr.compute_leaderboard(profiles)

        user_ids = [e.user_id for e in board.entries]
        assert "u5" not in user_ids  # Epsilon only has 5 trades


class TestFeedManager:
    """Test social feed manager."""

    def test_create_post(self):
        mgr = FeedManager()
        post = mgr.create_post(
            "u1", "TraderJoe", PostType.TRADE_IDEA,
            "AAPL looks bullish above $200",
            symbol="AAPL", target_price=220.0, direction="long",
        )
        assert post.user_id == "u1"
        assert post.symbol == "AAPL"
        assert post.post_type == PostType.TRADE_IDEA

    def test_post_content_limit(self):
        config = SocialConfig(feed=FeedConfig(max_post_length=50))
        mgr = FeedManager(config=config)
        with pytest.raises(ValueError, match="max length"):
            mgr.create_post("u1", "T", PostType.COMMENTARY, "x" * 100)

    def test_daily_post_limit(self):
        config = SocialConfig(feed=FeedConfig(max_posts_per_day=2))
        mgr = FeedManager(config=config)
        mgr.create_post("u1", "T", PostType.COMMENTARY, "Post 1")
        mgr.create_post("u1", "T", PostType.COMMENTARY, "Post 2")
        with pytest.raises(ValueError, match="Daily post limit"):
            mgr.create_post("u1", "T", PostType.COMMENTARY, "Post 3")

    def test_like_post(self):
        mgr = FeedManager()
        post = mgr.create_post("u1", "T", PostType.COMMENTARY, "Test")
        assert mgr.like_post(post.post_id, "u2") is True
        assert post.likes_count == 1

        # No duplicate like
        assert mgr.like_post(post.post_id, "u2") is False
        assert post.likes_count == 1

    def test_comment_on_post(self):
        mgr = FeedManager()
        post = mgr.create_post("u1", "T", PostType.COMMENTARY, "Test")
        interaction = mgr.comment_on_post(post.post_id, "u2", "Great idea!")
        assert interaction is not None
        assert interaction.comment_text == "Great idea!"
        assert post.comments_count == 1

    def test_bookmark_post(self):
        mgr = FeedManager()
        post = mgr.create_post("u1", "T", PostType.COMMENTARY, "Test")
        assert mgr.bookmark_post(post.post_id, "u2") is True
        assert post.bookmarks_count == 1

        bookmarks = mgr.get_bookmarks("u2")
        assert len(bookmarks) == 1

    def test_delete_post(self):
        mgr = FeedManager()
        post = mgr.create_post("u1", "T", PostType.COMMENTARY, "Test")
        assert mgr.delete_post(post.post_id) is True
        assert mgr.get_post(post.post_id) is None

    def test_global_feed(self):
        mgr = FeedManager()
        mgr.create_post("u1", "T1", PostType.TRADE_IDEA, "Buy AAPL", symbol="AAPL")
        mgr.create_post("u2", "T2", PostType.COMMENTARY, "Market thoughts")
        mgr.create_post("u1", "T1", PostType.TRADE_IDEA, "Buy MSFT", symbol="MSFT")

        feed = mgr.get_global_feed()
        assert len(feed) == 3

        feed = mgr.get_global_feed(post_type=PostType.TRADE_IDEA)
        assert len(feed) == 2

        feed = mgr.get_global_feed(symbol="AAPL")
        assert len(feed) == 1

    def test_user_feed(self):
        mgr = FeedManager()
        mgr.create_post("u1", "T1", PostType.COMMENTARY, "Post from u1")
        mgr.create_post("u2", "T2", PostType.COMMENTARY, "Post from u2")
        mgr.create_post("u3", "T3", PostType.COMMENTARY, "Post from u3")

        feed = mgr.get_user_feed(["u1", "u3"])
        assert len(feed) == 2

    def test_trending(self):
        mgr = FeedManager()
        p1 = mgr.create_post("u1", "T", PostType.TRADE_IDEA, "Hot pick")
        p2 = mgr.create_post("u2", "T", PostType.COMMENTARY, "Analysis")

        # p1 gets more engagement
        mgr.like_post(p1.post_id, "u2")
        mgr.like_post(p1.post_id, "u3")
        mgr.comment_on_post(p1.post_id, "u4", "Agree!")

        trending = mgr.get_trending()
        assert trending[0].post_id == p1.post_id
        assert trending[0].is_trending is True

    def test_get_comments(self):
        mgr = FeedManager()
        post = mgr.create_post("u1", "T", PostType.COMMENTARY, "Test")
        mgr.comment_on_post(post.post_id, "u2", "Comment 1")
        mgr.comment_on_post(post.post_id, "u3", "Comment 2")

        comments = mgr.get_comments(post.post_id)
        assert len(comments) == 2

    def test_get_stats(self):
        mgr = FeedManager()
        mgr.create_post("u1", "T", PostType.TRADE_IDEA, "Test")
        mgr.create_post("u1", "T", PostType.COMMENTARY, "Test 2")

        stats = mgr.get_stats()
        assert stats["total_posts"] == 2
        assert stats["posts_by_type"]["trade_idea"] == 1
        assert stats["posts_by_type"]["commentary"] == 1


class TestSocialFullWorkflow:
    """Integration tests for the full social trading workflow."""

    def test_complete_social_workflow(self):
        """End-to-end: profiles, strategies, copy, leaderboard, feed."""
        # 1. Create profiles
        profiles = ProfileManager()
        profiles.create_profile("u1", "AlphaTrader", bio="Pro quant")
        profiles.create_profile("u2", "BetaInvestor", bio="Value investor")
        profiles.create_profile("u3", "GammaTrader", bio="Day trader")

        # 2. Update stats
        profiles.update_stats("u1", PerformanceStats(
            total_return=0.35, sharpe_ratio=2.0, win_rate=0.60,
            total_trades=100, max_drawdown=-0.05,
        ))
        profiles.update_stats("u2", PerformanceStats(
            total_return=0.15, sharpe_ratio=1.2, win_rate=0.55,
            total_trades=50, max_drawdown=-0.10,
        ))
        profiles.update_stats("u3", PerformanceStats(
            total_return=0.25, sharpe_ratio=1.5, win_rate=0.52,
            total_trades=200, max_drawdown=-0.12,
        ))

        # 3. Follow
        profiles.follow("u2", "u1")
        profiles.follow("u3", "u1")
        assert profiles.get_profile("u1").followers_count == 2

        # 4. Publish strategy
        strategies = StrategyManager()
        s1 = strategies.create_strategy(
            "u1", "Momentum Alpha",
            category=StrategyCategory.MOMENTUM,
            tags=["momentum", "quant"],
        )
        strategies.publish_strategy(s1.strategy_id)

        # 5. Copy trading
        copy_engine = CopyTradingEngine()
        rel = copy_engine.start_copying("u2", "u1", s1.strategy_id)
        copy_engine.record_copied_trade(rel.copy_id, 100.0)
        assert rel.total_pnl == 100.0

        # 6. Leaderboard
        leaderboard = LeaderboardManager()
        all_profiles = profiles.get_all_profiles()
        board = leaderboard.compute_leaderboard(
            all_profiles, LeaderboardMetric.TOTAL_RETURN,
        )
        assert board.entries[0].display_name == "AlphaTrader"
        assert board.entries[0].rank == 1

        # 7. Social feed
        feed = FeedManager()
        post = feed.create_post(
            "u1", "AlphaTrader", PostType.TRADE_IDEA,
            "AAPL looking strong above $200, targeting $220",
            symbol="AAPL", target_price=220.0, direction="long",
        )
        feed.like_post(post.post_id, "u2")
        feed.comment_on_post(post.post_id, "u3", "Agree, solid setup!")

        assert post.likes_count == 1
        assert post.comments_count == 1

    def test_strategy_with_performance_tracking(self):
        """Strategy performance recording and stats update."""
        strategies = StrategyManager()
        s = strategies.create_strategy("u1", "Test Strategy")
        strategies.publish_strategy(s.strategy_id)

        # Record daily performance
        for i in range(5):
            strategies.record_performance(
                s.strategy_id,
                daily_return=0.01 * (i + 1),
                nav=100 + i * 2,
                num_positions=5,
            )

        history = strategies.get_performance(s.strategy_id)
        assert len(history) == 5

        # Update aggregate stats
        strategies.update_strategy_stats(
            s.strategy_id,
            PerformanceStats(total_return=0.08, sharpe_ratio=1.5, total_trades=20),
        )
        updated = strategies.get_strategy(s.strategy_id)
        assert updated.stats.total_return == 0.08


class TestSocialModuleImports:
    """Test that all module exports work."""

    def test_top_level_imports(self):
        from src.social import (
            ProfileVisibility, TradingStyle, Badge,
            StrategyStatus, StrategyCategory,
            CopyStatus, CopyMode,
            LeaderboardMetric, LeaderboardPeriod,
            PostType, InteractionType,
            PerformanceStats, TraderProfile, Strategy,
            CopyRelationship, Leaderboard, LeaderboardEntry,
            SocialPost, SocialInteraction, FollowRelationship,
            ProfileManager, StrategyManager,
            CopyTradingEngine, LeaderboardManager, FeedManager,
            BADGE_REQUIREMENTS, DEFAULT_SOCIAL_CONFIG,
        )
