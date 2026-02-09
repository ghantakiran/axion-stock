"""Tests for Influencer Intelligence Platform (PRD-152).

Tests: InfluencerDiscovery, PerformanceLedger, NetworkAnalyzer,
InfluencerAlertBridge — all with mock social post data.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest

from src.influencer_intel.discovery import (
    CandidateProfile,
    DiscoveryConfig,
    DiscoveryResult,
    InfluencerDiscovery,
)
from src.influencer_intel.ledger import (
    InfluencerReport,
    LedgerConfig,
    PerformanceLedger,
    PerformanceStats,
    PredictionRecord,
)
from src.influencer_intel.network import (
    CommunityCluster,
    InfluencerNode,
    NetworkAnalyzer,
    NetworkConfig,
    NetworkReport,
)
from src.influencer_intel.alerts import (
    AlertConfig,
    AlertPriority,
    InfluencerAlert,
    InfluencerAlertBridge,
)


# ── Helpers ───────────────────────────────────────────────────────────


@dataclass
class _MockPost:
    """Mock social post for testing."""
    author: str = ""
    source: str = "twitter"
    upvotes: int = 100
    comments: int = 10
    sentiment: float = 0.5
    tickers: list = field(default_factory=list)
    text: str = "test post"
    timestamp: str = ""


@dataclass
class _MockSignal:
    """Mock influencer signal for testing."""
    author_id: str = ""
    platform: str = "twitter"
    symbol: str = "AAPL"
    sentiment: float = 0.5
    direction: str = "bullish"
    impact_score: float = 0.7
    tier: str = "macro"


def _make_posts(authors, n_per_author=5, tickers=None, upvotes=200):
    """Generate mock posts for multiple authors."""
    posts = []
    tickers = tickers or ["AAPL", "TSLA", "NVDA"]
    now = datetime.now(timezone.utc)

    for author in authors:
        for i in range(n_per_author):
            ts = (now - timedelta(hours=n_per_author * 4 - i * 4)).isoformat()
            posts.append(_MockPost(
                author=author,
                source="twitter",
                upvotes=upvotes,
                sentiment=0.3 + i * 0.1,
                tickers=tickers[:2] if i % 2 == 0 else tickers[1:],
                timestamp=ts,
            ))
    return posts


# ── TestDiscoveryConfig ──────────────────────────────────────────────


class TestDiscoveryConfig:
    """Test DiscoveryConfig defaults."""

    def test_defaults(self):
        cfg = DiscoveryConfig()
        assert cfg.min_posts == 3
        assert cfg.min_engagement_rate == 0.5
        assert cfg.max_candidates == 50


# ── TestInfluencerDiscovery ──────────────────────────────────────────


class TestInfluencerDiscovery:
    """Test influencer discovery engine."""

    def test_ingest_posts(self):
        discovery = InfluencerDiscovery()
        posts = _make_posts(["alice", "bob"], n_per_author=5)
        count = discovery.ingest_posts(posts)
        assert count == 10

    def test_discover_candidates(self):
        discovery = InfluencerDiscovery()
        posts = _make_posts(["alice", "bob", "carol"], n_per_author=6, upvotes=100)
        discovery.ingest_posts(posts)
        result = discovery.discover()
        assert result.candidate_count > 0
        assert result.total_posts_analyzed == 18
        assert result.total_authors_seen == 3

    def test_min_posts_filter(self):
        discovery = InfluencerDiscovery(DiscoveryConfig(min_posts=10))
        posts = _make_posts(["alice"], n_per_author=5)
        discovery.ingest_posts(posts)
        result = discovery.discover()
        assert result.candidate_count == 0  # Below min_posts

    def test_engagement_rate_filter(self):
        discovery = InfluencerDiscovery(DiscoveryConfig(min_engagement_rate=1000))
        posts = _make_posts(["alice"], n_per_author=5, upvotes=10)
        discovery.ingest_posts(posts)
        result = discovery.discover()
        assert result.candidate_count == 0

    def test_discovery_score_ordering(self):
        discovery = InfluencerDiscovery()
        # High engagement author
        high_posts = _make_posts(["whale"], n_per_author=10, upvotes=500)
        # Low engagement author
        low_posts = _make_posts(["minnow"], n_per_author=5, upvotes=5)
        discovery.ingest_posts(high_posts + low_posts)
        result = discovery.discover()
        if result.candidate_count >= 2:
            assert result.candidates[0].discovery_score >= result.candidates[1].discovery_score

    def test_candidate_to_dict(self):
        c = CandidateProfile(
            author_id="alice", platform="twitter",
            post_count=10, total_upvotes=500,
            engagement_rate=50.0, discovery_score=0.8,
        )
        d = c.to_dict()
        assert d["author_id"] == "alice"
        assert d["discovery_score"] == 0.8

    def test_discovery_result_to_dict(self):
        result = DiscoveryResult(
            candidates=[CandidateProfile(author_id="alice")],
            total_posts_analyzed=100,
        )
        d = result.to_dict()
        assert d["total_posts_analyzed"] == 100
        assert len(d["candidates"]) == 1

    def test_clear(self):
        discovery = InfluencerDiscovery()
        discovery.ingest_posts(_make_posts(["alice"], n_per_author=5))
        discovery.clear()
        result = discovery.discover()
        assert result.candidate_count == 0

    def test_no_author_skipped(self):
        discovery = InfluencerDiscovery()
        posts = [_MockPost(author="", source="twitter")]
        count = discovery.ingest_posts(posts)
        assert count == 0


# ── TestPerformanceLedger ────────────────────────────────────────────


class TestPerformanceLedger:
    """Test performance tracking ledger."""

    def test_record_prediction(self):
        ledger = PerformanceLedger()
        pid = ledger.record_prediction(PredictionRecord(
            author_id="trader1", platform="twitter",
            ticker="AAPL", direction="bullish", entry_price=180.0,
        ))
        assert pid.startswith("pred_")
        assert ledger.prediction_count == 1

    def test_evaluate_prediction(self):
        ledger = PerformanceLedger()
        ledger.record_prediction(PredictionRecord(
            prediction_id="p1", author_id="trader1",
            platform="twitter", ticker="AAPL",
            direction="bullish", entry_price=180.0,
        ))
        record = ledger.evaluate("p1", exit_price=190.0)
        assert record is not None
        assert record.was_correct is True
        assert record.actual_return_pct == pytest.approx(5.56, abs=0.01)

    def test_bearish_prediction_correct(self):
        ledger = PerformanceLedger()
        ledger.record_prediction(PredictionRecord(
            prediction_id="p1", author_id="trader1",
            platform="twitter", ticker="TSLA",
            direction="bearish", entry_price=200.0,
        ))
        record = ledger.evaluate("p1", exit_price=180.0)
        assert record.was_correct is True  # Price went down

    def test_bearish_prediction_incorrect(self):
        ledger = PerformanceLedger()
        ledger.record_prediction(PredictionRecord(
            prediction_id="p1", author_id="trader1",
            platform="twitter", ticker="TSLA",
            direction="bearish", entry_price=200.0,
        ))
        record = ledger.evaluate("p1", exit_price=220.0)
        assert record.was_correct is False

    def test_evaluate_nonexistent(self):
        ledger = PerformanceLedger()
        assert ledger.evaluate("nonexistent", exit_price=100.0) is None

    def test_get_stats(self):
        ledger = PerformanceLedger()
        # 3 bullish, 2 correct
        for i in range(3):
            ledger.record_prediction(PredictionRecord(
                prediction_id=f"p{i}", author_id="trader1",
                platform="twitter", ticker="AAPL",
                direction="bullish", entry_price=180.0,
            ))

        ledger.evaluate("p0", exit_price=190.0)  # Correct
        ledger.evaluate("p1", exit_price=170.0)  # Wrong
        ledger.evaluate("p2", exit_price=195.0)  # Correct

        stats = ledger.get_stats("twitter", "trader1")
        assert stats.total_predictions == 3
        assert stats.correct_predictions == 2
        assert stats.accuracy_rate == pytest.approx(0.667, abs=0.01)

    def test_sector_accuracy(self):
        ledger = PerformanceLedger()
        ledger.record_prediction(PredictionRecord(
            prediction_id="p1", author_id="t1", platform="twitter",
            ticker="AAPL", direction="bullish", entry_price=180.0,
        ))
        ledger.evaluate("p1", exit_price=190.0, sector="technology")

        stats = ledger.get_stats("twitter", "t1")
        assert "technology" in stats.sector_accuracy
        assert stats.sector_accuracy["technology"] == 1.0

    def test_streak_tracking(self):
        ledger = PerformanceLedger()
        # Win, win, loss, win
        for i, (exit_p, direction) in enumerate([
            (190, "bullish"), (195, "bullish"), (170, "bullish"), (200, "bullish"),
        ]):
            ledger.record_prediction(PredictionRecord(
                prediction_id=f"p{i}", author_id="t1", platform="twitter",
                ticker="AAPL", direction=direction, entry_price=180.0,
            ))
            ledger.evaluate(f"p{i}", exit_price=exit_p)

        stats = ledger.get_stats("twitter", "t1")
        assert stats.streak_current == 1  # Last was win
        assert stats.streak_max == 2  # First two wins

    def test_generate_report(self):
        ledger = PerformanceLedger()
        for author in ["t1", "t2"]:
            for i in range(3):
                ledger.record_prediction(PredictionRecord(
                    prediction_id=f"{author}_{i}", author_id=author,
                    platform="twitter", ticker="AAPL",
                    direction="bullish", entry_price=180.0,
                ))
                ledger.evaluate(f"{author}_{i}", exit_price=190.0)

        report = ledger.generate_report()
        assert report.influencer_count == 2
        assert report.total_predictions == 6
        assert report.overall_accuracy == 1.0

    def test_report_top_by_accuracy(self):
        ledger = PerformanceLedger()
        # t1: 5/5 correct, t2: 3/5 correct
        for i in range(5):
            ledger.record_prediction(PredictionRecord(
                prediction_id=f"t1_{i}", author_id="t1", platform="twitter",
                ticker="AAPL", direction="bullish", entry_price=180.0,
            ))
            ledger.evaluate(f"t1_{i}", exit_price=190.0)

        for i in range(5):
            ledger.record_prediction(PredictionRecord(
                prediction_id=f"t2_{i}", author_id="t2", platform="twitter",
                ticker="AAPL", direction="bullish", entry_price=180.0,
            ))
            ledger.evaluate(f"t2_{i}", exit_price=190.0 if i < 3 else 170.0)

        report = ledger.generate_report()
        top = report.get_top_by_accuracy(n=2)
        assert len(top) == 2
        assert top[0].accuracy_rate > top[1].accuracy_rate

    def test_prediction_record_to_dict(self):
        r = PredictionRecord(
            prediction_id="p1", author_id="t1",
            ticker="AAPL", direction="bullish",
        )
        d = r.to_dict()
        assert d["prediction_id"] == "p1"

    def test_performance_stats_to_dict(self):
        s = PerformanceStats(
            author_id="t1", platform="twitter",
            accuracy_rate=0.75, avg_return_pct=2.5,
        )
        d = s.to_dict()
        assert d["accuracy_rate"] == 0.75

    def test_get_prediction(self):
        ledger = PerformanceLedger()
        ledger.record_prediction(PredictionRecord(
            prediction_id="p1", author_id="t1", platform="twitter",
            ticker="AAPL", direction="bullish", entry_price=180.0,
        ))
        assert ledger.get_prediction("p1") is not None
        assert ledger.get_prediction("nonexistent") is None


# ── TestNetworkAnalyzer ──────────────────────────────────────────────


class TestNetworkAnalyzer:
    """Test influencer network analysis."""

    def _make_network_posts(self):
        """Create posts with overlapping ticker mentions."""
        now = datetime.now(timezone.utc)
        posts = []
        # alice and bob share AAPL, TSLA, NVDA (3 shared)
        for i in range(5):
            ts = (now - timedelta(hours=20 - i * 4)).isoformat()
            posts.append(_MockPost(
                author="alice", source="twitter",
                tickers=["AAPL", "TSLA", "NVDA"], sentiment=0.5,
                timestamp=ts,
            ))
            posts.append(_MockPost(
                author="bob", source="twitter",
                tickers=["AAPL", "TSLA", "NVDA"], sentiment=0.4,
                timestamp=ts,
            ))
        # carol shares AAPL, TSLA, NVDA with alice/bob
        for i in range(5):
            ts = (now - timedelta(hours=20 - i * 4)).isoformat()
            posts.append(_MockPost(
                author="carol", source="twitter",
                tickers=["AAPL", "TSLA", "NVDA"], sentiment=0.3,
                timestamp=ts,
            ))
        return posts

    def test_ingest_posts(self):
        analyzer = NetworkAnalyzer()
        posts = self._make_network_posts()
        count = analyzer.ingest_posts(posts)
        assert count == 15

    def test_analyze_finds_cluster(self):
        analyzer = NetworkAnalyzer(NetworkConfig(min_co_mentions=3))
        posts = self._make_network_posts()
        analyzer.ingest_posts(posts)
        report = analyzer.analyze()
        assert report.node_count >= 3
        assert report.cluster_count >= 1

    def test_most_connected(self):
        analyzer = NetworkAnalyzer(NetworkConfig(min_co_mentions=3))
        analyzer.ingest_posts(self._make_network_posts())
        report = analyzer.analyze()
        top = report.get_most_connected(n=1)
        assert len(top) == 1
        assert top[0].degree >= 1

    def test_density(self):
        analyzer = NetworkAnalyzer(NetworkConfig(min_co_mentions=3))
        analyzer.ingest_posts(self._make_network_posts())
        report = analyzer.analyze()
        assert 0 <= report.density <= 1

    def test_no_edges_with_high_threshold(self):
        analyzer = NetworkAnalyzer(NetworkConfig(min_co_mentions=100))
        analyzer.ingest_posts(self._make_network_posts())
        report = analyzer.analyze()
        assert report.total_edges == 0
        assert report.cluster_count == 0

    def test_cluster_coordination_score(self):
        analyzer = NetworkAnalyzer(NetworkConfig(min_co_mentions=3))
        analyzer.ingest_posts(self._make_network_posts())
        report = analyzer.analyze()
        if report.clusters:
            cluster = report.clusters[0]
            assert 0 <= cluster.coordination_score <= 1

    def test_node_to_dict(self):
        n = InfluencerNode(author_id="alice", platform="twitter", degree=3)
        d = n.to_dict()
        assert d["author_id"] == "alice"
        assert d["degree"] == 3

    def test_cluster_to_dict(self):
        c = CommunityCluster(cluster_id=0, members=["a", "b"], size=2)
        d = c.to_dict()
        assert d["size"] == 2

    def test_report_to_dict(self):
        r = NetworkReport(total_edges=5, density=0.3)
        d = r.to_dict()
        assert d["total_edges"] == 5

    def test_most_coordinated_empty(self):
        report = NetworkReport()
        assert report.get_most_coordinated_cluster() is None

    def test_clear(self):
        analyzer = NetworkAnalyzer()
        analyzer.ingest_posts(self._make_network_posts())
        analyzer.clear()
        report = analyzer.analyze()
        assert report.node_count == 0


# ── TestInfluencerAlertBridge ────────────────────────────────────────


class TestInfluencerAlertBridge:
    """Test influencer alert generation."""

    def test_mega_mention_alert(self):
        bridge = InfluencerAlertBridge()
        signals = [_MockSignal(author_id="whale", tier="mega", symbol="AAPL")]
        alerts = bridge.check_signals(signals)
        assert len(alerts) >= 1
        assert any(a.alert_type == "mega_mention" for a in alerts)

    def test_macro_mention_alert(self):
        bridge = InfluencerAlertBridge()
        signals = [_MockSignal(author_id="mid", tier="macro", symbol="TSLA")]
        alerts = bridge.check_signals(signals)
        assert len(alerts) >= 1

    def test_nano_filtered_by_tier(self):
        bridge = InfluencerAlertBridge(AlertConfig(
            min_tier_for_alert="macro",
            min_impact_score=0.9,
        ))
        signals = [_MockSignal(author_id="small", tier="nano", impact_score=0.1)]
        alerts = bridge.check_signals(signals)
        assert len(alerts) == 0

    def test_sentiment_reversal_alert(self):
        bridge = InfluencerAlertBridge(AlertConfig(sentiment_reversal_threshold=0.3))
        # First signal: bullish
        bridge.check_signals([_MockSignal(
            author_id="flipper", tier="macro", sentiment=0.8,
        )])
        # Second signal: bearish (reversal)
        alerts = bridge.check_signals([_MockSignal(
            author_id="flipper", tier="macro", sentiment=-0.5,
        )])
        assert any(a.alert_type == "sentiment_reversal" for a in alerts)

    def test_coordination_alert(self):
        bridge = InfluencerAlertBridge(AlertConfig(coordination_alert_threshold=0.6))
        signals = [
            _MockSignal(author_id="a1", symbol="GME", direction="bullish"),
            _MockSignal(author_id="a2", symbol="GME", direction="bullish"),
            _MockSignal(author_id="a3", symbol="GME", direction="bullish"),
        ]
        alert = bridge.check_coordination("GME", signals)
        assert alert is not None
        assert alert.alert_type == "coordination"
        assert alert.priority == AlertPriority.CRITICAL

    def test_no_coordination_with_few_signals(self):
        bridge = InfluencerAlertBridge()
        signals = [_MockSignal(author_id="a1", symbol="GME")]
        alert = bridge.check_coordination("GME", signals)
        assert alert is None

    def test_alert_to_dict(self):
        a = InfluencerAlert(
            alert_id="test1", alert_type="mega_mention",
            priority=AlertPriority.HIGH, author_id="whale",
            ticker="AAPL",
        )
        d = a.to_dict()
        assert d["alert_id"] == "test1"
        assert d["priority"] == "high"

    def test_get_recent_alerts(self):
        bridge = InfluencerAlertBridge()
        for _ in range(5):
            bridge.check_signals([_MockSignal(tier="mega")])
        recent = bridge.get_recent_alerts(n=3)
        assert len(recent) == 3

    def test_clear(self):
        bridge = InfluencerAlertBridge()
        bridge.check_signals([_MockSignal(tier="mega")])
        bridge.clear()
        assert bridge.alert_count == 0

    def test_alert_priority_enum(self):
        assert AlertPriority.LOW.value == "low"
        assert AlertPriority.CRITICAL.value == "critical"
        assert len(AlertPriority) == 4


# ── TestModuleImports ────────────────────────────────────────────────


class TestModuleImports:
    """Test that all __all__ exports are importable."""

    def test_all_imports(self):
        from src.influencer_intel import __all__ as exports
        import src.influencer_intel as mod
        for name in exports:
            assert hasattr(mod, name), f"Missing export: {name}"

    def test_config_defaults(self):
        assert DiscoveryConfig().lookback_days == 30
        assert LedgerConfig().min_predictions_for_stats == 5
        assert NetworkConfig().min_co_mentions == 3
        assert AlertConfig().min_impact_score == 0.3
