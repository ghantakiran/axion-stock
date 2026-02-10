"""Tests for PRD-147: Autonomous Signal Fusion Agent.

8 test classes, ~50 tests covering collector, fusion, recommender, agent,
and module imports.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from src.signal_fusion.collector import (
    DEMO_TICKERS,
    RawSignal,
    SignalCollector,
    SignalSource,
    VALID_DIRECTIONS,
)
from src.signal_fusion.fusion import (
    DEFAULT_SOURCE_WEIGHTS,
    FusedSignal,
    FusionConfig,
    SignalFusion,
)
from src.signal_fusion.recommender import (
    Action,
    Recommendation,
    RecommenderConfig,
    TradeRecommender,
    STRONG_BUY_THRESHOLD,
    BUY_THRESHOLD,
    SELL_THRESHOLD,
    STRONG_SELL_THRESHOLD,
)
from src.signal_fusion.agent import AgentConfig, AgentState, FusionAgent


# ── TestSignalSource ──────────────────────────────────────────────────


class TestSignalSource:
    """Tests for the SignalSource enum."""

    def test_enum_values(self):
        assert SignalSource.EMA_CLOUD.value == "ema_cloud"
        assert SignalSource.SOCIAL.value == "social"
        assert SignalSource.ML_RANKING.value == "ml_ranking"

    def test_all_eight_sources(self):
        sources = list(SignalSource)
        assert len(sources) == 8
        expected = {
            "ema_cloud", "social", "factor", "ml_ranking",
            "sentiment", "technical", "fundamental", "news",
        }
        assert {s.value for s in sources} == expected

    def test_string_representation(self):
        assert str(SignalSource.FACTOR) == "factor"
        assert str(SignalSource.NEWS) == "news"
        assert str(SignalSource.TECHNICAL) == "technical"


# ── TestRawSignal ─────────────────────────────────────────────────────


class TestRawSignal:
    """Tests for the RawSignal dataclass."""

    def test_creation(self):
        sig = RawSignal(
            source=SignalSource.EMA_CLOUD,
            symbol="AAPL",
            direction="bullish",
            strength=75.0,
        )
        assert sig.source == SignalSource.EMA_CLOUD
        assert sig.symbol == "AAPL"
        assert sig.direction == "bullish"
        assert sig.strength == 75.0

    def test_defaults(self):
        sig = RawSignal(
            source=SignalSource.SOCIAL,
            symbol="NVDA",
            direction="neutral",
            strength=50.0,
        )
        assert sig.confidence == 0.5
        assert isinstance(sig.timestamp, datetime)
        assert isinstance(sig.metadata, dict)
        assert len(sig.signal_id) > 0

    def test_direction_validation(self):
        with pytest.raises(ValueError, match="direction must be"):
            RawSignal(
                source=SignalSource.NEWS,
                symbol="TSLA",
                direction="sideways",
                strength=30.0,
            )

    def test_metadata(self):
        sig = RawSignal(
            source=SignalSource.FACTOR,
            symbol="MSFT",
            direction="bearish",
            strength=60.0,
            metadata={"model": "xgboost", "version": 2},
        )
        assert sig.metadata["model"] == "xgboost"
        assert sig.metadata["version"] == 2

    def test_to_dict(self):
        sig = RawSignal(
            source=SignalSource.SENTIMENT,
            symbol="AMZN",
            direction="bullish",
            strength=80.0,
            confidence=0.9,
        )
        d = sig.to_dict()
        assert d["symbol"] == "AMZN"
        assert d["source"] == "sentiment"
        assert d["direction"] == "bullish"
        assert d["strength"] == 80.0
        assert d["confidence"] == 0.9
        assert "timestamp" in d
        assert "signal_id" in d

    def test_strength_clamped(self):
        sig = RawSignal(
            source=SignalSource.TECHNICAL,
            symbol="AAPL",
            direction="bullish",
            strength=150.0,
        )
        assert sig.strength == 100.0

    def test_confidence_clamped(self):
        sig = RawSignal(
            source=SignalSource.TECHNICAL,
            symbol="AAPL",
            direction="bearish",
            strength=50.0,
            confidence=1.5,
        )
        assert sig.confidence == 1.0


# ── TestSignalCollector ───────────────────────────────────────────────


class TestSignalCollector:
    """Tests for the SignalCollector class."""

    def test_collect_all_demo(self):
        collector = SignalCollector(demo_mode=True)
        signals = collector.collect_all("AAPL")
        assert len(signals) == 8  # one per source
        symbols = {s.symbol for s in signals}
        assert symbols == {"AAPL"}

    def test_collect_from_single_source(self):
        collector = SignalCollector(demo_mode=True)
        signals = collector.collect_from(SignalSource.EMA_CLOUD, "NVDA")
        assert len(signals) == 1
        assert signals[0].source == SignalSource.EMA_CLOUD
        assert signals[0].symbol == "NVDA"

    def test_active_sources(self):
        collector = SignalCollector(
            demo_mode=True,
            active_sources=[SignalSource.EMA_CLOUD, SignalSource.FACTOR],
        )
        active = collector.get_active_sources()
        assert len(active) == 2
        assert SignalSource.EMA_CLOUD in active
        assert SignalSource.FACTOR in active

    def test_collect_from_inactive_source(self):
        collector = SignalCollector(
            demo_mode=True,
            active_sources=[SignalSource.EMA_CLOUD],
        )
        signals = collector.collect_from(SignalSource.SOCIAL, "AAPL")
        assert len(signals) == 0

    def test_multi_symbol(self):
        collector = SignalCollector(demo_mode=True)
        result = collector.collect_multi(["AAPL", "TSLA"])
        assert "AAPL" in result
        assert "TSLA" in result
        assert len(result["AAPL"]) == 8
        assert len(result["TSLA"]) == 8

    def test_collect_all_default_sources(self):
        collector = SignalCollector(demo_mode=True)
        active = collector.get_active_sources()
        assert len(active) == 8


# ── TestFusionConfig ──────────────────────────────────────────────────


class TestFusionConfig:
    """Tests for FusionConfig."""

    def test_defaults(self):
        config = FusionConfig()
        assert config.min_sources == 2
        assert config.agreement_threshold == 0.6
        assert config.decay_minutes == 60.0
        # Weights should be normalized to sum to 1.0
        total = sum(config.source_weights.values())
        assert abs(total - 1.0) < 0.01

    def test_custom_weights(self):
        custom = {SignalSource.EMA_CLOUD: 0.5, SignalSource.FACTOR: 0.5}
        config = FusionConfig(source_weights=custom)
        assert abs(config.get_weight(SignalSource.EMA_CLOUD) - 0.5) < 0.01
        assert abs(config.get_weight(SignalSource.FACTOR) - 0.5) < 0.01

    def test_weight_normalization(self):
        # Weights that don't sum to 1.0 should be normalized
        custom = {
            SignalSource.EMA_CLOUD: 2.0,
            SignalSource.FACTOR: 3.0,
        }
        config = FusionConfig(source_weights=custom)
        total = sum(config.source_weights.values())
        assert abs(total - 1.0) < 0.01
        assert abs(config.get_weight(SignalSource.EMA_CLOUD) - 0.4) < 0.01

    def test_min_sources(self):
        config = FusionConfig(min_sources=3)
        assert config.min_sources == 3


# ── TestSignalFusion ──────────────────────────────────────────────────


class TestSignalFusion:
    """Tests for the SignalFusion engine."""

    def _make_signal(
        self,
        source: SignalSource,
        symbol: str = "AAPL",
        direction: str = "bullish",
        strength: float = 70.0,
        confidence: float = 0.7,
        timestamp: datetime | None = None,
    ) -> RawSignal:
        return RawSignal(
            source=source,
            symbol=symbol,
            direction=direction,
            strength=strength,
            confidence=confidence,
            timestamp=timestamp or datetime.now(timezone.utc),
        )

    def test_single_source(self):
        fusion = SignalFusion()
        signals = [self._make_signal(SignalSource.EMA_CLOUD)]
        result = fusion.fuse(signals)
        assert result.symbol == "AAPL"
        assert result.source_count == 1

    def test_multi_source(self):
        fusion = SignalFusion()
        signals = [
            self._make_signal(SignalSource.EMA_CLOUD, direction="bullish"),
            self._make_signal(SignalSource.FACTOR, direction="bullish"),
            self._make_signal(SignalSource.ML_RANKING, direction="bullish"),
        ]
        result = fusion.fuse(signals)
        assert result.source_count == 3
        assert result.direction == "bullish"

    def test_agreement_calculation(self):
        fusion = SignalFusion()
        signals = [
            self._make_signal(SignalSource.EMA_CLOUD, direction="bullish"),
            self._make_signal(SignalSource.FACTOR, direction="bullish"),
            self._make_signal(SignalSource.ML_RANKING, direction="bearish"),
        ]
        result = fusion.fuse(signals)
        # 2 bullish vs 1 bearish -> bullish consensus
        assert result.direction == "bullish"
        assert len(result.agreeing_sources) == 2
        assert len(result.dissenting_sources) == 1

    def test_time_decay(self):
        config = FusionConfig(decay_minutes=30)
        fusion = SignalFusion(config=config)

        now = datetime.now(timezone.utc)
        old_time = now - timedelta(hours=2)

        fresh_signal = self._make_signal(
            SignalSource.EMA_CLOUD, direction="bullish", strength=80.0, timestamp=now
        )
        stale_signal = self._make_signal(
            SignalSource.FACTOR, direction="bearish", strength=80.0, timestamp=old_time
        )

        result = fusion.fuse([fresh_signal, stale_signal])
        # Fresh bullish should dominate over stale bearish
        assert result.direction == "bullish"
        assert result.composite_score > 0

    def test_composite_score_range(self):
        fusion = SignalFusion()
        # All bullish with high strength
        signals = [
            self._make_signal(src, direction="bullish", strength=100.0, confidence=1.0)
            for src in SignalSource
        ]
        result = fusion.fuse(signals)
        assert -100.0 <= result.composite_score <= 100.0

        # All bearish
        signals2 = [
            self._make_signal(src, direction="bearish", strength=100.0, confidence=1.0)
            for src in SignalSource
        ]
        result2 = fusion.fuse(signals2)
        assert -100.0 <= result2.composite_score <= 100.0

    def test_bullish_consensus(self):
        fusion = SignalFusion()
        signals = [
            self._make_signal(src, direction="bullish", strength=80.0, confidence=0.8)
            for src in list(SignalSource)[:6]
        ]
        result = fusion.fuse(signals)
        assert result.direction == "bullish"
        assert result.composite_score > 0
        assert len(result.agreeing_sources) == 6

    def test_bearish_consensus(self):
        fusion = SignalFusion()
        signals = [
            self._make_signal(src, direction="bearish", strength=85.0, confidence=0.85)
            for src in list(SignalSource)[:5]
        ]
        result = fusion.fuse(signals)
        assert result.direction == "bearish"
        assert result.composite_score < 0

    def test_mixed_signals(self):
        fusion = SignalFusion()
        signals = [
            self._make_signal(SignalSource.EMA_CLOUD, direction="bullish", strength=70.0),
            self._make_signal(SignalSource.FACTOR, direction="bearish", strength=70.0),
            self._make_signal(SignalSource.ML_RANKING, direction="neutral", strength=50.0),
        ]
        result = fusion.fuse(signals)
        assert result.source_count == 3
        assert len(result.dissenting_sources) > 0

    def test_reasoning_text(self):
        fusion = SignalFusion()
        signals = [
            self._make_signal(SignalSource.EMA_CLOUD, direction="bullish"),
            self._make_signal(SignalSource.FACTOR, direction="bearish"),
        ]
        result = fusion.fuse(signals)
        assert len(result.reasoning) >= 2
        # First reasoning line is the summary
        assert "Consensus" in result.reasoning[0]
        assert "Agreement" in result.reasoning[0]

    def test_batch_fuse(self):
        fusion = SignalFusion()
        by_symbol = {
            "AAPL": [
                self._make_signal(SignalSource.EMA_CLOUD, symbol="AAPL", direction="bullish"),
                self._make_signal(SignalSource.FACTOR, symbol="AAPL", direction="bullish"),
            ],
            "TSLA": [
                self._make_signal(SignalSource.EMA_CLOUD, symbol="TSLA", direction="bearish"),
            ],
        }
        results = fusion.fuse_batch(by_symbol)
        assert "AAPL" in results
        assert "TSLA" in results
        assert results["AAPL"].symbol == "AAPL"
        assert results["TSLA"].symbol == "TSLA"

    def test_empty_signals(self):
        fusion = SignalFusion()
        result = fusion.fuse([])
        assert result.direction == "neutral"
        assert result.composite_score == 0.0
        assert result.source_count == 0


# ── TestTradeRecommender ──────────────────────────────────────────────


class TestTradeRecommender:
    """Tests for the TradeRecommender."""

    def _make_fused(
        self,
        symbol: str = "AAPL",
        direction: str = "bullish",
        composite_score: float = 60.0,
        confidence: float = 0.8,
        source_count: int = 5,
        agreeing: int = 4,
    ) -> FusedSignal:
        agreeing_list = [f"source_{i}" for i in range(agreeing)]
        dissenting_list = [f"source_{i}" for i in range(agreeing, source_count)]
        return FusedSignal(
            symbol=symbol,
            direction=direction,
            composite_score=composite_score,
            confidence=confidence,
            source_count=source_count,
            agreeing_sources=agreeing_list,
            dissenting_sources=dissenting_list,
            reasoning=["Test reasoning"],
        )

    def test_strong_buy_threshold(self):
        rec = TradeRecommender()
        fused = self._make_fused(composite_score=55.0, confidence=0.85)
        result = rec.recommend(fused)
        assert result is not None
        assert result.action == Action.STRONG_BUY

    def test_hold_zone(self):
        rec = TradeRecommender()
        fused = self._make_fused(composite_score=5.0, confidence=0.6)
        result = rec.recommend(fused)
        # HOLD actions are still returned but position_size is 0
        assert result is not None
        assert result.action == Action.HOLD
        assert result.position_size_pct == 0.0

    def test_sell_signal(self):
        config = RecommenderConfig(enable_short=True)
        rec = TradeRecommender(config=config)
        fused = self._make_fused(
            direction="bearish", composite_score=-55.0, confidence=0.8
        )
        result = rec.recommend(fused)
        assert result is not None
        assert result.action == Action.STRONG_SELL

    def test_sell_disabled_short(self):
        """Without enable_short, sell signals become HOLD."""
        config = RecommenderConfig(enable_short=False)
        rec = TradeRecommender(config=config)
        fused = self._make_fused(
            direction="bearish", composite_score=-55.0, confidence=0.8
        )
        result = rec.recommend(fused)
        assert result is not None
        assert result.action == Action.HOLD

    def test_position_sizing(self):
        config = RecommenderConfig(max_single_weight=0.10)
        rec = TradeRecommender(config=config)
        fused = self._make_fused(composite_score=60.0, confidence=0.8)
        result = rec.recommend(fused)
        assert result is not None
        # confidence * max_weight * 100 = 0.8 * 0.1 * 100 = 8.0
        assert result.position_size_pct == pytest.approx(8.0)
        assert result.position_size_pct <= 10.0  # max_single_weight * 100

    def test_stop_loss(self):
        rec = TradeRecommender()
        fused = self._make_fused(composite_score=60.0, confidence=0.7)
        result = rec.recommend(fused)
        assert result is not None
        assert 2.0 <= result.stop_loss_pct <= 5.0

    def test_portfolio_ranking(self):
        rec = TradeRecommender()
        fused_signals = {
            "AAPL": self._make_fused("AAPL", composite_score=70.0, confidence=0.9),
            "NVDA": self._make_fused("NVDA", composite_score=30.0, confidence=0.6),
            "TSLA": self._make_fused("TSLA", composite_score=55.0, confidence=0.75),
        }
        recs = rec.recommend_portfolio(fused_signals)
        # Should be ranked by |score| * confidence
        assert len(recs) > 0
        # AAPL (70*0.9=63) should rank above TSLA (55*0.75=41.25)
        symbols = [r.symbol for r in recs]
        assert symbols.index("AAPL") < symbols.index("TSLA")

    def test_max_positions(self):
        config = RecommenderConfig(max_positions=2)
        rec = TradeRecommender(config=config)
        fused_signals = {
            f"SYM{i}": self._make_fused(
                f"SYM{i}", composite_score=50.0 + i, confidence=0.7
            )
            for i in range(5)
        }
        recs = rec.recommend_portfolio(fused_signals)
        assert len(recs) <= 2

    def test_risk_levels(self):
        rec = TradeRecommender()
        # High confidence + high agreement -> low risk
        fused_low = self._make_fused(
            confidence=0.85, source_count=5, agreeing=5
        )
        result_low = rec.recommend(fused_low)
        assert result_low is not None
        assert result_low.risk_level == "low"

        # Low confidence + low agreement -> high risk
        fused_high = self._make_fused(
            confidence=0.3, source_count=5, agreeing=1
        )
        # Need to lower min_confidence to get a rec for this
        config_low = RecommenderConfig(min_confidence=0.1)
        rec_low = TradeRecommender(config=config_low)
        result_high = rec_low.recommend(fused_high)
        assert result_high is not None
        assert result_high.risk_level == "high"

    def test_min_confidence_filter(self):
        config = RecommenderConfig(min_confidence=0.9)
        rec = TradeRecommender(config=config)
        fused = self._make_fused(confidence=0.5)
        result = rec.recommend(fused)
        assert result is None

    def test_recommendation_to_dict(self):
        rec = TradeRecommender()
        fused = self._make_fused(composite_score=55.0, confidence=0.8)
        result = rec.recommend(fused)
        assert result is not None
        d = result.to_dict()
        assert "symbol" in d
        assert "action" in d
        assert "position_size_pct" in d
        assert "reasoning" in d


# ── TestFusionAgent ───────────────────────────────────────────────────


class TestFusionAgent:
    """Tests for the FusionAgent orchestrator."""

    def test_scan_pipeline(self):
        agent = FusionAgent(
            agent_config=AgentConfig(symbols=["AAPL", "NVDA"]),
        )
        state = agent.scan()
        assert state.signals_collected > 0
        assert state.fusions_produced > 0
        assert isinstance(state.last_scan, datetime)

    def test_state_tracking(self):
        agent = FusionAgent(
            agent_config=AgentConfig(symbols=["AAPL"]),
        )
        assert agent.get_state() is None
        agent.scan()
        state = agent.get_state()
        assert state is not None
        assert state.signals_collected > 0

    def test_history(self):
        agent = FusionAgent(
            agent_config=AgentConfig(symbols=["AAPL"]),
        )
        agent.scan()
        agent.scan()
        agent.scan()
        history = agent.get_history(limit=2)
        assert len(history) == 2
        # Most recent first
        assert history[0].last_scan >= history[1].last_scan

    def test_recommendations(self):
        agent = FusionAgent(
            agent_config=AgentConfig(
                symbols=["AAPL", "NVDA", "TSLA"],
                max_recommendations=3,
            ),
            recommender_config=RecommenderConfig(min_confidence=0.0),
        )
        agent.scan()
        recs = agent.get_recommendations()
        assert len(recs) <= 3

    def test_config_defaults(self):
        config = AgentConfig()
        assert config.scan_interval_minutes == 15
        assert config.max_recommendations == 5
        assert config.auto_execute is False
        assert config.paper_mode is True
        assert len(config.symbols) > 0

    def test_paper_mode(self):
        agent = FusionAgent(
            agent_config=AgentConfig(
                symbols=["AAPL"],
                auto_execute=True,
                paper_mode=True,
            ),
            recommender_config=RecommenderConfig(min_confidence=0.0),
        )
        state = agent.scan()
        if state.execution_results:
            for result in state.execution_results:
                assert result["paper_mode"] is True
                assert result["status"] == "simulated"

    def test_state_to_dict(self):
        agent = FusionAgent(
            agent_config=AgentConfig(symbols=["AAPL"]),
        )
        state = agent.scan()
        d = state.to_dict()
        assert "last_scan" in d
        assert "signals_collected" in d
        assert "fusions_produced" in d
        assert "recommendations_count" in d

    def test_no_recommendations_before_scan(self):
        agent = FusionAgent()
        recs = agent.get_recommendations()
        assert recs == []


# ── TestModuleImports ─────────────────────────────────────────────────


class TestSignalFusionModuleImports:
    """Tests that all module exports are accessible."""

    def test_all_exports(self):
        import src.signal_fusion as sf
        expected_exports = [
            "SignalSource", "RawSignal", "SignalCollector",
            "FusionConfig", "FusedSignal", "SignalFusion",
            "Action", "Recommendation", "RecommenderConfig", "TradeRecommender",
            "AgentConfig", "AgentState", "FusionAgent",
        ]
        for name in expected_exports:
            assert hasattr(sf, name), f"Missing export: {name}"

    def test_key_classes(self):
        from src.signal_fusion import (
            SignalCollector,
            SignalFusion,
            TradeRecommender,
            FusionAgent,
        )
        assert SignalCollector is not None
        assert SignalFusion is not None
        assert TradeRecommender is not None
        assert FusionAgent is not None

    def test_enums(self):
        from src.signal_fusion import SignalSource, Action
        assert len(list(SignalSource)) == 8
        assert Action.STRONG_BUY == "STRONG_BUY"
        assert Action.HOLD == "HOLD"
