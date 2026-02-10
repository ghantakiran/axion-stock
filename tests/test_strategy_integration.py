"""PRD-173: Strategy Pipeline Integration — tests.

Tests RegimeBridge, FusionBridge, StrategyBridge, and orchestrator wiring.
~45 tests across 5 classes.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from src.bot_pipeline.regime_bridge import RegimeBridge, RegimeState
from src.bot_pipeline.fusion_bridge import FusionBridge, FusionResult
from src.bot_pipeline.strategy_bridge import StrategyBridge, StrategyDecision
from src.regime_adaptive.profiles import ProfileRegistry, StrategyProfile
from src.signal_fusion.collector import RawSignal, SignalSource
from src.signal_fusion.fusion import FusionConfig
from src.strategy_selector.selector import SelectorConfig
from src.trade_executor.executor import ExecutorConfig


# ═════════════════════════════════════════════════════════════════════
# Test RegimeBridge
# ═════════════════════════════════════════════════════════════════════


class TestRegimeBridge:
    """Test regime detection bridge."""

    def test_default_regime(self):
        bridge = RegimeBridge()
        assert bridge.get_current_regime() == "sideways"

    def test_update_regime(self):
        bridge = RegimeBridge()
        bridge.update_regime("bull", confidence=0.8)
        assert bridge.get_current_regime() == "bull"

    def test_confidence_clamped(self):
        bridge = RegimeBridge()
        bridge.update_regime("bear", confidence=1.5)
        state = bridge.get_current_state()
        assert state.confidence == 1.0

    def test_confidence_min_clamped(self):
        bridge = RegimeBridge()
        bridge.update_regime("crisis", confidence=-0.5)
        state = bridge.get_current_state()
        assert state.confidence == 0.0

    def test_get_strategy_profile_bull(self):
        bridge = RegimeBridge()
        bridge.update_regime("bull", confidence=0.9)
        profile = bridge.get_strategy_profile()
        assert profile.regime == "bull"

    def test_get_strategy_profile_for_explicit_regime(self):
        bridge = RegimeBridge()
        profile = bridge.get_strategy_profile("crisis")
        assert profile.regime == "crisis"

    def test_adapt_config_bull(self):
        bridge = RegimeBridge()
        bridge.update_regime("bull", confidence=0.9)
        base = ExecutorConfig()
        adapted = bridge.adapt_config(base)
        # Bull profile has higher max_concurrent_positions
        assert adapted.max_concurrent_positions >= 10

    def test_adapt_config_crisis(self):
        bridge = RegimeBridge()
        bridge.update_regime("crisis", confidence=0.9)
        base = ExecutorConfig()
        adapted = bridge.adapt_config(base)
        # Crisis profile is very conservative
        assert adapted.max_concurrent_positions <= 5

    def test_adapt_preserves_broker(self):
        bridge = RegimeBridge()
        base = ExecutorConfig(primary_broker="alpaca")
        adapted = bridge.adapt_config(base)
        assert adapted.primary_broker == "alpaca"

    def test_regime_history(self):
        bridge = RegimeBridge()
        bridge.update_regime("bull", 0.8)
        bridge.update_regime("bear", 0.6)
        history = bridge.get_regime_history()
        assert len(history) == 2
        assert history[0]["regime"] == "bull"
        assert history[1]["regime"] == "bear"

    def test_regime_state_to_dict(self):
        state = RegimeState(regime="bear", confidence=0.75)
        d = state.to_dict()
        assert d["regime"] == "bear"
        assert d["confidence"] == 0.75


# ═════════════════════════════════════════════════════════════════════
# Test FusionBridge
# ═════════════════════════════════════════════════════════════════════


class TestFusionBridge:
    """Test signal fusion bridge."""

    def _make_signal(self, source: SignalSource, direction: str, strength: float = 75.0):
        return RawSignal(
            source=source,
            symbol="AAPL",
            direction=direction,
            strength=strength,
            confidence=0.8,
        )

    def test_fuse_empty_signals(self):
        bridge = FusionBridge()
        result = bridge.fuse_signals([])
        assert result.direction == "neutral"
        assert result.should_trade is False

    def test_fuse_single_signal(self):
        bridge = FusionBridge()
        signals = [self._make_signal(SignalSource.EMA_CLOUD, "bullish", 80)]
        result = bridge.fuse_signals(signals)
        assert result.symbol == "AAPL"
        assert result.should_trade is False  # Need >= 2 sources

    def test_fuse_two_agreeing_signals(self):
        bridge = FusionBridge(min_score_to_trade=10.0)
        signals = [
            self._make_signal(SignalSource.EMA_CLOUD, "bullish", 90),
            self._make_signal(SignalSource.TECHNICAL, "bullish", 85),
        ]
        result = bridge.fuse_signals(signals)
        assert result.direction == "bullish"
        assert result.composite_score > 0

    def test_fuse_conflicting_signals(self):
        bridge = FusionBridge()
        signals = [
            self._make_signal(SignalSource.EMA_CLOUD, "bullish", 80),
            self._make_signal(SignalSource.SENTIMENT, "bearish", 80),
        ]
        result = bridge.fuse_signals(signals)
        assert result.source_count == 2

    def test_get_fusion_weights(self):
        bridge = FusionBridge()
        weights = bridge.get_fusion_weights()
        assert "ema_cloud" in weights
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_update_weights(self):
        bridge = FusionBridge()
        bridge.update_weights({"ema_cloud": 0.5, "technical": 0.5})
        weights = bridge.get_fusion_weights()
        assert abs(weights["ema_cloud"] - 0.5) < 0.01

    def test_update_weights_with_unknown_source(self):
        bridge = FusionBridge()
        # Should not crash — unknown source is logged and skipped
        bridge.update_weights({"ema_cloud": 0.5, "nonexistent": 0.5})
        weights = bridge.get_fusion_weights()
        assert "ema_cloud" in weights

    def test_fusion_history(self):
        bridge = FusionBridge()
        bridge.fuse_signals([self._make_signal(SignalSource.EMA_CLOUD, "bullish")])
        history = bridge.get_fusion_history()
        assert len(history) == 1

    def test_fusion_result_to_dict(self):
        result = FusionResult(
            symbol="AAPL", direction="bullish", composite_score=55.0,
            confidence=0.7, source_count=3, should_trade=True,
        )
        d = result.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["should_trade"] is True


# ═════════════════════════════════════════════════════════════════════
# Test StrategyBridge
# ═════════════════════════════════════════════════════════════════════


class TestStrategyBridge:
    """Test strategy selector bridge."""

    def _make_price_data(self, n=30, base=100.0):
        import random
        random.seed(42)
        closes = [base + random.uniform(-2, 2) for _ in range(n)]
        highs = [c + random.uniform(0, 1) for c in closes]
        lows = [c - random.uniform(0, 1) for c in closes]
        return highs, lows, closes

    def test_select_strategy_returns_decision(self):
        bridge = StrategyBridge()
        highs, lows, closes = self._make_price_data()
        decision = bridge.select_strategy("AAPL", highs, lows, closes, "bull")
        assert isinstance(decision, StrategyDecision)
        assert decision.ticker == "AAPL"
        assert decision.strategy in ("ema_cloud", "mean_reversion")

    def test_select_strategy_crisis_override(self):
        bridge = StrategyBridge()
        highs, lows, closes = self._make_price_data()
        decision = bridge.select_strategy("AAPL", highs, lows, closes, "crisis")
        assert decision.strategy == "mean_reversion"

    def test_record_outcome(self):
        bridge = StrategyBridge()
        bridge.record_outcome("ema_cloud", 150.0)
        bridge.record_outcome("ema_cloud", -50.0)
        stats = bridge.get_strategy_stats()
        assert stats["ema_cloud"]["signals"] == 2

    def test_decision_history(self):
        bridge = StrategyBridge()
        highs, lows, closes = self._make_price_data()
        bridge.select_strategy("AAPL", highs, lows, closes)
        history = bridge.get_decision_history()
        assert len(history) == 1

    def test_decision_to_dict(self):
        d = StrategyDecision(
            ticker="NVDA", strategy="ema_cloud", confidence=85.0,
            adx_value=30.5, reasoning="Strong trend",
        )
        result = d.to_dict()
        assert result["ticker"] == "NVDA"
        assert result["strategy"] == "ema_cloud"


# ═════════════════════════════════════════════════════════════════════
# Test Orchestrator Integration
# ═════════════════════════════════════════════════════════════════════


class TestOrchestratorStrategyIntegration:
    """Test that orchestrator accepts and uses the new bridge params."""

    def test_orchestrator_accepts_bridges(self):
        from src.bot_pipeline.orchestrator import BotOrchestrator, PipelineConfig

        config = PipelineConfig(
            enable_regime_adaptation=False,
            enable_signal_fusion=False,
            enable_strategy_selection=False,
            enable_alerting=False,
            enable_analytics=False,
        )
        orch = BotOrchestrator(config=config)
        assert orch._regime_bridge is None
        assert orch._fusion_bridge is None
        assert orch._strategy_bridge is None

    def test_orchestrator_with_regime_bridge(self):
        from src.bot_pipeline.orchestrator import BotOrchestrator, PipelineConfig

        bridge = RegimeBridge()
        config = PipelineConfig(
            enable_strategy_selection=False,
            enable_signal_fusion=False,
            enable_alerting=False,
            enable_analytics=False,
        )
        orch = BotOrchestrator(config=config, regime_bridge=bridge)
        assert orch._regime_bridge is bridge

    def test_pipeline_config_new_fields(self):
        from src.bot_pipeline.orchestrator import PipelineConfig

        config = PipelineConfig()
        assert config.enable_strategy_selection is True
        assert config.enable_signal_fusion is True
        assert config.enable_regime_adaptation is True
        assert config.enable_alerting is True
        assert config.enable_analytics is True
        assert config.feedback_adjust_every_n_trades == 50
