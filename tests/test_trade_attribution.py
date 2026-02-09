"""Tests for Live Trade Attribution System (PRD-160).

Covers config, signal-trade linking, P&L decomposition, rolling
signal performance tracking, and the unified attribution engine.
"""
import math
import unittest
from datetime import datetime, timedelta

from src.trade_attribution.config import (
    AttributionConfig,
    DecompositionMethod,
    TimeWindow,
)
from src.trade_attribution.linker import (
    LinkedTrade,
    LinkageReport,
    TradeSignalLinker,
)
from src.trade_attribution.decomposer import (
    DecompositionReport,
    PnLBreakdown,
    TradeDecomposer,
)
from src.trade_attribution.tracker import (
    RollingSignalStats,
    SignalPerformanceTracker,
    TrackerSnapshot,
)
from src.trade_attribution.engine import (
    AttributionEngine,
    AttributionResult,
    LiveAttributionReport,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_signal(
    symbol: str = "AAPL",
    signal_type: str = "ema_cross",
    conviction: int = 80,
    timestamp: datetime | None = None,
    signal_id: str = "sig-001",
    direction: str = "long",
) -> dict:
    return {
        "signal_id": signal_id,
        "signal_type": signal_type,
        "symbol": symbol,
        "direction": direction,
        "conviction": conviction,
        "timestamp": timestamp or datetime.utcnow(),
    }


def _make_trade(
    trade_id: str = "t-001",
    symbol: str = "AAPL",
    entry_price: float = 150.0,
    exit_price: float = 155.0,
    entry_time: datetime | None = None,
    exit_time: datetime | None = None,
    shares: float = 100.0,
    pnl: float | None = None,
    exit_reason: str = "target",
    broker: str = "alpaca",
    direction: str = "long",
    regime_at_entry: str = "",
    regime_at_exit: str = "",
) -> dict:
    now = datetime.utcnow()
    et = entry_time or now
    xt = exit_time or (et + timedelta(hours=2))
    calculated_pnl = pnl if pnl is not None else (exit_price - entry_price) * shares
    return {
        "trade_id": trade_id,
        "symbol": symbol,
        "entry_price": entry_price,
        "exit_price": exit_price,
        "entry_time": et,
        "exit_time": xt,
        "shares": shares,
        "pnl": calculated_pnl,
        "exit_reason": exit_reason,
        "broker": broker,
        "direction": direction,
        "regime_at_entry": regime_at_entry,
        "regime_at_exit": regime_at_exit,
    }


# ---------------------------------------------------------------------------
# 1. TestAttributionConfig
# ---------------------------------------------------------------------------

class TestAttributionConfig(unittest.TestCase):
    """Tests for AttributionConfig dataclass and enums."""

    def test_default_config(self):
        cfg = AttributionConfig()
        self.assertEqual(cfg.decomposition_method, DecompositionMethod.SIMPLE)
        self.assertEqual(cfg.max_signal_age_seconds, 300)
        self.assertTrue(cfg.match_by_conviction)
        self.assertTrue(cfg.include_costs)
        self.assertAlmostEqual(cfg.commission_per_share, 0.005)
        self.assertAlmostEqual(cfg.decay_factor, 0.95)
        self.assertEqual(cfg.min_trades_for_stats, 5)
        self.assertTrue(cfg.track_by_regime)

    def test_custom_windows(self):
        cfg = AttributionConfig(
            windows=[TimeWindow.LAST_100, TimeWindow.LAST_90D]
        )
        self.assertEqual(len(cfg.windows), 2)
        self.assertIn(TimeWindow.LAST_100, cfg.windows)
        self.assertIn(TimeWindow.LAST_90D, cfg.windows)

    def test_decomposition_method_enum(self):
        self.assertEqual(DecompositionMethod.SIMPLE.value, "simple")
        self.assertEqual(DecompositionMethod.VWAP.value, "vwap")
        self.assertEqual(DecompositionMethod.IMPLEMENTATION.value, "implementation")
        # str enum membership
        self.assertIsInstance(DecompositionMethod.SIMPLE, str)

    def test_cost_config_override(self):
        cfg = AttributionConfig(
            commission_per_share=0.01,
            slippage_model="fixed",
            include_costs=False,
        )
        self.assertAlmostEqual(cfg.commission_per_share, 0.01)
        self.assertEqual(cfg.slippage_model, "fixed")
        self.assertFalse(cfg.include_costs)

    def test_time_window_enum_values(self):
        self.assertEqual(TimeWindow.LAST_20.value, "last_20")
        self.assertEqual(TimeWindow.LAST_50.value, "last_50")
        self.assertEqual(TimeWindow.LAST_7D.value, "last_7d")
        self.assertEqual(TimeWindow.LAST_30D.value, "last_30d")
        self.assertEqual(TimeWindow.ALL_TIME.value, "all_time")
        # Seven total members
        self.assertEqual(len(TimeWindow), 7)

    def test_regime_source_default(self):
        cfg = AttributionConfig()
        self.assertEqual(cfg.regime_source, "regime_signals")


# ---------------------------------------------------------------------------
# 2. TestTradeSignalLinker
# ---------------------------------------------------------------------------

class TestTradeSignalLinker(unittest.TestCase):
    """Tests for TradeSignalLinker matching and buffer management."""

    def setUp(self):
        self.linker = TradeSignalLinker()

    def test_register_signal(self):
        sig = _make_signal()
        self.linker.register_signal(sig)
        self.assertEqual(len(self.linker._signal_buffer), 1)
        self.assertEqual(self.linker._signal_buffer[0]["signal_id"], "sig-001")

    def test_link_exact_match(self):
        now = datetime.utcnow()
        sig = _make_signal(timestamp=now, signal_id="sig-100", conviction=90)
        self.linker.register_signal(sig)
        trade = _make_trade(
            trade_id="t-100", entry_time=now + timedelta(seconds=5),
            exit_time=now + timedelta(hours=1),
        )
        linked = self.linker.link_trade(trade)
        self.assertEqual(linked.signal_id, "sig-100")
        self.assertEqual(linked.signal_conviction, 90)
        self.assertEqual(linked.trade_id, "t-100")

    def test_link_fuzzy_time_proximity(self):
        """Closer signal in time should be preferred."""
        now = datetime.utcnow()
        sig_old = _make_signal(
            timestamp=now - timedelta(seconds=200),
            signal_id="old", conviction=80,
        )
        sig_new = _make_signal(
            timestamp=now - timedelta(seconds=10),
            signal_id="new", conviction=80,
        )
        self.linker.register_signal(sig_old)
        self.linker.register_signal(sig_new)
        trade = _make_trade(trade_id="t-fuzzy", entry_time=now)
        linked = self.linker.link_trade(trade)
        self.assertEqual(linked.signal_id, "new")

    def test_no_match_time_too_old(self):
        now = datetime.utcnow()
        sig = _make_signal(
            timestamp=now - timedelta(seconds=600), signal_id="stale"
        )
        self.linker.register_signal(sig)
        trade = _make_trade(trade_id="t-old", entry_time=now)
        linked = self.linker.link_trade(trade)
        self.assertEqual(linked.signal_id, "")
        self.assertEqual(linked.signal_type, "unknown")

    def test_buffer_trim_at_1000(self):
        for i in range(1050):
            self.linker.register_signal(
                _make_signal(signal_id=f"s-{i}")
            )
        # After 1001st signal, buffer should have been trimmed to 500,
        # then grow to 1050-1000+500 = 550 (trimmed at 1001, then added 49 more)
        # Actually: trim happens when > 1000; at 1001 trim to 500, then 1002..1050 add 49 -> 549
        self.assertLessEqual(len(self.linker._signal_buffer), 600)
        self.assertGreater(len(self.linker._signal_buffer), 0)

    def test_linkage_report(self):
        now = datetime.utcnow()
        self.linker.register_signal(
            _make_signal(timestamp=now, signal_id="s1")
        )
        self.linker.link_trade(
            _make_trade(trade_id="t1", entry_time=now + timedelta(seconds=1))
        )
        self.linker.link_trade(
            _make_trade(
                trade_id="t2", symbol="MSFT",
                entry_time=now + timedelta(seconds=1),
            )
        )
        report = self.linker.get_linkage_report()
        self.assertIsInstance(report, LinkageReport)
        self.assertEqual(report.total_trades, 2)
        self.assertEqual(report.linked_trades, 1)
        self.assertEqual(report.unlinked_trades, 1)
        self.assertAlmostEqual(report.linkage_rate, 0.5)
        self.assertIn("t2", report.unlinked_trade_ids)

    def test_clear(self):
        self.linker.register_signal(_make_signal())
        self.linker.link_trade(_make_trade())
        self.linker.clear()
        self.assertEqual(len(self.linker._signal_buffer), 0)
        self.assertEqual(len(self.linker._linked_trades), 0)

    def test_time_window_filter_symbol_mismatch(self):
        """Signal for different symbol should not match."""
        now = datetime.utcnow()
        self.linker.register_signal(
            _make_signal(symbol="GOOG", timestamp=now, signal_id="goog-sig")
        )
        trade = _make_trade(
            trade_id="t-aapl", symbol="AAPL", entry_time=now
        )
        linked = self.linker.link_trade(trade)
        self.assertEqual(linked.signal_id, "")

    def test_conviction_bonus_scoring(self):
        """Higher conviction signal should beat zero-conviction when time-equal."""
        now = datetime.utcnow()
        self.linker.register_signal(
            _make_signal(
                timestamp=now - timedelta(seconds=10),
                signal_id="no-conv", conviction=0,
            )
        )
        self.linker.register_signal(
            _make_signal(
                timestamp=now - timedelta(seconds=10),
                signal_id="hi-conv", conviction=90,
            )
        )
        trade = _make_trade(trade_id="t-conv", entry_time=now)
        linked = self.linker.link_trade(trade)
        self.assertEqual(linked.signal_id, "hi-conv")

    def test_pnl_pct_calculation(self):
        """Linker should calculate realized_pnl_pct from entry/exit prices."""
        now = datetime.utcnow()
        self.linker.register_signal(_make_signal(timestamp=now))
        trade = _make_trade(
            trade_id="t-pct", entry_price=100.0, exit_price=110.0,
            shares=50, entry_time=now + timedelta(seconds=1),
        )
        linked = self.linker.link_trade(trade)
        # pnl_pct = (110-100)/100 = 0.1
        self.assertAlmostEqual(linked.realized_pnl_pct, 0.1, places=4)

    def test_hold_duration_calculated(self):
        """Linker should compute hold duration from entry/exit times."""
        now = datetime.utcnow()
        self.linker.register_signal(_make_signal(timestamp=now))
        trade = _make_trade(
            trade_id="t-hold",
            entry_time=now + timedelta(seconds=1),
            exit_time=now + timedelta(seconds=1, hours=3),
        )
        linked = self.linker.link_trade(trade)
        self.assertEqual(linked.hold_duration_seconds, 3 * 3600)


# ---------------------------------------------------------------------------
# 3. TestLinkedTrade
# ---------------------------------------------------------------------------

class TestLinkedTrade(unittest.TestCase):
    """Tests for LinkedTrade dataclass."""

    def test_to_dict_keys(self):
        lt = LinkedTrade(
            trade_id="t-1", signal_id="s-1", symbol="TSLA",
            entry_price=200.0, exit_price=210.0, entry_shares=50,
            realized_pnl=500.0, realized_pnl_pct=0.05,
            hold_duration_seconds=3600,
            entry_time=datetime(2025, 1, 1, 10, 0, 0),
            exit_time=datetime(2025, 1, 1, 11, 0, 0),
        )
        d = lt.to_dict()
        expected_keys = {
            "trade_id", "signal_id", "signal_type", "signal_conviction",
            "signal_direction", "symbol", "entry_price", "entry_time",
            "entry_shares", "exit_price", "exit_time", "exit_reason",
            "realized_pnl", "realized_pnl_pct", "hold_duration_seconds",
            "regime_at_entry", "regime_at_exit", "broker",
        }
        self.assertEqual(set(d.keys()), expected_keys)
        self.assertEqual(d["trade_id"], "t-1")
        self.assertAlmostEqual(d["realized_pnl"], 500.0)

    def test_is_winner_property(self):
        self.assertTrue(
            LinkedTrade(trade_id="w", realized_pnl=1.0).is_winner
        )
        self.assertFalse(
            LinkedTrade(trade_id="l", realized_pnl=-1.0).is_winner
        )
        self.assertFalse(
            LinkedTrade(trade_id="z", realized_pnl=0.0).is_winner
        )

    def test_hold_duration_hours(self):
        lt = LinkedTrade(trade_id="h", hold_duration_seconds=7200)
        self.assertAlmostEqual(lt.hold_duration_hours, 2.0)

    def test_pnl_pct_round_trip(self):
        lt = LinkedTrade(trade_id="p", realized_pnl_pct=0.03456)
        d = lt.to_dict()
        self.assertAlmostEqual(d["realized_pnl_pct"], 0.0346, places=4)

    def test_default_field_values(self):
        lt = LinkedTrade(trade_id="defaults")
        self.assertEqual(lt.signal_id, "")
        self.assertEqual(lt.signal_type, "unknown")
        self.assertEqual(lt.signal_conviction, 0)
        self.assertEqual(lt.signal_direction, "long")
        self.assertAlmostEqual(lt.entry_price, 0.0)
        self.assertAlmostEqual(lt.realized_pnl, 0.0)
        self.assertFalse(lt.is_winner)

    def test_entry_time_iso_format(self):
        dt = datetime(2025, 6, 15, 14, 30, 0)
        lt = LinkedTrade(trade_id="iso", entry_time=dt, exit_time=dt)
        d = lt.to_dict()
        self.assertEqual(d["entry_time"], "2025-06-15T14:30:00")


# ---------------------------------------------------------------------------
# 4. TestTradeDecomposer
# ---------------------------------------------------------------------------

class TestTradeDecomposer(unittest.TestCase):
    """Tests for P&L decomposition logic."""

    def setUp(self):
        self.decomposer = TradeDecomposer()

    def test_simple_decompose_default_bars(self):
        """Without explicit bars, default bars are used (entry +/- 0.5%)."""
        trade = _make_trade(
            trade_id="d-1", entry_price=100.0, exit_price=105.0, shares=100,
        )
        bd = self.decomposer.decompose(trade)
        self.assertEqual(bd.trade_id, "d-1")
        self.assertAlmostEqual(bd.total_pnl, 500.0)
        # With default bars, entry_mid = (100*1.005 + 100*0.995)/2 = 100.0
        # So entry quality should be ~0 for default bars
        self.assertAlmostEqual(bd.entry_quality, 0.0, places=1)

    def test_decompose_with_explicit_bars(self):
        trade = _make_trade(
            trade_id="d-2", entry_price=100.0, exit_price=110.0,
            shares=50, pnl=500.0,
        )
        entry_bar = {"open": 99.0, "high": 102.0, "low": 98.0, "close": 101.0}
        exit_bar = {"open": 109.0, "high": 112.0, "low": 108.0, "close": 111.0}
        bd = self.decomposer.decompose(trade, entry_bar, exit_bar)
        # entry_mid = (102 + 98) / 2 = 100.0, exit_mid = (112 + 108) / 2 = 110.0
        # entry_quality = (100 - 100) * 50 * 1.0 = 0
        self.assertAlmostEqual(bd.entry_quality, 0.0, places=2)
        # market_movement = (110 - 100) * 50 * 1.0 = 500
        self.assertAlmostEqual(bd.market_movement, 500.0, places=2)
        # exit_timing = (110 - 110) * 50 * 1.0 = 0
        self.assertAlmostEqual(bd.exit_timing, 0.0, places=2)
        self.assertGreater(bd.transaction_costs, 0.0)

    def test_batch_decompose(self):
        trades = [
            _make_trade(trade_id="b-1", entry_price=100, exit_price=105, shares=10),
            _make_trade(trade_id="b-2", entry_price=200, exit_price=195, shares=20, pnl=-100.0),
        ]
        report = self.decomposer.decompose_batch(trades)
        self.assertIsInstance(report, DecompositionReport)
        self.assertEqual(len(report.breakdowns), 2)
        self.assertAlmostEqual(
            report.total_pnl,
            report.breakdowns[0].total_pnl + report.breakdowns[1].total_pnl,
        )

    def test_entry_score_long_at_low(self):
        """Long entry at low of bar should give entry_score near +1."""
        trade = _make_trade(
            trade_id="es-1", entry_price=98.0, exit_price=105.0, shares=10,
        )
        entry_bar = {"open": 99, "high": 102, "low": 98, "close": 101}
        bd = self.decomposer.decompose(trade, entry_bar)
        self.assertAlmostEqual(bd.entry_score, 1.0, places=2)

    def test_entry_score_short_at_high(self):
        """Short entry at high of bar should give entry_score near +1."""
        trade = _make_trade(
            trade_id="es-2", entry_price=102.0, exit_price=98.0,
            shares=10, direction="short",
        )
        entry_bar = {"open": 99, "high": 102, "low": 98, "close": 100}
        bd = self.decomposer.decompose(trade, entry_bar)
        self.assertAlmostEqual(bd.entry_score, 1.0, places=2)

    def test_exit_score_long_at_high(self):
        """Long exit at high of bar should give exit_score near +1."""
        trade = _make_trade(
            trade_id="xs-1", entry_price=100.0, exit_price=112.0, shares=10,
        )
        exit_bar = {"open": 109, "high": 112, "low": 108, "close": 111}
        bd = self.decomposer.decompose(trade, exit_bar=exit_bar)
        self.assertAlmostEqual(bd.exit_score, 1.0, places=2)

    def test_transaction_costs_positive(self):
        trade = _make_trade(
            trade_id="tc-1", entry_price=100.0, exit_price=101.0, shares=100,
        )
        bd = self.decomposer.decompose(trade)
        # commission = 0.005 * 100 * 2 = 1.0
        # sqrt impact = 0.01 * sqrt(100) * 100 / 100 = 0.01 * 10 * 1 = 0.1
        expected_commission = 0.005 * 100 * 2
        expected_impact = 0.01 * math.sqrt(100) * 100.0 / 100
        self.assertAlmostEqual(
            bd.transaction_costs, expected_commission + expected_impact, places=4
        )

    def test_decomposition_report_to_dict(self):
        """DecompositionReport.to_dict() should include trade_count."""
        trades = [
            _make_trade(trade_id="rd-1", entry_price=100, exit_price=103, shares=10),
            _make_trade(trade_id="rd-2", entry_price=200, exit_price=210, shares=5),
        ]
        report = self.decomposer.decompose_batch(trades)
        d = report.to_dict()
        self.assertEqual(d["trade_count"], 2)
        self.assertIn("avg_entry_score", d)
        self.assertIn("avg_exit_score", d)

    def test_entry_score_midpoint_zero(self):
        """Entry at bar midpoint should yield entry_score near 0."""
        trade = _make_trade(
            trade_id="mid-1", entry_price=100.0, exit_price=105.0, shares=10,
        )
        entry_bar = {"open": 99, "high": 102, "low": 98, "close": 101}
        # midpoint = (102+98)/2 = 100, entry at 100 => score = 1 - 2*(100-98)/4 = 0
        bd = self.decomposer.decompose(trade, entry_bar)
        self.assertAlmostEqual(bd.entry_score, 0.0, places=2)

    def test_direction_multiplier_short(self):
        """Short trade: positive pnl when price drops."""
        trade = _make_trade(
            trade_id="dm-1", entry_price=100.0, exit_price=95.0,
            shares=10, direction="short",
            pnl=50.0,  # (100-95)*10
        )
        entry_bar = {"open": 99, "high": 102, "low": 98, "close": 100}
        exit_bar = {"open": 96, "high": 97, "low": 94, "close": 95}
        bd = self.decomposer.decompose(trade, entry_bar, exit_bar)
        # direction = -1
        # entry_mid = 100, exit_mid = 95.5
        # entry_quality = (100-100)*10*(-1) = 0
        # market_movement = (95.5 - 100)*10*(-1) = 45
        # exit_timing = (95 - 95.5)*10*(-1) = 5
        self.assertAlmostEqual(bd.entry_quality, 0.0, places=2)
        self.assertAlmostEqual(bd.market_movement, 45.0, places=2)
        self.assertAlmostEqual(bd.exit_timing, 5.0, places=2)


# ---------------------------------------------------------------------------
# 5. TestPnLBreakdown
# ---------------------------------------------------------------------------

class TestPnLBreakdown(unittest.TestCase):
    """Tests for PnLBreakdown dataclass."""

    def test_to_dict_all_keys(self):
        bd = PnLBreakdown(
            trade_id="p-1", symbol="SPY", total_pnl=100.0,
            entry_quality=30.0, market_movement=60.0,
            exit_timing=15.0, transaction_costs=2.0, residual=-3.0,
            entry_score=0.5, exit_score=0.7,
        )
        d = bd.to_dict()
        self.assertEqual(d["trade_id"], "p-1")
        self.assertEqual(d["total_pnl"], 100.0)
        self.assertIn("entry_score", d)
        self.assertIn("exit_score", d)
        self.assertIn("residual", d)

    def test_percentage_fields(self):
        bd = PnLBreakdown(
            total_pnl=200.0,
            entry_quality_pct=0.4,
            market_movement_pct=0.5,
            exit_timing_pct=0.08,
            cost_pct=0.02,
        )
        d = bd.to_dict()
        self.assertAlmostEqual(d["entry_quality_pct"], 0.4, places=4)
        self.assertAlmostEqual(d["market_movement_pct"], 0.5, places=4)
        total_pct = (
            d["entry_quality_pct"] + d["market_movement_pct"]
            + d["exit_timing_pct"] + d["cost_pct"]
        )
        self.assertAlmostEqual(total_pct, 1.0, places=4)

    def test_residual_calculation(self):
        """Residual should capture the gap between total PnL and component sum."""
        decomposer = TradeDecomposer()
        trade = _make_trade(
            trade_id="r-1", entry_price=100.0, exit_price=105.0,
            shares=100, pnl=500.0,
        )
        bd = decomposer.decompose(trade)
        component_sum = (
            bd.entry_quality + bd.market_movement + bd.exit_timing - bd.transaction_costs
        )
        self.assertAlmostEqual(
            bd.residual, bd.total_pnl - component_sum, places=6
        )


# ---------------------------------------------------------------------------
# 6. TestSignalPerformanceTracker
# ---------------------------------------------------------------------------

class TestSignalPerformanceTracker(unittest.TestCase):
    """Tests for rolling signal performance tracking."""

    def _linked_trade(
        self, signal_type="ema_cross", pnl=100.0, conviction=80,
        hold_secs=3600, regime="bull", exit_time=None,
    ):
        return LinkedTrade(
            trade_id=f"lt-{id(pnl)}",
            signal_type=signal_type,
            signal_conviction=conviction,
            realized_pnl=pnl,
            realized_pnl_pct=pnl / 10000.0,
            hold_duration_seconds=hold_secs,
            regime_at_entry=regime,
            exit_time=exit_time or datetime.utcnow(),
        )

    def test_record_trade(self):
        tracker = SignalPerformanceTracker()
        lt = self._linked_trade()
        tracker.record_trade(lt)
        self.assertEqual(tracker.get_trade_count(), 1)

    def test_snapshot_with_windows(self):
        cfg = AttributionConfig(windows=[TimeWindow.LAST_20, TimeWindow.ALL_TIME])
        tracker = SignalPerformanceTracker(cfg)
        for i in range(10):
            tracker.record_trade(
                self._linked_trade(pnl=float(10 + i))
            )
        snap = tracker.get_snapshot()
        self.assertIsInstance(snap, TrackerSnapshot)
        self.assertIn("ema_cross", snap.by_signal_type)
        # Should have stats for each window
        stats_list = snap.by_signal_type["ema_cross"]
        windows = {s.window for s in stats_list}
        self.assertIn("last_20", windows)
        self.assertIn("all_time", windows)

    def test_regime_tracking(self):
        tracker = SignalPerformanceTracker()
        tracker.record_trade(self._linked_trade(regime="bull", pnl=50.0))
        tracker.record_trade(self._linked_trade(regime="bear", pnl=-20.0))
        snap = tracker.get_snapshot()
        self.assertIn("bull", snap.by_regime)
        self.assertIn("bear", snap.by_regime)

    def test_sharpe_calculation(self):
        """Sharpe = mean/stdev * sqrt(252) when >= 2 trades."""
        tracker = SignalPerformanceTracker()
        pnls = [100.0, 50.0, 75.0, 120.0, 60.0]
        for p in pnls:
            tracker.record_trade(self._linked_trade(pnl=p))
        snap = tracker.get_snapshot()
        overall = snap.overall
        self.assertIsNotNone(overall)
        self.assertGreater(overall.sharpe_ratio, 0.0)
        # Verify rough magnitude
        import statistics
        mean_r = statistics.mean(pnls)
        std_r = statistics.stdev(pnls)
        expected = (mean_r / std_r) * (252 ** 0.5)
        self.assertAlmostEqual(overall.sharpe_ratio, expected, places=2)

    def test_best_worst_signal_type(self):
        cfg = AttributionConfig(windows=[TimeWindow.ALL_TIME])
        tracker = SignalPerformanceTracker(cfg)
        # 5+ trades for "good" signals (all winners)
        for _ in range(6):
            tracker.record_trade(
                self._linked_trade(signal_type="good", pnl=100.0)
            )
        # 5+ trades for "bad" signals (all losers)
        for _ in range(6):
            tracker.record_trade(
                self._linked_trade(signal_type="bad", pnl=-50.0)
            )
        snap = tracker.get_snapshot()
        self.assertEqual(snap.get_best_signal_type("all_time"), "good")
        self.assertEqual(snap.get_worst_signal_type("all_time"), "bad")

    def test_profit_factor(self):
        cfg = AttributionConfig(windows=[TimeWindow.ALL_TIME])
        tracker = SignalPerformanceTracker(cfg)
        # 3 wins of 100, 2 losses of -50
        for _ in range(3):
            tracker.record_trade(self._linked_trade(pnl=100.0))
        for _ in range(2):
            tracker.record_trade(self._linked_trade(pnl=-50.0))
        snap = tracker.get_snapshot()
        overall = snap.overall
        # profit_factor = 300 / 100 = 3.0
        self.assertAlmostEqual(overall.profit_factor, 3.0, places=2)

    def test_win_rate(self):
        cfg = AttributionConfig(windows=[TimeWindow.ALL_TIME])
        tracker = SignalPerformanceTracker(cfg)
        tracker.record_trade(self._linked_trade(pnl=100.0))
        tracker.record_trade(self._linked_trade(pnl=50.0))
        tracker.record_trade(self._linked_trade(pnl=-30.0))
        snap = tracker.get_snapshot()
        self.assertAlmostEqual(snap.overall.win_rate, 2 / 3, places=4)

    def test_clear(self):
        tracker = SignalPerformanceTracker()
        tracker.record_trade(self._linked_trade())
        tracker.clear()
        self.assertEqual(tracker.get_trade_count(), 0)


# ---------------------------------------------------------------------------
# 7. TestAttributionEngine
# ---------------------------------------------------------------------------

class TestAttributionEngine(unittest.TestCase):
    """Tests for the unified AttributionEngine."""

    def test_register_and_attribute(self):
        engine = AttributionEngine()
        now = datetime.utcnow()
        engine.register_signal(
            _make_signal(timestamp=now, signal_id="e-sig-1")
        )
        result = engine.attribute_trade(
            _make_trade(
                trade_id="e-t-1",
                entry_time=now + timedelta(seconds=2),
                exit_time=now + timedelta(hours=1),
            )
        )
        self.assertIsInstance(result, AttributionResult)
        self.assertEqual(result.linked_trade.signal_id, "e-sig-1")
        self.assertIsNotNone(result.breakdown)

    def test_multi_trade_pipeline(self):
        engine = AttributionEngine()
        now = datetime.utcnow()
        for i in range(5):
            engine.register_signal(
                _make_signal(
                    timestamp=now + timedelta(seconds=i * 10),
                    signal_id=f"ms-{i}",
                )
            )
            engine.attribute_trade(
                _make_trade(
                    trade_id=f"mt-{i}",
                    entry_time=now + timedelta(seconds=i * 10 + 1),
                    exit_time=now + timedelta(seconds=i * 10 + 3600),
                )
            )
        self.assertEqual(engine.get_trade_count(), 5)

    def test_get_report_structure(self):
        engine = AttributionEngine()
        now = datetime.utcnow()
        engine.register_signal(_make_signal(timestamp=now))
        engine.attribute_trade(
            _make_trade(
                entry_time=now + timedelta(seconds=1),
                exit_time=now + timedelta(hours=1),
            )
        )
        report = engine.get_report()
        self.assertIsInstance(report, LiveAttributionReport)
        self.assertEqual(report.total_trades, 1)
        self.assertIsNotNone(report.linkage_report)
        self.assertIsNotNone(report.decomposition_report)
        self.assertIsNotNone(report.performance_snapshot)

    def test_to_dict(self):
        engine = AttributionEngine()
        now = datetime.utcnow()
        engine.register_signal(_make_signal(timestamp=now))
        engine.attribute_trade(
            _make_trade(
                entry_time=now + timedelta(seconds=1),
                exit_time=now + timedelta(hours=1),
            )
        )
        report = engine.get_report()
        d = report.to_dict()
        self.assertIn("total_trades", d)
        self.assertIn("total_pnl", d)
        self.assertIn("results", d)
        self.assertIn("linkage", d)
        self.assertIn("decomposition", d)
        self.assertIn("performance", d)

    def test_to_dataframe(self):
        engine = AttributionEngine()
        now = datetime.utcnow()
        engine.register_signal(_make_signal(timestamp=now))
        engine.attribute_trade(
            _make_trade(
                entry_time=now + timedelta(seconds=1),
                exit_time=now + timedelta(hours=1),
            )
        )
        report = engine.get_report()
        df = report.to_dataframe()
        self.assertGreater(len(df), 0)
        self.assertIn("trade_id", df.columns)

    def test_clear(self):
        engine = AttributionEngine()
        now = datetime.utcnow()
        engine.register_signal(_make_signal(timestamp=now))
        engine.attribute_trade(
            _make_trade(
                entry_time=now + timedelta(seconds=1),
                exit_time=now + timedelta(hours=1),
            )
        )
        engine.clear()
        self.assertEqual(engine.get_trade_count(), 0)

    def test_unlinked_trade_no_signal(self):
        engine = AttributionEngine()
        result = engine.attribute_trade(
            _make_trade(trade_id="orphan", symbol="NVDA")
        )
        self.assertEqual(result.linked_trade.signal_id, "")
        self.assertEqual(result.linked_trade.signal_type, "unknown")
        self.assertIsNotNone(result.breakdown)

    def test_full_pipeline_end_to_end(self):
        """Complete flow: register signals, attribute trades, get report, verify totals."""
        engine = AttributionEngine()
        now = datetime.utcnow()

        # Register 3 signals
        for i in range(3):
            engine.register_signal(
                _make_signal(
                    symbol="SPY",
                    signal_type="momentum",
                    conviction=70 + i * 10,
                    timestamp=now + timedelta(seconds=i * 100),
                    signal_id=f"fp-sig-{i}",
                )
            )

        # Execute 3 trades with known PnLs
        expected_pnl = 0.0
        for i in range(3):
            entry_p = 400.0 + i
            exit_p = 405.0 + i
            shares = 10.0
            pnl = (exit_p - entry_p) * shares
            expected_pnl += pnl
            engine.attribute_trade(
                _make_trade(
                    trade_id=f"fp-t-{i}",
                    symbol="SPY",
                    entry_price=entry_p,
                    exit_price=exit_p,
                    shares=shares,
                    pnl=pnl,
                    entry_time=now + timedelta(seconds=i * 100 + 5),
                    exit_time=now + timedelta(seconds=i * 100 + 3600),
                )
            )

        report = engine.get_report()
        self.assertEqual(report.total_trades, 3)
        self.assertAlmostEqual(report.total_pnl, expected_pnl, places=2)
        self.assertEqual(report.linkage_report.linked_trades, 3)
        self.assertAlmostEqual(report.linkage_report.linkage_rate, 1.0)


# ---------------------------------------------------------------------------
# 8. TestModuleImports
# ---------------------------------------------------------------------------

class TestModuleImports(unittest.TestCase):
    """Tests for module exports and importability."""

    def test_all_exports_importable(self):
        import src.trade_attribution as mod
        self.assertEqual(len(mod.__all__), 15)
        for name in mod.__all__:
            obj = getattr(mod, name, None)
            self.assertIsNotNone(obj, f"{name} is not importable from src.trade_attribution")

    def test_config_defaults_accessible(self):
        from src.trade_attribution import AttributionConfig, TimeWindow
        cfg = AttributionConfig()
        # Default windows should contain LAST_20, LAST_50, ALL_TIME
        self.assertIn(TimeWindow.LAST_20, cfg.windows)
        self.assertIn(TimeWindow.LAST_50, cfg.windows)
        self.assertIn(TimeWindow.ALL_TIME, cfg.windows)
        self.assertEqual(len(cfg.windows), 3)

    def test_dataclass_types(self):
        """Key classes should be importable and instantiable."""
        from src.trade_attribution import (
            LinkedTrade, PnLBreakdown, RollingSignalStats,
            AttributionResult, LiveAttributionReport,
        )
        self.assertIsInstance(LinkedTrade(trade_id="x"), LinkedTrade)
        self.assertIsInstance(PnLBreakdown(), PnLBreakdown)
        self.assertIsInstance(RollingSignalStats(), RollingSignalStats)
        self.assertIsInstance(AttributionResult(), AttributionResult)
        self.assertIsInstance(LiveAttributionReport(), LiveAttributionReport)


if __name__ == "__main__":
    unittest.main()
