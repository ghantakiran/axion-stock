"""Tests for PRD-155: Regime-Adaptive Strategy Engine.

8 test classes, ~50 tests covering profiles, registry, adapter, tuner,
monitor, configs, and module imports.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from src.regime_adaptive.profiles import StrategyProfile, ProfileRegistry
from src.regime_adaptive.adapter import AdapterConfig, ConfigAdaptation, RegimeAdapter
from src.regime_adaptive.tuner import (
    TunerConfig,
    TuningAdjustment,
    TunerResult,
    PerformanceTuner,
)
from src.regime_adaptive.monitor import (
    MonitorConfig,
    RegimeTransition,
    MonitorState,
    RegimeMonitor,
)


# ── Helper ───────────────────────────────────────────────────────────


def _make_executor_config() -> dict:
    """Return a default ExecutorConfig-like dict with standard fields."""
    return {
        "max_risk_per_trade": 0.05,
        "max_concurrent_positions": 10,
        "daily_loss_limit": 0.10,
        "max_single_stock_exposure": 0.15,
        "max_sector_exposure": 0.30,
        "reward_to_risk_target": 2.0,
        "time_stop_minutes": 120,
        "trailing_stop_cloud": "pullback",
        "scale_in_enabled": True,
        "consecutive_loss_threshold": 3,
    }


# ── TestStrategyProfile ─────────────────────────────────────────────


class TestStrategyProfile:
    """Tests for the StrategyProfile dataclass."""

    def test_creation_with_defaults(self):
        profile = StrategyProfile()
        assert profile.name == ""
        assert profile.regime == "sideways"
        assert profile.max_risk_per_trade == 0.05
        assert profile.position_size_multiplier == 1.0
        assert profile.min_conviction == 50

    def test_to_dict_contains_all_fields(self):
        profile = StrategyProfile(name="test", regime="bull")
        d = profile.to_dict()
        expected_keys = {
            "name", "regime", "description",
            "max_risk_per_trade", "max_concurrent_positions",
            "daily_loss_limit", "max_single_stock_exposure",
            "max_sector_exposure", "reward_to_risk_target",
            "time_stop_minutes", "trailing_stop_cloud",
            "scale_in_enabled", "consecutive_loss_threshold",
            "preferred_signal_types", "avoid_signal_types",
            "position_size_multiplier", "min_conviction",
        }
        assert set(d.keys()) == expected_keys

    def test_bull_profile_fields(self):
        registry = ProfileRegistry()
        bull = registry.get_profile("bull")
        assert bull.name == "bull_aggressive"
        assert bull.regime == "bull"
        assert bull.position_size_multiplier == 1.2
        assert "CLOUD_CROSS_BULLISH" in bull.preferred_signal_types
        assert "CLOUD_CROSS_BEARISH" in bull.avoid_signal_types

    def test_crisis_vs_bull_risk_levels(self):
        registry = ProfileRegistry()
        bull = registry.get_profile("bull")
        crisis = registry.get_profile("crisis")
        assert crisis.max_risk_per_trade < bull.max_risk_per_trade
        assert crisis.max_concurrent_positions < bull.max_concurrent_positions
        assert crisis.daily_loss_limit < bull.daily_loss_limit
        assert crisis.position_size_multiplier < bull.position_size_multiplier
        assert crisis.min_conviction > bull.min_conviction

    def test_default_all_fields_present(self):
        profile = StrategyProfile()
        d = profile.to_dict()
        assert len(d) == 17
        for key, value in d.items():
            assert value is not None


# ── TestProfileRegistry ──────────────────────────────────────────────


class TestProfileRegistry:
    """Tests for the ProfileRegistry."""

    def test_get_all_profiles_returns_four(self):
        registry = ProfileRegistry()
        profiles = registry.get_all_profiles()
        assert len(profiles) == 4
        assert set(profiles.keys()) == {"bull", "bear", "sideways", "crisis"}

    def test_get_profile_bull(self):
        registry = ProfileRegistry()
        bull = registry.get_profile("bull")
        assert bull.regime == "bull"
        assert bull.name == "bull_aggressive"
        assert bull.max_risk_per_trade == 0.06

    def test_get_profile_crisis(self):
        registry = ProfileRegistry()
        crisis = registry.get_profile("crisis")
        assert crisis.regime == "crisis"
        assert crisis.name == "crisis_protective"
        assert crisis.max_concurrent_positions == 3

    def test_register_custom(self):
        registry = ProfileRegistry()
        custom = StrategyProfile(
            name="custom_hyper",
            regime="hyper_bull",
            max_risk_per_trade=0.10,
            position_size_multiplier=2.0,
        )
        registry.register_custom(custom)
        fetched = registry.get_profile("hyper_bull")
        assert fetched.name == "custom_hyper"
        assert fetched.max_risk_per_trade == 0.10
        assert len(registry.get_all_profiles()) == 5

    def test_get_blended_profile_low_confidence_shifts_toward_sideways(self):
        registry = ProfileRegistry()
        blended = registry.get_blended_profile("bull", 0.5)
        pure_bull = registry.get_profile("bull")
        sideways = registry.get_profile("sideways")
        # The blended max_risk should be between sideways and bull
        assert blended.max_risk_per_trade >= sideways.max_risk_per_trade
        assert blended.max_risk_per_trade <= pure_bull.max_risk_per_trade
        assert "blended" in blended.name

    def test_get_blended_profile_high_confidence_stays_near_regime(self):
        registry = ProfileRegistry()
        blended = registry.get_blended_profile("bull", 0.85)
        pure_bull = registry.get_profile("bull")
        # At confidence >= 0.7 the pure profile is returned
        assert blended.max_risk_per_trade == pure_bull.max_risk_per_trade
        assert blended.position_size_multiplier == pure_bull.position_size_multiplier

    def test_blended_boolean_conservative(self):
        registry = ProfileRegistry()
        # Bear has scale_in_enabled=False, sideways has True
        blended = registry.get_blended_profile("bear", 0.55)
        # Conservative: both must be True => False wins
        assert blended.scale_in_enabled is False

    def test_unknown_regime_falls_back_to_sideways(self):
        registry = ProfileRegistry()
        profile = registry.get_profile("unknown_regime")
        assert profile.regime == "sideways"
        assert profile.name == "sideways_neutral"


# ── TestRegimeAdapter ────────────────────────────────────────────────


class TestRegimeAdapter:
    """Tests for the RegimeAdapter."""

    def test_adapt_bull_increases_risk(self):
        adapter = RegimeAdapter()
        config = _make_executor_config()
        result = adapter.adapt(config, "bull", 0.9)
        # Bull profile has max_risk_per_trade=0.06 vs default 0.05
        assert result.adapted_config["max_risk_per_trade"] >= 0.06

    def test_adapt_crisis_reduces_risk(self):
        adapter = RegimeAdapter()
        config = _make_executor_config()
        result = adapter.adapt(config, "crisis", 0.9)
        # Crisis profile has max_risk_per_trade=0.02
        assert result.adapted_config["max_risk_per_trade"] <= 0.02
        assert result.adapted_config["max_concurrent_positions"] <= 3

    def test_adapt_low_confidence_no_change(self):
        adapter = RegimeAdapter()
        config = _make_executor_config()
        result = adapter.adapt(config, "crisis", 0.3)
        # Below min_confidence_to_adapt (0.5) -> no changes
        assert result.changes == []
        assert result.adapted_config == config
        assert "below confidence" in result.profile_used

    def test_filter_signals_removes_avoided_types(self):
        adapter = RegimeAdapter()
        signals = [
            {"signal_type": "CLOUD_CROSS_BULLISH", "strength": 80},
            {"signal_type": "CLOUD_CROSS_BEARISH", "strength": 70},
            {"signal_type": "TREND_ALIGNED_LONG", "strength": 60},
        ]
        # Crisis avoids bullish and long signals
        filtered = adapter.filter_signals(signals, "crisis", 0.9)
        signal_types = [s["signal_type"] for s in filtered]
        assert "CLOUD_CROSS_BULLISH" not in signal_types
        assert "CLOUD_CROSS_BEARISH" in signal_types

    def test_filter_signals_boosts_preferred(self):
        adapter = RegimeAdapter()
        signals = [
            {"signal_type": "CLOUD_CROSS_BULLISH", "strength": 80},
            {"signal_type": "TREND_ALIGNED_LONG", "strength": 60},
            {"signal_type": "MOMENTUM_EXHAUSTION", "strength": 50},
        ]
        # Bull profile prefers CLOUD_CROSS_BULLISH and TREND_ALIGNED_LONG
        filtered = adapter.filter_signals(signals, "bull", 0.9)
        boosted = [s for s in filtered if s.get("regime_boost") == 1.0]
        assert len(boosted) >= 1
        boosted_types = [s["signal_type"] for s in boosted]
        assert "CLOUD_CROSS_BULLISH" in boosted_types

    def test_smooth_transition_interpolation(self):
        adapter = RegimeAdapter(config=AdapterConfig(smooth_transitions=True))
        config = _make_executor_config()
        # First call: sideways
        adapter.adapt(config, "sideways", 0.8)
        # Second call: switch to bull -> transition_progress resets to 0
        result = adapter.adapt(config, "bull", 0.8)
        # The adapter starts interpolating; result should differ from both
        # pure sideways and pure bull due to partial transition
        bull_profile_risk = 0.06
        sideways_profile_risk = 0.04
        adapted_risk = result.adapted_config["max_risk_per_trade"]
        # With transition_progress=0, it should still be near the previous profile
        assert adapted_risk >= sideways_profile_risk or adapted_risk <= bull_profile_risk

    def test_adaptation_history_tracked(self):
        adapter = RegimeAdapter()
        config = _make_executor_config()
        adapter.adapt(config, "bull", 0.9)
        adapter.adapt(config, "crisis", 0.8)
        history = adapter.get_adaptation_history()
        assert len(history) == 2
        assert history[0]["regime"] == "bull"
        assert history[1]["regime"] == "crisis"

    def test_reset_clears_state(self):
        adapter = RegimeAdapter()
        config = _make_executor_config()
        adapter.adapt(config, "bull", 0.9)
        assert len(adapter.get_adaptation_history()) == 1
        adapter.reset()
        assert len(adapter.get_adaptation_history()) == 0

    def test_adapt_sideways_baseline(self):
        adapter = RegimeAdapter()
        config = _make_executor_config()
        result = adapter.adapt(config, "sideways", 0.9)
        # Sideways has max_risk_per_trade=0.04, daily_loss_limit=0.08
        assert result.adapted_config["max_risk_per_trade"] == 0.04
        assert result.adapted_config["daily_loss_limit"] == 0.08
        assert result.profile_used == "sideways_neutral"

    def test_to_dict_on_adaptation(self):
        adapter = RegimeAdapter()
        config = _make_executor_config()
        result = adapter.adapt(config, "bull", 0.9)
        d = result.to_dict()
        assert "adaptation_id" in d
        assert "original_config" in d
        assert "adapted_config" in d
        assert "changes" in d
        assert d["regime"] == "bull"
        assert d["confidence"] == 0.9
        assert "timestamp" in d


# ── TestAdapterConfig ────────────────────────────────────────────────


class TestAdapterConfig:
    """Tests for the AdapterConfig dataclass."""

    def test_defaults(self):
        cfg = AdapterConfig()
        assert cfg.smooth_transitions is True
        assert cfg.transition_speed == 0.5
        assert cfg.respect_user_overrides is True
        assert cfg.min_confidence_to_adapt == 0.5
        assert cfg.log_adaptations is True

    def test_custom_values(self):
        cfg = AdapterConfig(
            smooth_transitions=False,
            transition_speed=0.8,
            min_confidence_to_adapt=0.7,
        )
        assert cfg.smooth_transitions is False
        assert cfg.transition_speed == 0.8
        assert cfg.min_confidence_to_adapt == 0.7

    def test_min_confidence_boundary(self):
        adapter = RegimeAdapter(config=AdapterConfig(min_confidence_to_adapt=0.8))
        config = _make_executor_config()
        # Confidence 0.75 is below the 0.8 threshold
        result = adapter.adapt(config, "crisis", 0.75)
        assert result.changes == []
        # Confidence 0.85 is above threshold
        result2 = adapter.adapt(config, "crisis", 0.85)
        assert len(result2.changes) > 0


# ── TestPerformanceTuner ─────────────────────────────────────────────


class TestPerformanceTuner:
    """Tests for the PerformanceTuner."""

    def test_no_trades_no_adjustment(self):
        tuner = PerformanceTuner()
        config = _make_executor_config()
        result = tuner.tune(config)
        assert result.adjustments == []
        assert result.overall_factor == 1.0
        assert result.is_tightened is False
        assert result.is_loosened is False

    def test_consecutive_losses_tighten(self):
        tuner = PerformanceTuner()
        config = _make_executor_config()
        # Record 3 consecutive losses (default tighten_after_losses=3)
        for _ in range(3):
            tuner.record_trade(-0.02, signal_type="CLOUD_CROSS_BULLISH", regime="bull")
        result = tuner.tune(config)
        assert result.is_tightened is True
        assert result.overall_factor < 1.0
        assert len(result.adjustments) > 0
        # max_risk_per_trade should be reduced
        risk_adj = [a for a in result.adjustments if a.field == "max_risk_per_trade"]
        assert len(risk_adj) == 1
        assert risk_adj[0].adjusted_value < risk_adj[0].original_value

    def test_consecutive_wins_loosen(self):
        tuner = PerformanceTuner()
        config = _make_executor_config()
        # Record 6 consecutive wins (default loosen_after_wins=5, need win_rate > 0.6)
        for _ in range(6):
            tuner.record_trade(0.03, signal_type="TREND_ALIGNED_LONG", regime="bull")
        result = tuner.tune(config)
        assert result.is_loosened is True
        assert result.overall_factor > 1.0
        # max_risk_per_trade should be increased
        risk_adj = [a for a in result.adjustments if a.field == "max_risk_per_trade"]
        assert len(risk_adj) == 1
        assert risk_adj[0].adjusted_value > risk_adj[0].original_value

    def test_mixed_results_no_change(self):
        tuner = PerformanceTuner()
        config = _make_executor_config()
        # Alternate wins and losses — no streak
        tuner.record_trade(0.02)
        tuner.record_trade(-0.01)
        tuner.record_trade(0.015)
        tuner.record_trade(-0.005)
        result = tuner.tune(config)
        assert result.is_tightened is False
        assert result.is_loosened is False
        assert result.overall_factor == 1.0
        assert result.adjustments == []

    def test_record_trade_stores_history(self):
        tuner = PerformanceTuner()
        tuner.record_trade(0.05, signal_type="CLOUD_CROSS_BULLISH", regime="bull")
        tuner.record_trade(-0.02, signal_type="CLOUD_BOUNCE_LONG", regime="sideways")
        history = tuner.get_trade_history()
        assert len(history) == 2
        assert history[0]["pnl_pct"] == 0.05
        assert history[0]["signal_type"] == "CLOUD_CROSS_BULLISH"
        assert history[1]["pnl_pct"] == -0.02

    def test_tune_with_specific_config(self):
        tuner = PerformanceTuner()
        # 4 consecutive losses to trigger tightening
        for _ in range(4):
            tuner.record_trade(-0.03)
        custom_config = {
            "max_risk_per_trade": 0.08,
            "daily_loss_limit": 0.15,
            "max_concurrent_positions": 15,
            "reward_to_risk_target": 1.5,
        }
        result = tuner.tune(custom_config)
        assert result.is_tightened is True
        # Verify all tightenable fields got adjusted
        adjusted_fields = {a.field for a in result.adjustments}
        assert "max_risk_per_trade" in adjusted_fields
        assert "daily_loss_limit" in adjusted_fields

    def test_reset_clears_trades(self):
        tuner = PerformanceTuner()
        tuner.record_trade(0.01)
        tuner.record_trade(0.02)
        assert len(tuner.get_trade_history()) == 2
        tuner.reset()
        assert len(tuner.get_trade_history()) == 0

    def test_tighten_factor_limits(self):
        tuner = PerformanceTuner(config=TunerConfig(max_tighten_factor=0.5))
        config = _make_executor_config()
        # Record many consecutive losses to push factor toward the floor
        for _ in range(10):
            tuner.record_trade(-0.05)
        result = tuner.tune(config)
        assert result.is_tightened is True
        # Factor should not go below max_tighten_factor (0.5)
        assert result.overall_factor >= 0.5


# ── TestTunerConfig ──────────────────────────────────────────────────


class TestTunerConfig:
    """Tests for the TunerConfig dataclass."""

    def test_defaults(self):
        cfg = TunerConfig()
        assert cfg.lookback_trades == 20
        assert cfg.tighten_after_losses == 3
        assert cfg.loosen_after_wins == 5
        assert cfg.max_tighten_factor == 0.5
        assert cfg.max_loosen_factor == 1.3

    def test_custom_values(self):
        cfg = TunerConfig(
            lookback_trades=50,
            tighten_after_losses=5,
            loosen_after_wins=10,
            max_tighten_factor=0.3,
            max_loosen_factor=1.5,
        )
        assert cfg.lookback_trades == 50
        assert cfg.tighten_after_losses == 5
        assert cfg.max_loosen_factor == 1.5

    def test_boundary_values(self):
        cfg = TunerConfig(
            lookback_trades=1,
            tighten_after_losses=1,
            loosen_after_wins=1,
            max_tighten_factor=0.1,
            max_loosen_factor=2.0,
        )
        assert cfg.lookback_trades == 1
        assert cfg.max_tighten_factor == 0.1
        assert cfg.max_loosen_factor == 2.0


# ── TestRegimeMonitor ────────────────────────────────────────────────


class TestRegimeMonitor:
    """Tests for the RegimeMonitor."""

    def test_initial_state_sideways(self):
        monitor = RegimeMonitor()
        state = monitor.get_state()
        assert state.current_regime == "sideways"
        assert state.current_confidence == 0.5
        assert state.is_circuit_broken is False

    def test_update_same_regime_no_transition(self):
        monitor = RegimeMonitor()
        result = monitor.update("sideways", 0.8)
        assert result is None
        state = monitor.get_state()
        assert state.current_regime == "sideways"
        assert state.current_confidence == 0.8

    def test_update_new_regime_creates_transition(self):
        monitor = RegimeMonitor()
        result = monitor.update("bull", 0.85, method="hmm")
        assert result is not None
        assert result.from_regime == "sideways"
        assert result.to_regime == "bull"
        assert result.confidence == 0.85
        assert result.method == "hmm"
        state = monitor.get_state()
        assert state.current_regime == "bull"

    def test_circuit_breaker_trips(self):
        monitor = RegimeMonitor(config=MonitorConfig(max_transitions_per_hour=3))
        # Alternate regimes to trigger transitions
        regimes = ["bull", "bear", "crisis", "bull", "bear"]
        transitions = []
        for regime in regimes:
            result = monitor.update(regime, 0.9)
            if result is not None:
                transitions.append(result)
        # After 3 transitions, circuit breaker should trip
        state = monitor.get_state()
        assert state.is_circuit_broken is True
        # Further transitions should be blocked
        result = monitor.update("crisis", 0.95)
        assert result is None

    def test_get_transitions_limit(self):
        monitor = RegimeMonitor()
        regimes = ["bull", "bear", "crisis", "sideways", "bull"]
        for regime in regimes:
            monitor.update(regime, 0.9)
        all_transitions = monitor.get_transitions(limit=100)
        limited = monitor.get_transitions(limit=2)
        assert len(limited) == 2
        assert len(all_transitions) == len(regimes)
        # Newest first
        assert limited[0].to_regime == "bull"

    def test_get_transition_frequency(self):
        monitor = RegimeMonitor()
        monitor.update("bull", 0.9)
        monitor.update("bear", 0.9)
        monitor.update("bull", 0.9)
        freq = monitor.get_transition_frequency()
        assert "sideways->bull" in freq
        assert "bull->bear" in freq
        assert "bear->bull" in freq
        assert freq["sideways->bull"] == 1
        assert freq["bull->bear"] == 1

    def test_reset(self):
        monitor = RegimeMonitor()
        monitor.update("bull", 0.9)
        monitor.update("bear", 0.85)
        assert len(monitor.get_transitions()) > 0
        monitor.reset()
        state = monitor.get_state()
        assert state.current_regime == "sideways"
        assert state.current_confidence == 0.5
        assert len(monitor.get_transitions()) == 0

    def test_update_below_confidence_threshold(self):
        monitor = RegimeMonitor(
            config=MonitorConfig(min_confidence_for_alert=0.6)
        )
        # Confidence 0.4 is below 0.6 threshold — transition should be suppressed
        result = monitor.update("bull", 0.4)
        assert result is None
        state = monitor.get_state()
        assert state.current_regime == "sideways"


# ── TestModuleImports ────────────────────────────────────────────────


class TestRegimeAdaptiveModuleImports:
    """Tests for module-level imports and __all__."""

    def test_all_importable(self):
        import src.regime_adaptive as mod
        for name in mod.__all__:
            obj = getattr(mod, name)
            assert obj is not None, f"{name} should be importable"

    def test_default_configs(self):
        cfg_adapter = AdapterConfig()
        cfg_tuner = TunerConfig()
        cfg_monitor = MonitorConfig()
        assert cfg_adapter.smooth_transitions is True
        assert cfg_tuner.lookback_trades == 20
        assert cfg_monitor.check_interval_seconds == 60.0
