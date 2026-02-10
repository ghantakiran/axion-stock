"""PRD-176: Adaptive Feedback Loop — tests.

Tests WeightStore, FeedbackBridge, and the complete feedback cycle.
~35 tests across 3 classes.
"""

from __future__ import annotations

import pytest

from src.signal_feedback.weight_store import WeightSnapshot, WeightStore
from src.signal_feedback.tracker import PerformanceTracker
from src.signal_feedback.adjuster import AdjusterConfig, WeightAdjuster
from src.bot_pipeline.feedback_bridge import FeedbackBridge, FeedbackConfig


# ═════════════════════════════════════════════════════════════════════
# Test WeightStore
# ═════════════════════════════════════════════════════════════════════


class TestWeightStore:
    """Test weight persistence and history."""

    def test_empty_store(self):
        store = WeightStore()
        assert store.get_latest() is None
        assert store.get_total_updates() == 0

    def test_record_snapshot(self):
        store = WeightStore()
        snap = store.record({"ema_cloud": 0.5, "vwap": 0.5}, trigger="initial")
        assert snap.weights["ema_cloud"] == 0.5
        assert snap.trigger == "initial"

    def test_get_latest(self):
        store = WeightStore()
        store.record({"a": 0.3, "b": 0.7}, trigger="auto")
        store.record({"a": 0.4, "b": 0.6}, trigger="auto")
        latest = store.get_latest()
        assert latest.weights["a"] == 0.4

    def test_history(self):
        store = WeightStore()
        for i in range(5):
            store.record({"src": 0.1 * (i + 1)}, trigger="auto", trade_count=i * 10)
        history = store.get_history(limit=3)
        assert len(history) == 3
        # Should be most recent 3
        assert history[-1]["trade_count"] == 40

    def test_weight_evolution(self):
        store = WeightStore()
        store.record({"ema": 0.3, "vwap": 0.7})
        store.record({"ema": 0.4, "vwap": 0.6})
        store.record({"ema": 0.5, "vwap": 0.5})
        evo = store.get_weight_evolution("ema")
        assert len(evo) == 3
        assert evo[0][1] == 0.3
        assert evo[2][1] == 0.5

    def test_evolution_missing_source(self):
        store = WeightStore()
        store.record({"ema": 0.5})
        evo = store.get_weight_evolution("nonexistent")
        assert len(evo) == 0

    def test_max_history_bounded(self):
        store = WeightStore(max_history=3)
        for i in range(5):
            store.record({"src": float(i)})
        assert store.get_total_updates() == 3

    def test_snapshot_to_dict(self):
        snap = WeightSnapshot(
            weights={"a": 0.5, "b": 0.5},
            trigger="manual",
            trade_count=100,
        )
        d = snap.to_dict()
        assert d["trigger"] == "manual"
        assert d["trade_count"] == 100


# ═════════════════════════════════════════════════════════════════════
# Test FeedbackBridge
# ═════════════════════════════════════════════════════════════════════


class TestFeedbackBridge:
    """Test the feedback bridge connecting adjuster to pipeline."""

    def test_initial_state(self):
        bridge = FeedbackBridge()
        assert bridge.get_trade_count() == 0
        assert bridge.get_current_weights() == {}

    def test_set_initial_weights(self):
        bridge = FeedbackBridge()
        bridge.set_initial_weights({"ema_cloud": 0.6, "vwap": 0.4})
        weights = bridge.get_current_weights()
        assert weights["ema_cloud"] == 0.6

    def test_on_trade_closed_increments_count(self):
        bridge = FeedbackBridge()
        bridge.on_trade_closed("ema_cloud", 100.0)
        assert bridge.get_trade_count() == 1

    def test_no_adjustment_before_threshold(self):
        config = FeedbackConfig(adjust_every_n_trades=10)
        bridge = FeedbackBridge(config=config)
        bridge.set_initial_weights({"ema_cloud": 0.5, "vwap": 0.5})
        result = bridge.on_trade_closed("ema_cloud", 100.0)
        assert result is None  # Not enough trades yet

    def test_adjustment_at_threshold(self):
        config = FeedbackConfig(adjust_every_n_trades=5)
        bridge = FeedbackBridge(config=config)
        bridge.set_initial_weights({"ema_cloud": 0.5, "vwap": 0.5})
        result = None
        for i in range(5):
            result = bridge.on_trade_closed("ema_cloud", 50.0 if i % 2 == 0 else -20.0)
        # 5th trade should trigger adjustment
        assert result is not None

    def test_force_adjustment(self):
        bridge = FeedbackBridge()
        bridge.set_initial_weights({"ema_cloud": 0.5, "vwap": 0.5})
        for _ in range(3):
            bridge.on_trade_closed("ema_cloud", 100.0)
        update = bridge.force_adjustment()
        assert update is not None
        assert "ema_cloud" in update.new_weights

    def test_weight_history_recorded(self):
        bridge = FeedbackBridge()
        bridge.set_initial_weights({"ema_cloud": 0.5})
        history = bridge.get_weight_history()
        assert len(history) >= 1  # Initial recording

    def test_get_source_performance(self):
        bridge = FeedbackBridge()
        bridge.on_trade_closed("ema_cloud", 100.0)
        bridge.on_trade_closed("ema_cloud", -50.0)
        perf = bridge.get_source_performance()
        assert "ema_cloud" in perf
        assert perf["ema_cloud"]["trade_count"] == 2

    def test_get_last_update_before_any(self):
        bridge = FeedbackBridge()
        assert bridge.get_last_update() is None

    def test_auto_apply_weights(self):
        config = FeedbackConfig(adjust_every_n_trades=2, auto_apply=True)
        bridge = FeedbackBridge(config=config)
        bridge.set_initial_weights({"ema_cloud": 0.5, "vwap": 0.5})
        bridge.on_trade_closed("ema_cloud", 100.0)
        bridge.on_trade_closed("ema_cloud", 100.0)
        # Weights should be updated after 2 trades
        weights = bridge.get_current_weights()
        assert len(weights) > 0


# ═════════════════════════════════════════════════════════════════════
# Test Full Feedback Cycle
# ═════════════════════════════════════════════════════════════════════


class TestFullFeedbackCycle:
    """Test the complete tracker → adjuster → fusion weights cycle."""

    def test_tracker_feeds_adjuster(self):
        tracker = PerformanceTracker()
        # Record enough trades — ema_cloud consistently positive, vwap consistently negative
        import random
        random.seed(99)
        for _ in range(30):
            tracker.record_outcome("ema_cloud", 50.0 + random.uniform(-5, 5), 70.0)
        for _ in range(30):
            tracker.record_outcome("vwap", -20.0 + random.uniform(-5, 5), 60.0)

        # Use max_weight=1.0 so the clamp doesn't equalize both sources
        adjuster = WeightAdjuster(
            config=AdjusterConfig(min_trades_to_adjust=20, max_weight=1.0),
            tracker=tracker,
        )
        update = adjuster.compute_weights({"ema_cloud": 0.5, "vwap": 0.5})
        # ema_cloud should get higher weight (positive Sharpe vs negative Sharpe)
        assert update.new_weights["ema_cloud"] > update.new_weights["vwap"]

    def test_recommended_weights_from_scratch(self):
        tracker = PerformanceTracker()
        for _ in range(30):
            tracker.record_outcome("ema_cloud", 100.0)
        for _ in range(30):
            tracker.record_outcome("vwap", 10.0)

        adjuster = WeightAdjuster(
            config=AdjusterConfig(min_trades_to_adjust=20),
            tracker=tracker,
        )
        weights = adjuster.get_recommended_weights(["ema_cloud", "vwap"])
        assert abs(sum(weights.values()) - 1.0) < 0.01

    def test_bridge_records_weight_changes(self):
        config = FeedbackConfig(adjust_every_n_trades=3)
        store = WeightStore()
        tracker = PerformanceTracker()
        bridge = FeedbackBridge(
            config=config, tracker=tracker, weight_store=store,
        )
        bridge.set_initial_weights({"ema_cloud": 0.5, "vwap": 0.5})

        for _ in range(3):
            bridge.on_trade_closed("ema_cloud", 100.0)

        # Should have initial + adjustment = 2 entries
        assert store.get_total_updates() >= 2

    def test_feedback_config_defaults(self):
        config = FeedbackConfig()
        assert config.adjust_every_n_trades == 50
        assert config.auto_apply is True

    def test_feedback_config_custom(self):
        config = FeedbackConfig(
            adjust_every_n_trades=10,
            auto_apply=False,
        )
        assert config.adjust_every_n_trades == 10
        assert config.auto_apply is False

    def test_weight_store_integration(self):
        store = WeightStore()
        store.record({"ema_cloud": 0.6, "vwap": 0.4}, trigger="initial", trade_count=0)
        store.record({"ema_cloud": 0.7, "vwap": 0.3}, trigger="auto", trade_count=50)
        latest = store.get_latest()
        assert latest.weights["ema_cloud"] == 0.7
        assert latest.trade_count == 50
