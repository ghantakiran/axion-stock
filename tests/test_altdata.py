"""Tests for Alternative Data module."""

import pytest
import numpy as np
from datetime import datetime

from src.altdata.config import (
    DataSource,
    SignalQuality,
    SentimentSource,
    SatelliteType,
    SatelliteConfig,
    WebTrafficConfig,
    SocialConfig,
    ScoringConfig,
    AltDataConfig,
    DEFAULT_CONFIG,
)
from src.altdata.models import (
    SatelliteSignal,
    WebTrafficSnapshot,
    SocialMention,
    SocialSentiment,
    AltDataSignal,
    AltDataComposite,
)
from src.altdata.satellite import SatelliteAnalyzer
from src.altdata.webtraffic import WebTrafficAnalyzer
from src.altdata.social import SocialSentimentAggregator
from src.altdata.scoring import AltDataScorer


# ─── Config Tests ───────────────────────────────────────────────


class TestAltdataConfig:
    def test_enums(self):
        assert DataSource.SATELLITE.value == "satellite"
        assert SignalQuality.HIGH.value == "high"
        assert SentimentSource.REDDIT.value == "reddit"
        assert SatelliteType.PARKING_LOT.value == "parking_lot"

    def test_default_config(self):
        cfg = DEFAULT_CONFIG
        assert cfg.satellite.anomaly_threshold == 2.0
        assert cfg.web_traffic.growth_window == 7
        assert cfg.social.min_mentions == 5
        assert cfg.scoring.min_sources == 2

    def test_satellite_config_defaults(self):
        cfg = SatelliteConfig()
        assert cfg.min_observations == 5
        assert cfg.lookback_days == 90
        assert cfg.trend_min_points == 3

    def test_social_config_weights(self):
        cfg = SocialConfig()
        total = sum(cfg.source_weights.values())
        assert abs(total - 1.0) < 0.01

    def test_scoring_config_weights(self):
        cfg = ScoringConfig()
        total = sum(cfg.source_weights.values())
        assert abs(total - 1.0) < 0.01


# ─── Model Tests ────────────────────────────────────────────────


class TestAltdataModels:
    def test_satellite_signal_properties(self):
        sig = SatelliteSignal(
            symbol="WMT", satellite_type=SatelliteType.PARKING_LOT,
            raw_value=850, z_score=1.5,
        )
        assert sig.signal_strength == 1.5
        assert sig.direction == "bullish"

    def test_satellite_signal_bearish(self):
        sig = SatelliteSignal(
            symbol="WMT", satellite_type=SatelliteType.PARKING_LOT,
            raw_value=500, z_score=-1.2,
        )
        assert sig.direction == "bearish"

    def test_satellite_signal_neutral(self):
        sig = SatelliteSignal(
            symbol="WMT", satellite_type=SatelliteType.PARKING_LOT,
            raw_value=700, z_score=0.2,
        )
        assert sig.direction == "neutral"

    def test_web_traffic_conversion_proxy(self):
        snap = WebTrafficSnapshot(
            symbol="AMZN", domain="amazon.com",
            bounce_rate=0.3, avg_duration=180,
        )
        proxy = snap.conversion_proxy
        assert 0 < proxy < 1

    def test_web_traffic_high_bounce(self):
        snap = WebTrafficSnapshot(
            symbol="X", domain="x.com", bounce_rate=1.0,
        )
        assert snap.conversion_proxy == 0.0

    def test_social_mention_sentiment(self):
        m = SocialMention(symbol="AAPL", source=SentimentSource.REDDIT, sentiment=0.8)
        assert m.is_bullish
        assert not m.is_bearish

    def test_social_sentiment_net(self):
        s = SocialSentiment(
            symbol="AAPL", source=SentimentSource.TWITTER,
            bullish_pct=0.6, bearish_pct=0.2,
        )
        assert abs(s.net_sentiment - 0.4) < 0.001
        assert abs(s.neutral_pct - 0.2) < 0.001

    def test_alt_data_signal_actionable(self):
        sig = AltDataSignal(
            symbol="AAPL", source=DataSource.SOCIAL,
            quality=SignalQuality.HIGH,
        )
        assert sig.is_actionable

    def test_alt_data_signal_not_actionable(self):
        sig = AltDataSignal(
            symbol="AAPL", source=DataSource.SOCIAL,
            quality=SignalQuality.NOISE,
        )
        assert not sig.is_actionable

    def test_composite_consensus(self):
        signals = [
            AltDataSignal(symbol="AAPL", source=DataSource.SATELLITE, raw_score=0.5),
            AltDataSignal(symbol="AAPL", source=DataSource.SOCIAL, raw_score=0.3),
            AltDataSignal(symbol="AAPL", source=DataSource.WEB_TRAFFIC, raw_score=-0.1),
        ]
        comp = AltDataComposite(symbol="AAPL", signals=signals)
        assert comp.has_consensus  # 2 of 3 positive > 0.6


# ─── Satellite Analyzer Tests ──────────────────────────────────


class TestSatelliteAnalyzer:
    def _make_analyzer(self) -> SatelliteAnalyzer:
        return SatelliteAnalyzer(SatelliteConfig(min_observations=3))

    def test_insufficient_data(self):
        sa = self._make_analyzer()
        sa.add_observation("WMT", SatelliteType.PARKING_LOT, 100)
        result = sa.analyze("WMT", SatelliteType.PARKING_LOT)
        assert result.raw_value == 0.0

    def test_basic_analysis(self):
        sa = self._make_analyzer()
        for v in [100, 110, 105, 120, 130]:
            sa.add_observation("WMT", SatelliteType.PARKING_LOT, v)
        result = sa.analyze("WMT", SatelliteType.PARKING_LOT)
        assert result.raw_value == 130
        assert result.z_score > 0
        assert result.normalized_value > 0.5

    def test_anomaly_detection(self):
        sa = SatelliteAnalyzer(SatelliteConfig(min_observations=3, anomaly_threshold=1.5))
        for v in [100, 100, 100, 100, 200]:
            sa.add_observation("XOM", SatelliteType.OIL_STORAGE, v)
        result = sa.analyze("XOM", SatelliteType.OIL_STORAGE)
        assert result.is_anomaly

    def test_trend_positive(self):
        sa = self._make_analyzer()
        for v in [10, 20, 30, 40, 50]:
            sa.add_observation("WMT", SatelliteType.PARKING_LOT, v)
        result = sa.analyze("WMT", SatelliteType.PARKING_LOT)
        assert result.trend > 0

    def test_analyze_all(self):
        sa = self._make_analyzer()
        for v in [100, 110, 120]:
            sa.add_observation("WMT", SatelliteType.PARKING_LOT, v)
            sa.add_observation("WMT", SatelliteType.CONSTRUCTION, v)
        results = sa.analyze_all("WMT")
        assert len(results) == 2

    def test_reset(self):
        sa = self._make_analyzer()
        for v in [100, 110, 120]:
            sa.add_observation("WMT", SatelliteType.PARKING_LOT, v)
        sa.reset()
        assert sa.get_observations("WMT", SatelliteType.PARKING_LOT) == []


# ─── Web Traffic Analyzer Tests ────────────────────────────────


class TestWebTrafficAnalyzer:
    def _make_analyzer(self) -> WebTrafficAnalyzer:
        return WebTrafficAnalyzer(WebTrafficConfig(growth_window=3, momentum_window=5))

    def test_empty_analysis(self):
        wt = self._make_analyzer()
        result = wt.analyze("AMZN")
        assert result.domain == ""
        assert result.visits == 0

    def test_basic_analysis(self):
        wt = self._make_analyzer()
        wt.add_snapshot("AMZN", "amazon.com", visits=1000, bounce_rate=0.3, avg_duration=120)
        result = wt.analyze("AMZN")
        assert result.visits == 1000
        assert result.engagement_score > 0

    def test_growth_rate(self):
        wt = self._make_analyzer()
        wt.add_snapshot("AMZN", "amazon.com", visits=1000)
        wt.add_snapshot("AMZN", "amazon.com", visits=1100)
        wt.add_snapshot("AMZN", "amazon.com", visits=1200)
        wt.add_snapshot("AMZN", "amazon.com", visits=1500)
        result = wt.analyze("AMZN")
        assert result.growth_rate > 0

    def test_engagement_score_range(self):
        wt = self._make_analyzer()
        wt.add_snapshot("X", "x.com", visits=500, bounce_rate=0.5, avg_duration=60)
        result = wt.analyze("X")
        assert 0 <= result.engagement_score <= 1

    def test_momentum_computation(self):
        wt = self._make_analyzer()
        for i in range(6):
            wt.add_snapshot("AMZN", "amazon.com", visits=1000 + i * 200)
        result = wt.analyze("AMZN")
        assert result.momentum > 0

    def test_is_growing(self):
        wt = self._make_analyzer()
        wt.add_snapshot("AMZN", "amazon.com", visits=1000)
        wt.add_snapshot("AMZN", "amazon.com", visits=1100)
        wt.add_snapshot("AMZN", "amazon.com", visits=1200)
        result = wt.analyze("AMZN")
        assert result.is_growing

    def test_reset(self):
        wt = self._make_analyzer()
        wt.add_snapshot("AMZN", "amazon.com", visits=1000)
        wt.reset()
        assert wt.get_history("AMZN") == []


# ─── Social Sentiment Tests ────────────────────────────────────


class TestSocialSentimentAggregator:
    def _make_aggregator(self) -> SocialSentimentAggregator:
        return SocialSentimentAggregator(SocialConfig(min_mentions=3))

    def _add_mentions(
        self, agg: SocialSentimentAggregator, symbol: str,
        source: SentimentSource, sentiments: list[float],
    ) -> None:
        for s in sentiments:
            agg.add_mention(SocialMention(symbol=symbol, source=source, sentiment=s))

    def test_insufficient_mentions(self):
        agg = self._make_aggregator()
        agg.add_mention(SocialMention(symbol="AAPL", source=SentimentSource.REDDIT, sentiment=0.5))
        result = agg.analyze("AAPL", SentimentSource.REDDIT)
        assert result.mentions == 0

    def test_basic_analysis(self):
        agg = self._make_aggregator()
        self._add_mentions(agg, "AAPL", SentimentSource.REDDIT, [0.8, 0.6, 0.3, -0.2, 0.5])
        result = agg.analyze("AAPL", SentimentSource.REDDIT)
        assert result.mentions == 5
        assert result.sentiment_score > 0
        assert result.bullish_pct > 0

    def test_bearish_sentiment(self):
        agg = self._make_aggregator()
        self._add_mentions(agg, "GME", SentimentSource.TWITTER, [-0.8, -0.6, -0.5, -0.3])
        result = agg.analyze("GME", SentimentSource.TWITTER)
        assert result.sentiment_score < 0
        assert result.bearish_pct > 0.5

    def test_aggregate_cross_source(self):
        agg = self._make_aggregator()
        self._add_mentions(agg, "AAPL", SentimentSource.REDDIT, [0.5, 0.6, 0.7])
        self._add_mentions(agg, "AAPL", SentimentSource.TWITTER, [0.3, 0.4, 0.5])
        result = agg.aggregate("AAPL")
        assert result.mentions == 6
        assert result.sentiment_score > 0

    def test_aggregate_empty(self):
        agg = self._make_aggregator()
        result = agg.aggregate("XYZ")
        assert result.mentions == 0

    def test_get_mentions_filtered(self):
        agg = self._make_aggregator()
        self._add_mentions(agg, "AAPL", SentimentSource.REDDIT, [0.5, 0.6])
        self._add_mentions(agg, "AAPL", SentimentSource.TWITTER, [0.3])
        reddit = agg.get_mentions("AAPL", SentimentSource.REDDIT)
        assert len(reddit) == 2

    def test_reset(self):
        agg = self._make_aggregator()
        self._add_mentions(agg, "AAPL", SentimentSource.REDDIT, [0.5, 0.6, 0.7])
        agg.reset()
        assert agg.get_mentions("AAPL") == []


# ─── Alt Data Scorer Tests ─────────────────────────────────────


class TestAltDataScorer:
    def test_score_satellite_empty(self):
        scorer = AltDataScorer()
        result = scorer.score_satellite([])
        assert result.signal_strength == 0.0

    def test_score_satellite(self):
        scorer = AltDataScorer()
        signals = [
            SatelliteSignal(symbol="WMT", satellite_type=SatelliteType.PARKING_LOT,
                            raw_value=130, z_score=1.5),
            SatelliteSignal(symbol="WMT", satellite_type=SatelliteType.CONSTRUCTION,
                            raw_value=80, z_score=0.8),
        ]
        result = scorer.score_satellite(signals)
        assert result.symbol == "WMT"
        assert result.source == DataSource.SATELLITE
        assert result.signal_strength > 0
        assert result.raw_score > 0

    def test_score_web_traffic_empty(self):
        scorer = AltDataScorer()
        snap = WebTrafficSnapshot(symbol="X", domain="")
        result = scorer.score_web_traffic(snap)
        assert result.signal_strength == 0.0

    def test_score_web_traffic(self):
        scorer = AltDataScorer()
        snap = WebTrafficSnapshot(
            symbol="AMZN", domain="amazon.com",
            growth_rate=25.0, engagement_score=0.7,
        )
        result = scorer.score_web_traffic(snap)
        assert result.signal_strength > 0
        assert result.source == DataSource.WEB_TRAFFIC

    def test_score_social_empty(self):
        scorer = AltDataScorer()
        sent = SocialSentiment(symbol="X", source=SentimentSource.REDDIT)
        result = scorer.score_social(sent)
        assert result.signal_strength == 0.0

    def test_score_social(self):
        scorer = AltDataScorer()
        sent = SocialSentiment(
            symbol="AAPL", source=SentimentSource.REDDIT,
            mentions=100, sentiment_score=0.6,
            bullish_pct=0.7, bearish_pct=0.1,
        )
        result = scorer.score_social(sent)
        assert result.signal_strength > 0
        assert result.source == DataSource.SOCIAL

    def test_score_social_spike_boost(self):
        scorer = AltDataScorer()
        sent = SocialSentiment(
            symbol="GME", source=SentimentSource.REDDIT,
            mentions=500, sentiment_score=0.4,
            bullish_pct=0.6, bearish_pct=0.1,
            is_spike=True,
        )
        result = scorer.score_social(sent)
        # Spike should boost strength
        assert result.signal_strength >= 0.4

    def test_composite_single_source(self):
        scorer = AltDataScorer()
        social = AltDataSignal(
            symbol="AAPL", source=DataSource.SOCIAL,
            signal_strength=0.6, quality=SignalQuality.MEDIUM,
            confidence=0.7, raw_score=0.5,
        )
        result = scorer.composite("AAPL", social_signal=social)
        assert result.n_sources == 1
        assert result.composite != 0

    def test_composite_multi_source(self):
        scorer = AltDataScorer()
        sat = AltDataSignal(
            symbol="WMT", source=DataSource.SATELLITE,
            signal_strength=0.8, quality=SignalQuality.HIGH,
            confidence=0.9, raw_score=0.7,
        )
        web = AltDataSignal(
            symbol="WMT", source=DataSource.WEB_TRAFFIC,
            signal_strength=0.5, quality=SignalQuality.MEDIUM,
            confidence=0.6, raw_score=0.3,
        )
        social = AltDataSignal(
            symbol="WMT", source=DataSource.SOCIAL,
            signal_strength=0.6, quality=SignalQuality.MEDIUM,
            confidence=0.7, raw_score=0.4,
        )
        result = scorer.composite("WMT", satellite_signal=sat, web_signal=web, social_signal=social)
        assert result.n_sources == 3
        assert result.composite > 0
        assert result.confidence > 0
        assert len(result.signals) == 3

    def test_composite_empty(self):
        scorer = AltDataScorer()
        result = scorer.composite("XYZ")
        assert result.n_sources == 0
        assert result.composite == 0.0

    def test_quality_assessment(self):
        scorer = AltDataScorer()
        assert scorer._assess_quality(0.9, 2) == SignalQuality.HIGH
        assert scorer._assess_quality(0.5, 2) == SignalQuality.MEDIUM
        assert scorer._assess_quality(0.3, 2) == SignalQuality.LOW
        assert scorer._assess_quality(0.05, 1) == SignalQuality.NOISE
