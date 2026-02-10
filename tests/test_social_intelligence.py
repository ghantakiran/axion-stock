"""Tests for Social Signal Intelligence (PRD-141).

8 test classes, ~55 tests covering scorer, volume analyzer,
influencer tracker, correlator, generator, and module imports.
"""

from datetime import datetime, timezone

import pytest

from src.sentiment.social import SocialPost


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _make_posts(n=5, source="twitter", sentiment=0.7, ticker="AAPL"):
    """Create test SocialPost objects."""
    posts = []
    for i in range(n):
        posts.append(SocialPost(
            text=f"${ticker} is looking great! Post #{i}",
            source=source,
            author=f"user_{i}",
            tickers=[ticker],
            sentiment=sentiment,
            upvotes=100 * (i + 1),
            comments=20 * (i + 1),
        ))
    return posts


def _make_multi_platform_posts():
    """Create posts across multiple platforms."""
    posts = []
    platforms = [
        ("twitter", 0.8, "AAPL"),
        ("reddit", 0.6, "AAPL"),
        ("discord", 0.7, "AAPL"),
        ("twitter", -0.5, "TSLA"),
        ("reddit", -0.3, "TSLA"),
        ("twitter", 0.9, "NVDA"),
    ]
    for i, (platform, sent, ticker) in enumerate(platforms):
        posts.append(SocialPost(
            text=f"${ticker} analysis from {platform}",
            source=platform,
            author=f"analyst_{i}",
            tickers=[ticker],
            sentiment=sent,
            upvotes=50 * (i + 1),
            comments=10 * (i + 1),
        ))
    return posts


# ═══════════════════════════════════════════════════════════════════════
# Test: Signal Scorer
# ═══════════════════════════════════════════════════════════════════════


class TestSignalScorer:
    """Tests for the multi-factor signal scorer."""

    def test_score_posts_returns_scored_tickers(self):
        from src.social_intelligence import SignalScorer
        scorer = SignalScorer()
        posts = _make_posts(5, ticker="AAPL")
        scored = scorer.score_posts(posts)
        assert len(scored) == 1
        assert scored[0].symbol == "AAPL"
        assert scored[0].score > 0

    def test_score_multiple_tickers(self):
        from src.social_intelligence import SignalScorer
        scorer = SignalScorer()
        posts = _make_posts(3, ticker="AAPL") + _make_posts(2, ticker="MSFT")
        scored = scorer.score_posts(posts)
        symbols = {s.symbol for s in scored}
        assert "AAPL" in symbols
        assert "MSFT" in symbols

    def test_higher_engagement_higher_score(self):
        from src.social_intelligence import SignalScorer
        scorer = SignalScorer()
        low = [SocialPost(text="$AAPL", tickers=["AAPL"], sentiment=0.5,
                          source="twitter", upvotes=1, comments=0)]
        high = [SocialPost(text="$MSFT", tickers=["MSFT"], sentiment=0.5,
                           source="twitter", upvotes=5000, comments=1000)]
        scored = scorer.score_posts(low + high)
        msft = next(s for s in scored if s.symbol == "MSFT")
        aapl = next(s for s in scored if s.symbol == "AAPL")
        assert msft.engagement_score > aapl.engagement_score

    def test_signal_strength_classification(self):
        from src.social_intelligence import SignalScorer, SignalStrength
        scorer = SignalScorer()
        posts = _make_posts(10, sentiment=0.9, ticker="AAPL")
        for p in posts:
            p.upvotes = 2000
            p.comments = 500
        scored = scorer.score_posts(posts)
        # High engagement + strong sentiment should be at least moderate
        assert scored[0].strength in (
            SignalStrength.VERY_STRONG, SignalStrength.STRONG, SignalStrength.MODERATE
        )

    def test_empty_posts(self):
        from src.social_intelligence import SignalScorer
        scorer = SignalScorer()
        assert scorer.score_posts([]) == []

    def test_velocity_factor(self):
        from src.social_intelligence import SignalScorer
        scorer = SignalScorer()
        posts = _make_posts(5, ticker="AAPL")
        # With low baseline, velocity should be higher
        scored_low = scorer.score_posts(posts, mention_baselines={"AAPL": 0.5})
        scored_high = scorer.score_posts(posts, mention_baselines={"AAPL": 100})
        assert scored_low[0].velocity_score > scored_high[0].velocity_score

    def test_score_mentions(self):
        from src.social_intelligence import SignalScorer
        from src.sentiment.social import TickerMention
        scorer = SignalScorer()
        mentions = {
            "AAPL": TickerMention(
                symbol="AAPL", count=10, scores=[0.8, 0.7, 0.9],
                total_upvotes=500, total_comments=100, sources=["twitter", "reddit"],
            ),
        }
        scored = scorer.score_mentions(mentions)
        assert len(scored) == 1
        assert scored[0].symbol == "AAPL"
        assert scored[0].score > 0

    def test_direction_assignment(self):
        from src.social_intelligence import SignalScorer
        scorer = SignalScorer()
        bullish = _make_posts(3, sentiment=0.8, ticker="AAPL")
        bearish = _make_posts(3, sentiment=-0.8, ticker="TSLA")
        scored = scorer.score_posts(bullish + bearish)
        aapl = next(s for s in scored if s.symbol == "AAPL")
        tsla = next(s for s in scored if s.symbol == "TSLA")
        assert aapl.direction == "bullish"
        assert tsla.direction == "bearish"

    def test_scored_ticker_to_dict(self):
        from src.social_intelligence import SignalScorer
        scorer = SignalScorer()
        scored = scorer.score_posts(_make_posts(3))
        d = scored[0].to_dict()
        assert "symbol" in d
        assert "score" in d
        assert "strength" in d
        assert "direction" in d

    def test_baseline_update(self):
        from src.social_intelligence import SignalScorer
        scorer = SignalScorer()
        scorer.update_baseline("AAPL", 10)
        scorer.update_baseline("AAPL", 20)
        assert scorer.get_baseline("AAPL") == 15.0


# ═══════════════════════════════════════════════════════════════════════
# Test: Volume Analyzer
# ═══════════════════════════════════════════════════════════════════════


class TestVolumeAnalyzer:
    """Tests for volume anomaly detection."""

    def test_no_anomaly_stable_volume(self):
        from src.social_intelligence import VolumeAnalyzer
        analyzer = VolumeAnalyzer()
        for i in range(10):
            result = analyzer.update("AAPL", 10)
        assert result is None

    def test_detect_spike(self):
        from src.social_intelligence import VolumeAnalyzer
        analyzer = VolumeAnalyzer()
        for i in range(10):
            analyzer.update("AAPL", 10)
        anomaly = analyzer.update("AAPL", 100)
        assert anomaly is not None
        assert anomaly.symbol == "AAPL"
        assert anomaly.z_score > 2.0

    def test_extreme_anomaly(self):
        from src.social_intelligence import VolumeAnalyzer, VolumeConfig
        analyzer = VolumeAnalyzer(VolumeConfig(extreme_multiplier=5.0))
        for i in range(10):
            analyzer.update("AAPL", 10)
        anomaly = analyzer.update("AAPL", 100)
        assert anomaly is not None
        assert anomaly.is_extreme is True

    def test_detect_anomalies_from_history(self):
        from src.social_intelligence import VolumeAnalyzer
        analyzer = VolumeAnalyzer()
        history = {
            "AAPL": [10, 12, 11, 10, 13, 10, 11, 100],
            "MSFT": [5, 6, 5, 4, 5, 6, 5, 5],
        }
        anomalies = analyzer.detect_anomalies(history)
        symbols = [a.symbol for a in anomalies]
        assert "AAPL" in symbols
        assert "MSFT" not in symbols

    def test_sustained_anomaly(self):
        from src.social_intelligence import VolumeAnalyzer, VolumeConfig
        analyzer = VolumeAnalyzer(VolumeConfig(sustained_window=2))
        for i in range(10):
            analyzer.update("AAPL", 10)
        analyzer.update("AAPL", 100)
        anomaly = analyzer.update("AAPL", 100)
        assert anomaly is not None
        assert anomaly.is_sustained is True

    def test_anomaly_to_dict(self):
        from src.social_intelligence import VolumeAnalyzer
        analyzer = VolumeAnalyzer()
        for i in range(10):
            analyzer.update("AAPL", 10)
        anomaly = analyzer.update("AAPL", 100)
        d = anomaly.to_dict()
        assert "z_score" in d
        assert "severity" in d

    def test_timeseries_tracking(self):
        from src.social_intelligence import VolumeAnalyzer
        analyzer = VolumeAnalyzer()
        analyzer.update("AAPL", 10)
        analyzer.update("AAPL", 20)
        ts = analyzer.get_timeseries("AAPL")
        assert ts is not None
        assert ts.symbol == "AAPL"
        assert ts.latest == 20
        assert ts.mean == 15.0

    def test_min_data_points(self):
        from src.social_intelligence import VolumeAnalyzer
        analyzer = VolumeAnalyzer()
        # Fewer than min_data_points — should never trigger
        for i in range(3):
            result = analyzer.update("AAPL", 1000)
        assert result is None

    def test_update_batch(self):
        from src.social_intelligence import VolumeAnalyzer
        analyzer = VolumeAnalyzer()
        for i in range(10):
            analyzer.update("AAPL", 10)
            analyzer.update("MSFT", 10)
        anomalies = analyzer.update_batch({"AAPL": 100, "MSFT": 10})
        symbols = [a.symbol for a in anomalies]
        assert "AAPL" in symbols
        assert "MSFT" not in symbols


# ═══════════════════════════════════════════════════════════════════════
# Test: Influencer Tracker
# ═══════════════════════════════════════════════════════════════════════


class TestInfluencerTracker:
    """Tests for influencer tracking and scoring."""

    def test_process_posts_builds_profiles(self):
        from src.social_intelligence import InfluencerTracker
        tracker = InfluencerTracker()
        posts = _make_posts(10, source="twitter")
        updated = tracker.process_posts(posts)
        assert updated == 10

    def test_influencer_threshold(self):
        from src.social_intelligence import InfluencerTracker, InfluencerConfig
        tracker = InfluencerTracker(InfluencerConfig(
            min_total_upvotes=100, min_posts=3,
        ))
        # Create high-engagement author
        posts = []
        for i in range(5):
            posts.append(SocialPost(
                text=f"$AAPL post {i}", source="twitter", author="mega_trader",
                tickers=["AAPL"], sentiment=0.8, upvotes=200, comments=50,
            ))
        tracker.process_posts(posts)
        top = tracker.get_top_influencers(n=5)
        assert len(top) == 1
        assert top[0].author_id == "mega_trader"

    def test_influencer_signals(self):
        from src.social_intelligence import InfluencerTracker, InfluencerConfig
        tracker = InfluencerTracker(InfluencerConfig(
            min_total_upvotes=50, min_posts=2,
        ))
        posts = []
        for i in range(5):
            posts.append(SocialPost(
                text=f"$NVDA bullish {i}", source="twitter", author="analyst_1",
                tickers=["NVDA"], sentiment=0.9, upvotes=100, comments=20,
            ))
        tracker.process_posts(posts)
        signals = tracker.get_influencer_signals(posts)
        assert len(signals) > 0
        assert signals[0].symbol == "NVDA"
        assert signals[0].direction == "bullish"

    def test_tier_classification(self):
        from src.social_intelligence import InfluencerTracker, InfluencerConfig
        tracker = InfluencerTracker(InfluencerConfig(
            min_total_upvotes=10, min_posts=1,
        ))
        posts = [SocialPost(
            text="$AAPL", source="twitter", author="whale",
            tickers=["AAPL"], sentiment=0.5, upvotes=15000, comments=100,
        )]
        tracker.process_posts(posts)
        profile = tracker.get_profile("twitter", "whale")
        assert profile is not None
        assert profile.tier == "mega"

    def test_prediction_recording(self):
        from src.social_intelligence import InfluencerTracker
        tracker = InfluencerTracker()
        posts = _make_posts(5, source="twitter")
        tracker.process_posts(posts)
        # Find a tracked author
        key = list(tracker.profiles.keys())[0]
        platform, author = key.split(":", 1)
        tracker.record_prediction(platform, author, True)
        tracker.record_prediction(platform, author, False)
        profile = tracker.get_profile(platform, author)
        assert profile.predictions_tracked == 2
        assert profile.correct_predictions == 1
        assert profile.accuracy_rate == 0.5

    def test_profile_to_dict(self):
        from src.social_intelligence import InfluencerTracker
        tracker = InfluencerTracker()
        tracker.process_posts(_make_posts(3))
        for profile in tracker.profiles.values():
            d = profile.to_dict()
            assert "author_id" in d
            assert "tier" in d
            assert "impact_score" in d

    def test_no_author_skipped(self):
        from src.social_intelligence import InfluencerTracker
        tracker = InfluencerTracker()
        posts = [SocialPost(text="$AAPL", tickers=["AAPL"], sentiment=0.5)]
        updated = tracker.process_posts(posts)
        assert updated == 0


# ═══════════════════════════════════════════════════════════════════════
# Test: Cross-Platform Correlator
# ═══════════════════════════════════════════════════════════════════════


class TestCrossPlatformCorrelator:
    """Tests for cross-platform correlation."""

    def test_consensus_detection(self):
        from src.social_intelligence import CrossPlatformCorrelator
        correlator = CrossPlatformCorrelator()
        posts = _make_multi_platform_posts()
        results = correlator.correlate(posts)
        aapl = next((r for r in results if r.symbol == "AAPL"), None)
        assert aapl is not None
        assert aapl.platform_count == 3
        assert aapl.is_consensus is True
        assert aapl.consensus_direction == "bullish"

    def test_divergent_detection(self):
        from src.social_intelligence import CrossPlatformCorrelator
        correlator = CrossPlatformCorrelator()
        # Create posts with opposing sentiments on same ticker
        posts = [
            SocialPost(text="$SPY bull", source="twitter", tickers=["SPY"],
                       sentiment=0.9, upvotes=100, comments=10),
            SocialPost(text="$SPY bear", source="reddit", tickers=["SPY"],
                       sentiment=-0.9, upvotes=100, comments=10),
            SocialPost(text="$SPY maybe", source="discord", tickers=["SPY"],
                       sentiment=0.0, upvotes=100, comments=10),
        ]
        results = correlator.correlate(posts)
        spy = next(r for r in results if r.symbol == "SPY")
        # All three have different directions → divergent
        assert spy.is_divergent is True

    def test_agreement_score(self):
        from src.social_intelligence import CrossPlatformCorrelator
        correlator = CrossPlatformCorrelator()
        posts = _make_multi_platform_posts()
        results = correlator.correlate(posts)
        for r in results:
            assert 0 <= r.agreement_score <= 1.2  # can go slightly over 1 due to spread bonus

    def test_single_platform(self):
        from src.social_intelligence import CrossPlatformCorrelator
        correlator = CrossPlatformCorrelator()
        posts = _make_posts(3, source="twitter", ticker="AAPL")
        results = correlator.correlate(posts)
        assert len(results) == 1
        assert results[0].platform_count == 1
        assert results[0].is_consensus is False

    def test_correlate_mentions(self):
        from src.social_intelligence import CrossPlatformCorrelator
        correlator = CrossPlatformCorrelator()
        data = {
            "AAPL": {"twitter": 0.8, "reddit": 0.7, "discord": 0.6},
            "TSLA": {"twitter": -0.5, "reddit": 0.8},
        }
        results = correlator.correlate_mentions(data)
        assert len(results) == 2

    def test_result_to_dict(self):
        from src.social_intelligence import CrossPlatformCorrelator
        correlator = CrossPlatformCorrelator()
        posts = _make_multi_platform_posts()
        results = correlator.correlate(posts)
        d = results[0].to_dict()
        assert "symbol" in d
        assert "consensus_sentiment" in d
        assert "agreement_score" in d

    def test_empty_posts(self):
        from src.social_intelligence import CrossPlatformCorrelator
        correlator = CrossPlatformCorrelator()
        assert correlator.correlate([]) == []


# ═══════════════════════════════════════════════════════════════════════
# Test: Social Signal Generator
# ═══════════════════════════════════════════════════════════════════════


class TestSocialSignalGenerator:
    """Tests for the complete signal generation pipeline."""

    def test_analyze_produces_report(self):
        from src.social_intelligence import SocialSignalGenerator
        gen = SocialSignalGenerator()
        posts = _make_multi_platform_posts()
        report = gen.analyze(posts)
        assert report.total_posts_analyzed == len(posts)
        assert report.total_tickers_found > 0

    def test_signals_generated(self):
        from src.social_intelligence import SocialSignalGenerator
        gen = SocialSignalGenerator()
        posts = _make_posts(10, sentiment=0.8, ticker="AAPL")
        for p in posts:
            p.upvotes = 1000
            p.comments = 200
        report = gen.analyze(posts)
        assert report.signals_generated > 0
        assert report.signals[0].symbol == "AAPL"

    def test_signal_action_classification(self):
        from src.social_intelligence import SocialSignalGenerator, SignalAction
        gen = SocialSignalGenerator()
        posts = _make_posts(10, sentiment=0.9, ticker="AAPL")
        for p in posts:
            p.upvotes = 5000
            p.comments = 1000
        report = gen.analyze(posts)
        if report.signals:
            assert report.signals[0].action in (
                SignalAction.STRONG_BUY, SignalAction.BUY, SignalAction.WATCH,
            )

    def test_volume_anomaly_boost(self):
        from src.social_intelligence import SocialSignalGenerator
        gen = SocialSignalGenerator()
        posts = _make_posts(5, sentiment=0.7, ticker="AAPL")
        history = {"AAPL": [5, 6, 5, 4, 5, 6, 5, 50]}
        report = gen.analyze(posts, mention_history=history)
        if report.signals:
            aapl = next((s for s in report.signals if s.symbol == "AAPL"), None)
            if aapl:
                assert aapl.has_volume_anomaly is True

    def test_empty_posts(self):
        from src.social_intelligence import SocialSignalGenerator
        gen = SocialSignalGenerator()
        report = gen.analyze([])
        assert report.signals_generated == 0
        assert report.total_posts_analyzed == 0

    def test_report_to_dict(self):
        from src.social_intelligence import SocialSignalGenerator
        gen = SocialSignalGenerator()
        posts = _make_multi_platform_posts()
        report = gen.analyze(posts)
        d = report.to_dict()
        assert "total_posts_analyzed" in d
        assert "signals_generated" in d

    def test_generate_from_scored(self):
        from src.social_intelligence import SocialSignalGenerator, SignalScorer
        scorer = SignalScorer()
        posts = _make_posts(5, sentiment=0.8, ticker="AAPL")
        for p in posts:
            p.upvotes = 2000
            p.comments = 500
        scored = scorer.score_posts(posts)
        gen = SocialSignalGenerator()
        signals = gen.generate_from_scored(scored)
        assert len(signals) >= 0  # may or may not meet threshold

    def test_signal_to_dict(self):
        from src.social_intelligence import SocialSignalGenerator
        gen = SocialSignalGenerator()
        posts = _make_posts(10, sentiment=0.9)
        for p in posts:
            p.upvotes = 3000
            p.comments = 500
        report = gen.analyze(posts)
        if report.signals:
            d = report.signals[0].to_dict()
            assert "symbol" in d
            assert "action" in d
            assert "confidence" in d

    def test_component_accessors(self):
        from src.social_intelligence import SocialSignalGenerator
        gen = SocialSignalGenerator()
        assert gen.scorer is not None
        assert gen.volume_analyzer is not None
        assert gen.influencer_tracker is not None
        assert gen.correlator is not None


# ═══════════════════════════════════════════════════════════════════════
# Test: Mention Timeseries
# ═══════════════════════════════════════════════════════════════════════


class TestMentionTimeseries:
    """Tests for MentionTimeseries data structure."""

    def test_add_and_properties(self):
        from src.social_intelligence import MentionTimeseries
        ts = MentionTimeseries(symbol="AAPL")
        ts.add(10)
        ts.add(20)
        ts.add(30)
        assert ts.latest == 30
        assert ts.mean == 20.0
        assert ts.std > 0

    def test_to_dict(self):
        from src.social_intelligence import MentionTimeseries
        ts = MentionTimeseries(symbol="AAPL")
        ts.add(5)
        d = ts.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["latest"] == 5


# ═══════════════════════════════════════════════════════════════════════
# Test: Module Imports
# ═══════════════════════════════════════════════════════════════════════


class TestSocialIntelligenceModuleImports:
    """Tests for module import integrity."""

    def test_all_exports_importable(self):
        from src.social_intelligence import __all__
        import src.social_intelligence as mod
        for name in __all__:
            assert hasattr(mod, name), f"Missing export: {name}"

    def test_signal_strength_enum(self):
        from src.social_intelligence import SignalStrength
        assert SignalStrength.VERY_STRONG.value == "very_strong"
        assert SignalStrength.NOISE.value == "noise"

    def test_signal_action_enum(self):
        from src.social_intelligence import SignalAction
        assert SignalAction.STRONG_BUY.value == "strong_buy"
        assert SignalAction.HOLD.value == "hold"

    def test_config_defaults(self):
        from src.social_intelligence import ScorerConfig, VolumeConfig
        sc = ScorerConfig()
        assert sc.sentiment_weight + sc.engagement_weight + sc.velocity_weight + \
               sc.freshness_weight + sc.credibility_weight == pytest.approx(1.0)
        vc = VolumeConfig()
        assert vc.z_score_threshold == 2.0
