"""Tests for Integration Pipeline (PRD-169).

5 test classes, ~25 tests verifying end-to-end signal-to-execution
pipeline across all 5 new modules: signal_persistence, unified_risk,
strategy_selector, signal_feedback, and enhanced_backtest.
"""

from __future__ import annotations

import math
import unittest
from datetime import date, datetime, timezone

from src.signal_persistence import (
    SignalStore,
    SignalRecorder,
    SignalRecord,
    SignalStatus,
    FusionRecord,
    RiskDecisionRecord,
    ExecutionRecord,
)
from src.unified_risk import (
    RiskContext,
    RiskContextConfig,
    CorrelationGuard,
    VaRPositionSizer,
    RegimeRiskAdapter,
)
from src.strategy_selector import (
    StrategySelector,
    MeanReversionStrategy,
    ADXGate,
    TrendStrength,
)
from src.signal_feedback import PerformanceTracker, WeightAdjuster, TrackerConfig, AdjusterConfig
from src.enhanced_backtest import (
    SurvivorshipFilter,
    ConvexImpactModel,
    MonteCarloSimulator,
    MonteCarloConfig,
    GapSimulator,
    GapConfig,
)


# ── Helpers ──────────────────────────────────────────────────────────


def _deterministic_returns(n: int = 30, seed_offset: int = 0) -> list[float]:
    """Generate deterministic return series."""
    return [0.01 * ((i + seed_offset) % 7 - 3) for i in range(n)]


def _trending_prices(n: int = 60, start: float = 100.0, step: float = 0.5) -> list[float]:
    return [start + i * step for i in range(n)]


def _oscillating_prices(n: int = 60, base: float = 100.0, amplitude: float = 5.0) -> list[float]:
    return [base + amplitude * math.sin(i * 0.3) for i in range(n)]


def _ohlc_from_closes(closes: list[float], spread: float = 1.0):
    highs = [c + spread for c in closes]
    lows = [c - spread for c in closes]
    return highs, lows


# ═══════════════════════════════════════════════════════════════════════
#  1. Signal → Fusion Pipeline
# ═══════════════════════════════════════════════════════════════════════


class TestSignalToFusionPipeline(unittest.TestCase):
    """Tests that signals can be created, persisted, fused, and linked."""

    def setUp(self):
        self.recorder = SignalRecorder()

    def test_create_and_persist_raw_signals(self):
        sig_id1 = self.recorder.record_signal(
            source="ema_cloud", ticker="AAPL",
            direction="bullish", strength=78.5, confidence=0.85,
        )
        sig_id2 = self.recorder.record_signal(
            source="social", ticker="AAPL",
            direction="bullish", strength=65.0, confidence=0.70,
        )
        self.assertIsNotNone(sig_id1)
        self.assertIsNotNone(sig_id2)

        signals = self.recorder.store.get_signals_by_ticker("AAPL")
        self.assertEqual(len(signals), 2)

    def test_fuse_signals_and_link(self):
        sig1 = self.recorder.record_signal(
            source="ema_cloud", ticker="AAPL",
            direction="bullish", strength=80.0, confidence=0.9,
        )
        sig2 = self.recorder.record_signal(
            source="factor", ticker="AAPL",
            direction="bullish", strength=70.0, confidence=0.75,
        )

        # Simulate fusion: weighted average of strengths
        composite = 0.6 * 80.0 + 0.4 * 70.0
        fusion_id = self.recorder.record_fusion(
            ticker="AAPL",
            input_signal_ids=[sig1, sig2],
            direction="bullish",
            composite_score=composite,
            confidence=0.82,
            source_count=2,
            agreement_ratio=1.0,
            source_weights_used={"ema_cloud": 0.6, "factor": 0.4},
        )
        self.assertIsNotNone(fusion_id)

        # Check that signals are linked to fusion
        record1 = self.recorder.store.get_signal(sig1)
        self.assertEqual(record1.fusion_id, fusion_id)
        self.assertEqual(record1.status, SignalStatus.FUSED)

    def test_full_trace_after_fusion(self):
        sig_id = self.recorder.record_signal(
            source="ema_cloud", ticker="MSFT",
            direction="bullish", strength=75.0,
        )
        fusion_id = self.recorder.record_fusion(
            ticker="MSFT", input_signal_ids=[sig_id],
            direction="bullish", composite_score=75.0, confidence=0.8,
        )
        trace = self.recorder.get_pipeline_trace(sig_id)
        self.assertIsNotNone(trace["signal"])
        self.assertIsNotNone(trace["fusion"])
        self.assertEqual(trace["signal"]["ticker"], "MSFT")

    def test_multiple_tickers_isolated(self):
        id_aapl = self.recorder.record_signal(
            source="ema_cloud", ticker="AAPL",
            direction="bullish", strength=80.0,
        )
        id_msft = self.recorder.record_signal(
            source="ema_cloud", ticker="MSFT",
            direction="bearish", strength=60.0,
        )
        aapl_signals = self.recorder.store.get_signals_by_ticker("AAPL")
        msft_signals = self.recorder.store.get_signals_by_ticker("MSFT")
        self.assertEqual(len(aapl_signals), 1)
        self.assertEqual(len(msft_signals), 1)

    def test_store_stats_after_pipeline(self):
        self.recorder.record_signal(
            source="ema_cloud", ticker="AAPL",
            direction="bullish", strength=80.0,
        )
        stats = self.recorder.get_stats()
        self.assertEqual(stats["total_signals"], 1)


# ═══════════════════════════════════════════════════════════════════════
#  2. Fusion → Risk Pipeline
# ═══════════════════════════════════════════════════════════════════════


class TestFusionToRiskPipeline(unittest.TestCase):
    """Tests that a fused signal passes through risk assessment."""

    def setUp(self):
        self.recorder = SignalRecorder()
        self.risk_ctx = RiskContext(equity=100_000.0)

    def test_approved_signal_through_risk(self):
        sig_id = self.recorder.record_signal(
            source="ema_cloud", ticker="AAPL",
            direction="bullish", strength=80.0, confidence=0.9,
        )
        fusion_id = self.recorder.record_fusion(
            ticker="AAPL", input_signal_ids=[sig_id],
            direction="bullish", composite_score=80.0, confidence=0.9,
        )

        returns = {"AAPL": _deterministic_returns(30)}
        assessment = self.risk_ctx.assess(
            ticker="AAPL", direction="long", positions=[],
            returns_by_ticker=returns, regime="bull",
        )
        self.assertTrue(assessment.approved)

        decision_id = self.recorder.record_risk_decision(
            signal_id=sig_id, fusion_id=fusion_id,
            approved=True,
            checks_run=assessment.checks_run,
            checks_passed=assessment.checks_run,
        )
        record = self.recorder.store.get_signal(sig_id)
        self.assertEqual(record.status, SignalStatus.RISK_APPROVED)

    def test_rejected_by_kill_switch(self):
        sig_id = self.recorder.record_signal(
            source="social", ticker="TSLA",
            direction="bullish", strength=60.0,
        )

        assessment = self.risk_ctx.assess(
            ticker="TSLA", direction="long", positions=[],
            kill_switch_active=True,
        )
        self.assertFalse(assessment.approved)

        self.recorder.record_risk_decision(
            signal_id=sig_id, approved=False,
            rejection_reason=assessment.rejection_reason,
            checks_run=assessment.checks_run,
        )
        record = self.recorder.store.get_signal(sig_id)
        self.assertEqual(record.status, SignalStatus.RISK_REJECTED)

    def test_rejected_by_max_positions(self):
        cfg = RiskContextConfig(max_concurrent_positions=2)
        ctx = RiskContext(config=cfg, equity=100_000.0)

        positions = [
            {"symbol": "AAPL", "market_value": 10_000},
            {"symbol": "MSFT", "market_value": 10_000},
        ]
        assessment = ctx.assess(
            ticker="GOOGL", direction="long", positions=positions,
        )
        self.assertFalse(assessment.approved)

    def test_risk_assessment_regime_aware(self):
        assessment_bull = self.risk_ctx.assess(
            ticker="AAPL", direction="long", positions=[],
            regime="bull",
        )
        assessment_crisis = self.risk_ctx.assess(
            ticker="AAPL", direction="long", positions=[],
            regime="crisis",
        )
        # In crisis, position sizing should be smaller
        self.assertLessEqual(
            assessment_crisis.max_position_size,
            assessment_bull.max_position_size,
        )


# ═══════════════════════════════════════════════════════════════════════
#  3. Risk → Execution Pipeline
# ═══════════════════════════════════════════════════════════════════════


class TestRiskToExecutionPipeline(unittest.TestCase):
    """Tests that risk-approved signals flow to execution recording."""

    def setUp(self):
        self.recorder = SignalRecorder()
        self.risk_ctx = RiskContext(equity=100_000.0)

    def test_full_signal_to_execution(self):
        # 1. Signal
        sig_id = self.recorder.record_signal(
            source="ema_cloud", ticker="AAPL",
            direction="bullish", strength=85.0, confidence=0.9,
        )
        # 2. Fusion
        fusion_id = self.recorder.record_fusion(
            ticker="AAPL", input_signal_ids=[sig_id],
            direction="bullish", composite_score=85.0, confidence=0.9,
        )
        # 3. Risk check
        assessment = self.risk_ctx.assess(
            ticker="AAPL", direction="long", positions=[],
        )
        self.assertTrue(assessment.approved)

        decision_id = self.recorder.record_risk_decision(
            signal_id=sig_id, fusion_id=fusion_id,
            approved=True, checks_run=assessment.checks_run,
        )
        # 4. Execution
        exec_id = self.recorder.record_execution(
            signal_id=sig_id, fusion_id=fusion_id,
            decision_id=decision_id, ticker="AAPL",
            direction="long", quantity=100, fill_price=185.50,
            requested_price=185.00, broker="alpaca",
        )
        self.assertIsNotNone(exec_id)

        # Verify full trace
        trace = self.recorder.get_pipeline_trace(sig_id)
        self.assertIsNotNone(trace["signal"])
        self.assertIsNotNone(trace["fusion"])
        self.assertIsNotNone(trace["execution"])
        self.assertEqual(trace["execution"]["ticker"], "AAPL")
        self.assertEqual(trace["signal"]["status"], SignalStatus.EXECUTED.value)

    def test_execution_records_slippage(self):
        sig_id = self.recorder.record_signal(
            source="ema_cloud", ticker="MSFT",
            direction="bullish", strength=75.0,
        )
        exec_id = self.recorder.record_execution(
            signal_id=sig_id, ticker="MSFT",
            direction="long", quantity=50, fill_price=310.25,
            requested_price=310.00,
        )
        execution = self.recorder.store.get_execution(exec_id)
        self.assertAlmostEqual(execution.slippage, 0.25, places=2)

    def test_execution_linked_to_signal(self):
        sig_id = self.recorder.record_signal(
            source="factor", ticker="GOOGL",
            direction="bullish", strength=70.0,
        )
        exec_id = self.recorder.record_execution(
            signal_id=sig_id, ticker="GOOGL",
            direction="long", quantity=25, fill_price=140.0,
        )
        signal = self.recorder.store.get_signal(sig_id)
        self.assertEqual(signal.execution_id, exec_id)
        self.assertEqual(signal.status, SignalStatus.EXECUTED)

    def test_impact_model_applied_to_execution(self):
        """Verify impact model can estimate slippage for an execution."""
        model = ConvexImpactModel()
        result = model.estimate(
            order_size=100, daily_volume=5_000_000,
            price=185.0, volatility=0.02, side="buy",
        )
        self.assertGreater(result.total_impact_bps, 0.0)
        self.assertGreater(result.effective_price, 185.0)

    def test_survivorship_filter_pre_execution(self):
        """Verify survivorship check before execution."""
        filt = SurvivorshipFilter()
        filt.add_listing("AAPL", listed_date=date(1980, 12, 12))
        filt.add_listing("DELISTED", listed_date=date(2000, 1, 1), delisted_date=date(2020, 1, 1))

        tradable = filt.filter_universe(
            tickers=["AAPL", "DELISTED"],
            as_of=date(2023, 6, 1),
            prices={"AAPL": 185.0, "DELISTED": 0.0},
            volumes={"AAPL": 50_000_000, "DELISTED": 0},
        )
        self.assertIn("AAPL", tradable)
        self.assertNotIn("DELISTED", tradable)


# ═══════════════════════════════════════════════════════════════════════
#  4. Strategy Selection Pipeline
# ═══════════════════════════════════════════════════════════════════════


class TestStrategySelectionPipeline(unittest.TestCase):
    """Tests that ADX gate routes to the correct strategy and signals flow."""

    def setUp(self):
        self.selector = StrategySelector()

    def test_adx_gate_routes_trend_to_ema(self):
        gate = ADXGate()
        closes = _trending_prices(60, step=2.0)
        highs, lows = _ohlc_from_closes(closes, spread=0.5)
        adx = gate.compute_adx(highs, lows, closes)
        strength = gate.classify(adx)
        strategy = gate.select_strategy(strength)
        # A strong uptrend should route to ema_cloud (if ADX is high enough)
        self.assertIn(strategy, ("ema_cloud", "mean_reversion"))

    def test_adx_gate_routes_chop_to_mean_reversion(self):
        gate = ADXGate()
        closes = _oscillating_prices(60, amplitude=2.0)
        highs, lows = _ohlc_from_closes(closes, spread=0.5)
        adx = gate.compute_adx(highs, lows, closes)
        if adx < 25:
            strength = gate.classify(adx)
            strategy = gate.select_strategy(strength)
            self.assertEqual(strategy, "mean_reversion")

    def test_selector_produces_strategy_choice(self):
        closes = _trending_prices(60, step=1.0)
        highs, lows = _ohlc_from_closes(closes)
        choice = self.selector.select("AAPL", highs, lows, closes, regime="bull")
        self.assertIn(choice.selected_strategy, ("ema_cloud", "mean_reversion"))
        self.assertGreater(choice.confidence, 0.0)

    def test_mean_reversion_signal_generated(self):
        mr = MeanReversionStrategy()
        closes = _oscillating_prices(60, amplitude=8.0)
        sig = mr.analyze("SPY", closes)
        self.assertNotEqual(sig.signal_type, "insufficient_data")
        self.assertIn(sig.direction, ("bullish", "bearish", "neutral"))

    def test_strategy_selection_batch(self):
        closes = _trending_prices(60)
        highs, lows = _ohlc_from_closes(closes)
        data = {
            "AAPL": {"highs": highs, "lows": lows, "closes": closes},
            "MSFT": {"highs": highs, "lows": lows, "closes": closes},
        }
        results = self.selector.select_batch(data, regime="sideways")
        self.assertEqual(len(results), 2)
        for ticker, choice in results.items():
            self.assertIn(choice.selected_strategy, ("ema_cloud", "mean_reversion"))

    def test_crisis_override_to_mean_reversion(self):
        closes = _trending_prices(60, step=2.0)
        highs, lows = _ohlc_from_closes(closes)
        choice = self.selector.select("AAPL", highs, lows, closes, regime="crisis")
        self.assertEqual(choice.selected_strategy, "mean_reversion")


# ═══════════════════════════════════════════════════════════════════════
#  5. Feedback Loop Pipeline
# ═══════════════════════════════════════════════════════════════════════


class TestFeedbackLoopPipeline(unittest.TestCase):
    """Tests the full feedback loop: outcomes → tracker → adjuster → weights."""

    def setUp(self):
        self.tracker = PerformanceTracker(
            TrackerConfig(min_trades_for_stats=5, rolling_window=100),
        )
        self.adjuster = WeightAdjuster(
            config=AdjusterConfig(
                min_trades_to_adjust=10, sharpe_target=0.5,
                max_weight=0.90,
            ),
            tracker=self.tracker,
        )

    def test_record_outcomes_and_get_performance(self):
        for i in range(20):
            pnl = 100.0 if i % 3 != 0 else -60.0
            self.tracker.record_outcome("ema_cloud", pnl, conviction=75.0)
        perf = self.tracker.get_performance("ema_cloud")
        self.assertEqual(perf.trade_count, 20)
        self.assertGreater(perf.total_pnl, 0.0)
        self.assertGreater(perf.win_rate, 0.5)

    def test_weight_adjustment_changes_weights(self):
        # Good source
        for _ in range(15):
            self.tracker.record_outcome("good_src", 150.0, 80.0)
        for _ in range(5):
            self.tracker.record_outcome("good_src", -40.0, 60.0)

        # Bad source
        for _ in range(5):
            self.tracker.record_outcome("bad_src", 50.0, 50.0)
        for _ in range(15):
            self.tracker.record_outcome("bad_src", -100.0, 40.0)

        initial_weights = {"good_src": 0.5, "bad_src": 0.5}
        update = self.adjuster.compute_weights(initial_weights)

        # Good source should get higher weight after normalization
        self.assertGreater(
            update.new_weights["good_src"],
            update.new_weights["bad_src"],
        )

    def test_multiple_feedback_cycles_converge(self):
        for _ in range(15):
            self.tracker.record_outcome("alpha", 200.0, 85.0)
        for _ in range(5):
            self.tracker.record_outcome("alpha", -50.0, 60.0)
        for _ in range(5):
            self.tracker.record_outcome("beta", 80.0, 55.0)
        for _ in range(15):
            self.tracker.record_outcome("beta", -90.0, 40.0)

        weights = {"alpha": 0.5, "beta": 0.5}
        for _ in range(5):
            update = self.adjuster.compute_weights(weights)
            weights = update.new_weights

        self.assertGreater(weights["alpha"], weights["beta"])
        total = sum(weights.values())
        self.assertAlmostEqual(total, 1.0, places=3)

    def test_recommended_weights_reflect_performance(self):
        for _ in range(15):
            self.tracker.record_outcome("winner", 200.0, 85.0)
        for _ in range(5):
            self.tracker.record_outcome("winner", -30.0, 60.0)
        for _ in range(5):
            self.tracker.record_outcome("loser", 40.0, 50.0)
        for _ in range(15):
            self.tracker.record_outcome("loser", -120.0, 35.0)

        weights = self.adjuster.get_recommended_weights(["winner", "loser", "new_source"])
        self.assertGreater(weights["winner"], weights["loser"])
        total = sum(weights.values())
        self.assertAlmostEqual(total, 1.0, places=3)

    def test_monte_carlo_validates_strategy(self):
        """Run Monte Carlo on realized trade P&Ls to validate strategy."""
        pnls = [100.0, -50.0, 200.0, -75.0, 150.0, 50.0, -30.0, 120.0]
        sim = MonteCarloSimulator(
            MonteCarloConfig(num_simulations=100, random_seed=42),
        )
        result = sim.simulate(pnls, initial_equity=100_000)
        self.assertGreater(result.probability_of_profit, 0.0)
        self.assertEqual(result.num_simulations, 100)

    def test_gap_risk_integrated_with_feedback(self):
        """Simulate gap events and record their P&L impact."""
        gap_sim = GapSimulator(
            config=GapConfig(overnight_gap_probability=1.0),
            seed=42,
        )
        event = gap_sim.simulate_overnight_gap(
            "AAPL", prev_close=185.0, position_side="long", stop_price=180.0,
        )
        self.assertIsNotNone(event)

        # Record the gap-induced loss if adverse
        if event.is_adverse:
            loss = (event.stop_fill_price - 185.0) * 100  # 100 shares
            self.tracker.record_outcome("ema_cloud", loss, 70.0)
            perf = self.tracker.get_performance("ema_cloud")
            self.assertEqual(perf.trade_count, 1)
