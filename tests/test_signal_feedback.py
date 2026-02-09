"""Tests for Signal Performance Feedback Loop (PRD-166).

8 test classes, ~55 tests covering tracker config, source performance,
performance tracker, adjuster config, weight update, weight adjuster,
feedback integration, and module imports.
"""

from __future__ import annotations

import math
import unittest
from datetime import datetime, timezone

from src.signal_feedback.tracker import (
    PerformanceTracker,
    SourcePerformance,
    TrackerConfig,
)
from src.signal_feedback.adjuster import (
    AdjusterConfig,
    WeightAdjuster,
    WeightUpdate,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _populate_tracker(
    tracker: PerformanceTracker,
    source: str,
    wins: int = 15,
    losses: int = 5,
    win_pnl: float = 100.0,
    loss_pnl: float = -50.0,
    conviction: float = 70.0,
) -> None:
    """Populate a tracker with a mix of wins and losses."""
    for _ in range(wins):
        tracker.record_outcome(source, win_pnl, conviction)
    for _ in range(losses):
        tracker.record_outcome(source, loss_pnl, conviction)


# ═══════════════════════════════════════════════════════════════════════
#  1. TrackerConfig
# ═══════════════════════════════════════════════════════════════════════


class TestTrackerConfig(unittest.TestCase):
    """Tests for TrackerConfig dataclass."""

    def test_defaults(self):
        cfg = TrackerConfig()
        self.assertEqual(cfg.rolling_window, 100)
        self.assertEqual(cfg.min_trades_for_stats, 10)
        self.assertAlmostEqual(cfg.decay_factor, 0.95)
        self.assertAlmostEqual(cfg.risk_free_rate, 0.05)

    def test_custom_values(self):
        cfg = TrackerConfig(rolling_window=50, min_trades_for_stats=5)
        self.assertEqual(cfg.rolling_window, 50)
        self.assertEqual(cfg.min_trades_for_stats, 5)

    def test_is_dataclass(self):
        cfg = TrackerConfig()
        self.assertTrue(hasattr(cfg, "__dataclass_fields__"))


# ═══════════════════════════════════════════════════════════════════════
#  2. SourcePerformance
# ═══════════════════════════════════════════════════════════════════════


class TestSourcePerformance(unittest.TestCase):
    """Tests for SourcePerformance dataclass."""

    def test_default_values(self):
        sp = SourcePerformance()
        self.assertEqual(sp.source, "")
        self.assertEqual(sp.trade_count, 0)
        self.assertEqual(sp.win_count, 0)
        self.assertAlmostEqual(sp.win_rate, 0.0)
        self.assertAlmostEqual(sp.sharpe_ratio, 0.0)

    def test_custom_values(self):
        sp = SourcePerformance(
            source="ema_cloud", trade_count=20, win_count=12,
            win_rate=0.6, total_pnl=500.0, avg_pnl=25.0,
            sharpe_ratio=1.5, profit_factor=3.0, avg_conviction=75.0,
        )
        self.assertEqual(sp.source, "ema_cloud")
        self.assertEqual(sp.trade_count, 20)
        self.assertAlmostEqual(sp.win_rate, 0.6)

    def test_to_dict_keys(self):
        sp = SourcePerformance(source="test")
        d = sp.to_dict()
        expected_keys = {
            "source", "trade_count", "win_count", "win_rate",
            "total_pnl", "avg_pnl", "sharpe_ratio", "profit_factor",
            "avg_conviction", "last_updated",
        }
        self.assertEqual(set(d.keys()), expected_keys)

    def test_to_dict_rounds_values(self):
        sp = SourcePerformance(
            source="x", win_rate=0.33333, avg_pnl=12.3456,
            sharpe_ratio=1.23456, profit_factor=2.34567,
        )
        d = sp.to_dict()
        self.assertAlmostEqual(d["win_rate"], 0.333, places=3)
        self.assertAlmostEqual(d["avg_pnl"], 12.35, places=2)


# ═══════════════════════════════════════════════════════════════════════
#  3. PerformanceTracker
# ═══════════════════════════════════════════════════════════════════════


class TestPerformanceTracker(unittest.TestCase):
    """Tests for the PerformanceTracker engine."""

    def setUp(self):
        self.tracker = PerformanceTracker()

    def test_record_outcome_creates_source(self):
        self.tracker.record_outcome("ema_cloud", 100.0, 80.0)
        perf = self.tracker.get_performance("ema_cloud")
        self.assertEqual(perf.trade_count, 1)

    def test_record_outcome_accumulates(self):
        for i in range(5):
            self.tracker.record_outcome("social", 50.0 * (1 if i % 2 == 0 else -1))
        perf = self.tracker.get_performance("social")
        self.assertEqual(perf.trade_count, 5)

    def test_rolling_window_trims(self):
        cfg = TrackerConfig(rolling_window=10)
        tracker = PerformanceTracker(config=cfg)
        for i in range(15):
            tracker.record_outcome("src", float(i))
        perf = tracker.get_performance("src")
        self.assertEqual(perf.trade_count, 10)

    def test_get_performance_unknown_source(self):
        perf = self.tracker.get_performance("nonexistent")
        self.assertEqual(perf.trade_count, 0)
        self.assertEqual(perf.source, "nonexistent")

    def test_win_rate_calculation(self):
        for _ in range(6):
            self.tracker.record_outcome("src", 100.0)
        for _ in range(4):
            self.tracker.record_outcome("src", -50.0)
        perf = self.tracker.get_performance("src")
        self.assertAlmostEqual(perf.win_rate, 0.6)

    def test_avg_pnl_calculation(self):
        self.tracker.record_outcome("src", 100.0)
        self.tracker.record_outcome("src", -50.0)
        perf = self.tracker.get_performance("src")
        self.assertAlmostEqual(perf.avg_pnl, 25.0)

    def test_total_pnl_calculation(self):
        self.tracker.record_outcome("src", 100.0)
        self.tracker.record_outcome("src", 200.0)
        self.tracker.record_outcome("src", -50.0)
        perf = self.tracker.get_performance("src")
        self.assertAlmostEqual(perf.total_pnl, 250.0)

    def test_profit_factor(self):
        for _ in range(5):
            self.tracker.record_outcome("src", 100.0)
        for _ in range(5):
            self.tracker.record_outcome("src", -50.0)
        perf = self.tracker.get_performance("src")
        self.assertAlmostEqual(perf.profit_factor, 500.0 / 250.0)

    def test_sharpe_below_min_trades(self):
        cfg = TrackerConfig(min_trades_for_stats=10)
        tracker = PerformanceTracker(config=cfg)
        for i in range(5):
            tracker.record_outcome("src", float(i))
        perf = tracker.get_performance("src")
        self.assertAlmostEqual(perf.sharpe_ratio, 0.0)

    def test_sharpe_enough_trades(self):
        _populate_tracker(self.tracker, "src", wins=10, losses=5)
        perf = self.tracker.get_performance("src")
        # With 15 trades (>=10 min), Sharpe should be computed
        # Positive average P&L should produce a non-zero Sharpe
        self.assertNotAlmostEqual(perf.sharpe_ratio, 0.0)

    def test_sharpe_all_identical_pnl_is_zero(self):
        cfg = TrackerConfig(min_trades_for_stats=5)
        tracker = PerformanceTracker(config=cfg)
        for _ in range(10):
            tracker.record_outcome("src", 100.0)
        perf = tracker.get_performance("src")
        # Zero variance -> sharpe = 0
        self.assertAlmostEqual(perf.sharpe_ratio, 0.0)

    def test_avg_conviction(self):
        self.tracker.record_outcome("src", 100.0, 80.0)
        self.tracker.record_outcome("src", -50.0, 60.0)
        perf = self.tracker.get_performance("src")
        self.assertAlmostEqual(perf.avg_conviction, 70.0)

    def test_get_all_performance(self):
        self.tracker.record_outcome("src_a", 100.0)
        self.tracker.record_outcome("src_b", -50.0)
        all_perf = self.tracker.get_all_performance()
        self.assertIn("src_a", all_perf)
        self.assertIn("src_b", all_perf)

    def test_get_ranked_sources(self):
        _populate_tracker(self.tracker, "good", wins=15, losses=2, win_pnl=200.0, loss_pnl=-30.0)
        _populate_tracker(self.tracker, "bad", wins=3, losses=12, win_pnl=50.0, loss_pnl=-100.0)
        ranked = self.tracker.get_ranked_sources()
        self.assertEqual(len(ranked), 2)
        # Best Sharpe should be first
        self.assertEqual(ranked[0].source, "good")

    def test_get_ranked_sources_empty(self):
        ranked = self.tracker.get_ranked_sources()
        self.assertEqual(len(ranked), 0)


# ═══════════════════════════════════════════════════════════════════════
#  4. AdjusterConfig
# ═══════════════════════════════════════════════════════════════════════


class TestAdjusterConfig(unittest.TestCase):
    """Tests for AdjusterConfig dataclass."""

    def test_defaults(self):
        cfg = AdjusterConfig()
        self.assertAlmostEqual(cfg.learning_rate, 0.1)
        self.assertAlmostEqual(cfg.min_weight, 0.02)
        self.assertAlmostEqual(cfg.max_weight, 0.40)
        self.assertAlmostEqual(cfg.sharpe_target, 1.5)
        self.assertAlmostEqual(cfg.decay_rate, 0.95)
        self.assertEqual(cfg.min_trades_to_adjust, 20)
        self.assertTrue(cfg.normalize)

    def test_custom_values(self):
        cfg = AdjusterConfig(learning_rate=0.2, min_weight=0.05, max_weight=0.50)
        self.assertAlmostEqual(cfg.learning_rate, 0.2)
        self.assertAlmostEqual(cfg.min_weight, 0.05)
        self.assertAlmostEqual(cfg.max_weight, 0.50)


# ═══════════════════════════════════════════════════════════════════════
#  5. WeightUpdate
# ═══════════════════════════════════════════════════════════════════════


class TestWeightUpdate(unittest.TestCase):
    """Tests for WeightUpdate dataclass."""

    def test_default_values(self):
        wu = WeightUpdate()
        self.assertEqual(wu.old_weights, {})
        self.assertEqual(wu.new_weights, {})
        self.assertEqual(wu.adjustments, [])

    def test_to_dict_keys(self):
        wu = WeightUpdate(
            old_weights={"a": 0.5},
            new_weights={"a": 0.6},
            adjustments=[{"source": "a", "action": "increase"}],
        )
        d = wu.to_dict()
        self.assertIn("old_weights", d)
        self.assertIn("new_weights", d)
        self.assertIn("adjustments", d)
        self.assertIn("timestamp", d)

    def test_to_dict_rounds_weights(self):
        wu = WeightUpdate(
            old_weights={"a": 0.33333},
            new_weights={"a": 0.66666},
        )
        d = wu.to_dict()
        self.assertAlmostEqual(d["old_weights"]["a"], 0.3333, places=4)
        self.assertAlmostEqual(d["new_weights"]["a"], 0.6667, places=4)


# ═══════════════════════════════════════════════════════════════════════
#  6. WeightAdjuster
# ═══════════════════════════════════════════════════════════════════════


class TestWeightAdjuster(unittest.TestCase):
    """Tests for the WeightAdjuster engine."""

    def setUp(self):
        self.tracker = PerformanceTracker()
        self.adjuster = WeightAdjuster(tracker=self.tracker)

    def test_compute_weights_no_data_no_change(self):
        weights = {"ema_cloud": 0.25, "social": 0.25}
        update = self.adjuster.compute_weights(weights)
        # Without sufficient trades, weights should be unchanged (then normalized)
        total = sum(update.new_weights.values())
        self.assertAlmostEqual(total, 1.0, places=3)

    def test_compute_weights_insufficient_trades(self):
        self.tracker.record_outcome("ema_cloud", 100.0)
        weights = {"ema_cloud": 0.5, "social": 0.5}
        update = self.adjuster.compute_weights(weights)
        # Only 1 trade < 20 min, action = no_change
        for adj in update.adjustments:
            if adj["source"] == "ema_cloud":
                self.assertEqual(adj["action"], "no_change")

    def test_compute_weights_positive_sharpe_increase(self):
        cfg = AdjusterConfig(min_trades_to_adjust=10, sharpe_target=0.5)
        tracker = PerformanceTracker(TrackerConfig(min_trades_for_stats=5))
        adjuster = WeightAdjuster(config=cfg, tracker=tracker)
        _populate_tracker(tracker, "ema_cloud", wins=15, losses=2, win_pnl=200.0, loss_pnl=-30.0)
        weights = {"ema_cloud": 0.25}
        update = adjuster.compute_weights(weights)
        found = False
        for adj in update.adjustments:
            if adj["source"] == "ema_cloud":
                found = True
                self.assertIn(adj["action"], ("increase", "slight_increase"))
        self.assertTrue(found)

    def test_compute_weights_negative_sharpe_decay(self):
        cfg = AdjusterConfig(min_trades_to_adjust=10, sharpe_target=1.5)
        tracker = PerformanceTracker(TrackerConfig(min_trades_for_stats=5))
        adjuster = WeightAdjuster(config=cfg, tracker=tracker)
        _populate_tracker(tracker, "bad_src", wins=2, losses=15, win_pnl=50.0, loss_pnl=-100.0)
        weights = {"bad_src": 0.25}
        update = adjuster.compute_weights(weights)
        for adj in update.adjustments:
            if adj["source"] == "bad_src":
                self.assertIn(adj["action"], ("decay", "strong_decay"))

    def test_compute_weights_normalization(self):
        cfg = AdjusterConfig(min_trades_to_adjust=10, normalize=True)
        tracker = PerformanceTracker(TrackerConfig(min_trades_for_stats=5))
        adjuster = WeightAdjuster(config=cfg, tracker=tracker)
        _populate_tracker(tracker, "a", wins=12, losses=3)
        _populate_tracker(tracker, "b", wins=8, losses=7)
        weights = {"a": 0.5, "b": 0.5}
        update = adjuster.compute_weights(weights)
        total = sum(update.new_weights.values())
        self.assertAlmostEqual(total, 1.0, places=3)

    def test_compute_weights_clamped_to_bounds(self):
        cfg = AdjusterConfig(min_weight=0.05, max_weight=0.40, min_trades_to_adjust=5)
        tracker = PerformanceTracker(TrackerConfig(min_trades_for_stats=3))
        adjuster = WeightAdjuster(config=cfg, tracker=tracker)
        _populate_tracker(tracker, "src", wins=20, losses=0, win_pnl=1000.0)
        weights = {"src": 0.50}
        update = adjuster.compute_weights(weights)
        # Before normalization, would be clamped. After normalization of a single source, it's 1.0.
        # With a single source and normalize=True, it should be 1.0
        self.assertAlmostEqual(update.new_weights["src"], 1.0, places=3)

    def test_get_weight_history(self):
        weights = {"a": 0.5, "b": 0.5}
        self.adjuster.compute_weights(weights)
        self.adjuster.compute_weights(weights)
        history = self.adjuster.get_weight_history(limit=10)
        self.assertEqual(len(history), 2)

    def test_get_weight_history_limited(self):
        for _ in range(5):
            self.adjuster.compute_weights({"a": 0.5})
        history = self.adjuster.get_weight_history(limit=3)
        self.assertEqual(len(history), 3)

    def test_get_recommended_weights_no_data(self):
        sources = ["ema_cloud", "social", "factor"]
        weights = self.adjuster.get_recommended_weights(sources)
        self.assertEqual(len(weights), 3)
        total = sum(weights.values())
        self.assertAlmostEqual(total, 1.0, places=3)

    def test_get_recommended_weights_with_data(self):
        cfg = AdjusterConfig(min_trades_to_adjust=10)
        tracker = PerformanceTracker(TrackerConfig(min_trades_for_stats=5))
        adjuster = WeightAdjuster(config=cfg, tracker=tracker)
        _populate_tracker(tracker, "good", wins=15, losses=2, win_pnl=200.0, loss_pnl=-30.0)
        _populate_tracker(tracker, "bad", wins=3, losses=12, win_pnl=50.0, loss_pnl=-100.0)
        sources = ["good", "bad", "new_source"]
        weights = adjuster.get_recommended_weights(sources)
        total = sum(weights.values())
        self.assertAlmostEqual(total, 1.0, places=3)
        self.assertGreater(weights["good"], weights["bad"])

    def test_get_recommended_weights_all_equal_when_no_history(self):
        sources = ["a", "b", "c"]
        weights = self.adjuster.get_recommended_weights(sources)
        # Should be roughly equal
        for w in weights.values():
            self.assertAlmostEqual(w, 1.0 / 3, places=3)


# ═══════════════════════════════════════════════════════════════════════
#  7. Feedback Integration
# ═══════════════════════════════════════════════════════════════════════


class TestFeedbackIntegration(unittest.TestCase):
    """Integration tests for tracker + adjuster working together."""

    def test_full_feedback_loop(self):
        tracker = PerformanceTracker(TrackerConfig(min_trades_for_stats=5))
        adjuster = WeightAdjuster(
            config=AdjusterConfig(min_trades_to_adjust=10, sharpe_target=0.5),
            tracker=tracker,
        )
        # Simulate outcomes
        _populate_tracker(tracker, "ema_cloud", wins=15, losses=3, win_pnl=150.0, loss_pnl=-60.0)
        _populate_tracker(tracker, "social", wins=5, losses=10, win_pnl=80.0, loss_pnl=-70.0)

        # Get initial weights
        initial = {"ema_cloud": 0.5, "social": 0.5}
        update = adjuster.compute_weights(initial)

        # EMA cloud should get relatively higher weight
        self.assertIsNotNone(update.new_weights)
        total = sum(update.new_weights.values())
        self.assertAlmostEqual(total, 1.0, places=3)

    def test_ranked_sources_match_adjuster_preference(self):
        tracker = PerformanceTracker(TrackerConfig(min_trades_for_stats=5))
        _populate_tracker(tracker, "best", wins=18, losses=2, win_pnl=300.0, loss_pnl=-20.0)
        _populate_tracker(tracker, "worst", wins=2, losses=18, win_pnl=30.0, loss_pnl=-200.0)

        ranked = tracker.get_ranked_sources()
        self.assertEqual(ranked[0].source, "best")

    def test_multiple_adjustment_cycles(self):
        tracker = PerformanceTracker(TrackerConfig(min_trades_for_stats=5))
        adjuster = WeightAdjuster(
            config=AdjusterConfig(min_trades_to_adjust=10),
            tracker=tracker,
        )
        _populate_tracker(tracker, "a", wins=12, losses=3)
        _populate_tracker(tracker, "b", wins=5, losses=10)

        weights = {"a": 0.5, "b": 0.5}
        for _ in range(3):
            update = adjuster.compute_weights(weights)
            weights = update.new_weights

        total = sum(weights.values())
        self.assertAlmostEqual(total, 1.0, places=3)
        history = adjuster.get_weight_history()
        self.assertEqual(len(history), 3)


# ═══════════════════════════════════════════════════════════════════════
#  8. Module Imports
# ═══════════════════════════════════════════════════════════════════════


class TestModuleImports(unittest.TestCase):
    """Verify public API is importable from the package."""

    def test_import_from_package(self):
        from src.signal_feedback import (
            AdjusterConfig,
            PerformanceTracker,
            SourcePerformance,
            TrackerConfig,
            WeightAdjuster,
            WeightUpdate,
        )
        self.assertIsNotNone(PerformanceTracker)
        self.assertIsNotNone(WeightAdjuster)

    def test_tracker_config_importable(self):
        from src.signal_feedback.tracker import TrackerConfig
        cfg = TrackerConfig()
        self.assertIsInstance(cfg, TrackerConfig)

    def test_adjuster_config_importable(self):
        from src.signal_feedback.adjuster import AdjusterConfig
        cfg = AdjusterConfig()
        self.assertIsInstance(cfg, AdjusterConfig)
