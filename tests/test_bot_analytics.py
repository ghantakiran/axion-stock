"""PRD-175: Live Bot Analytics — tests.

Tests metrics functions, BotPerformanceTracker, and PerformanceSnapshot.
~40 tests across 4 classes.
"""

from __future__ import annotations

import pytest

from src.bot_analytics.metrics import calmar_ratio, max_drawdown, sharpe_ratio, sortino_ratio
from src.bot_analytics.snapshot import PerformanceSnapshot
from src.bot_analytics.tracker import BotPerformanceTracker, TradeRecord


# ═════════════════════════════════════════════════════════════════════
# Test Metrics Functions
# ═════════════════════════════════════════════════════════════════════


class TestMetrics:
    """Test pure metric calculation functions."""

    def test_sharpe_empty(self):
        assert sharpe_ratio([]) == 0.0

    def test_sharpe_single_value(self):
        assert sharpe_ratio([100.0]) == 0.0

    def test_sharpe_positive_series(self):
        pnls = [10, 20, 15, 25, 30, 18, 22, 28, 12, 35]
        s = sharpe_ratio(pnls)
        assert s > 0

    def test_sharpe_negative_series(self):
        pnls = [-10, -20, -15, -25, -30]
        s = sharpe_ratio(pnls)
        assert s < 0

    def test_sharpe_zero_std(self):
        pnls = [10, 10, 10, 10]
        assert sharpe_ratio(pnls) == 0.0

    def test_sortino_empty(self):
        assert sortino_ratio([]) == 0.0

    def test_sortino_all_positive(self):
        pnls = [10, 20, 15, 25, 30]
        s = sortino_ratio(pnls)
        assert s == 10.0  # Capped positive (no downside)

    def test_sortino_with_losses(self):
        pnls = [10, -5, 20, -10, 15, -3, 25]
        s = sortino_ratio(pnls)
        assert s > 0

    def test_calmar_empty(self):
        assert calmar_ratio([]) == 0.0

    def test_calmar_no_drawdown(self):
        pnls = [10, 10, 10, 10]
        assert calmar_ratio(pnls) == 0.0  # max_drawdown is 0

    def test_calmar_with_drawdown(self):
        pnls = [100, -50, 30, -20, 80]
        c = calmar_ratio(pnls)
        assert c > 0

    def test_max_drawdown_empty(self):
        assert max_drawdown([]) == 0.0

    def test_max_drawdown_all_positive(self):
        assert max_drawdown([10, 20, 30]) == 0.0

    def test_max_drawdown_with_decline(self):
        pnls = [100, -50, 30]
        dd = max_drawdown(pnls)
        assert dd == 50.0  # Peak at 100, trough at 50

    def test_max_drawdown_multiple_dips(self):
        pnls = [50, -20, 30, -40, 10]
        dd = max_drawdown(pnls)
        # Cumulative: 50, 30, 60, 20, 30
        # Peak=60, trough=20, dd=40
        assert dd == 40.0

    def test_max_drawdown_single_loss(self):
        pnls = [-100]
        dd = max_drawdown(pnls)
        assert dd == 100.0


# ═════════════════════════════════════════════════════════════════════
# Test BotPerformanceTracker
# ═════════════════════════════════════════════════════════════════════


class TestBotPerformanceTracker:
    """Test the performance tracking engine."""

    def test_initial_state(self):
        tracker = BotPerformanceTracker()
        assert tracker.get_equity() == 100_000.0
        assert tracker.get_trade_count() == 0

    def test_record_winning_trade(self):
        tracker = BotPerformanceTracker()
        tracker.record_trade("AAPL", "long", 150.0, signal_type="ema_cloud")
        assert tracker.get_equity() == 100_150.0
        assert tracker.get_trade_count() == 1

    def test_record_losing_trade(self):
        tracker = BotPerformanceTracker()
        tracker.record_trade("TSLA", "long", -200.0, signal_type="ema_cloud")
        assert tracker.get_equity() == 99_800.0

    def test_equity_curve_grows(self):
        tracker = BotPerformanceTracker()
        tracker.record_trade("A", "long", 100.0)
        tracker.record_trade("B", "long", -50.0)
        snap = tracker.get_snapshot()
        assert len(snap.equity_curve) == 3  # initial + 2 trades

    def test_by_signal_breakdown(self):
        tracker = BotPerformanceTracker()
        tracker.record_trade("AAPL", "long", 100.0, signal_type="ema_cloud")
        tracker.record_trade("NVDA", "long", -30.0, signal_type="vwap_reversion")
        snap = tracker.get_snapshot()
        assert "ema_cloud" in snap.by_signal
        assert "vwap_reversion" in snap.by_signal
        assert snap.by_signal["ema_cloud"]["trades"] == 1
        assert snap.by_signal["ema_cloud"]["wins"] == 1

    def test_by_strategy_breakdown(self):
        tracker = BotPerformanceTracker()
        tracker.record_trade("AAPL", "long", 100.0, strategy="ema_cloud")
        tracker.record_trade("NVDA", "long", 50.0, strategy="orb_breakout")
        snap = tracker.get_snapshot()
        assert "ema_cloud" in snap.by_strategy
        assert "orb_breakout" in snap.by_strategy

    def test_win_rate_calculation(self):
        tracker = BotPerformanceTracker()
        tracker.record_trade("A", "long", 100.0)
        tracker.record_trade("B", "long", -50.0)
        tracker.record_trade("C", "long", 200.0)
        snap = tracker.get_snapshot()
        assert abs(snap.win_rate - 2 / 3) < 0.01

    def test_snapshot_metrics_populated(self):
        tracker = BotPerformanceTracker()
        for i in range(20):
            pnl = 50 if i % 3 != 0 else -30
            tracker.record_trade(f"T{i}", "long", pnl)
        snap = tracker.get_snapshot()
        assert snap.total_trades == 20
        assert snap.sharpe != 0  # Should have enough data
        assert snap.total_pnl != 0

    def test_get_recent_trades(self):
        tracker = BotPerformanceTracker()
        tracker.record_trade("AAPL", "long", 100.0, exit_reason="target")
        tracker.record_trade("NVDA", "short", -50.0, exit_reason="stop_loss")
        recent = tracker.get_recent_trades(limit=1)
        assert len(recent) == 1
        assert recent[0]["ticker"] == "NVDA"

    def test_max_history_bounded(self):
        tracker = BotPerformanceTracker(max_history=5)
        for i in range(10):
            tracker.record_trade(f"T{i}", "long", 10.0)
        assert tracker.get_trade_count() == 5


# ═════════════════════════════════════════════════════════════════════
# Test PerformanceSnapshot
# ═════════════════════════════════════════════════════════════════════


class TestPerformanceSnapshot:
    """Test PerformanceSnapshot dataclass."""

    def test_empty_snapshot(self):
        snap = PerformanceSnapshot()
        assert snap.total_trades == 0
        assert snap.win_rate == 0.0

    def test_snapshot_to_dict(self):
        snap = PerformanceSnapshot(
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            win_rate=0.6,
            total_pnl=500.0,
            avg_pnl=50.0,
            sharpe=1.5,
            sortino=2.0,
            calmar=1.2,
            max_drawdown=200.0,
        )
        d = snap.to_dict()
        assert d["total_trades"] == 10
        assert d["sharpe"] == 1.5
        assert "timestamp" in d

    def test_snapshot_has_equity_curve_len(self):
        snap = PerformanceSnapshot(equity_curve=[100, 110, 105, 120])
        d = snap.to_dict()
        assert d["equity_curve_len"] == 4


# ═════════════════════════════════════════════════════════════════════
# Test TradeRecord
# ═════════════════════════════════════════════════════════════════════


class TestTradeRecord:
    """Test TradeRecord dataclass."""

    def test_trade_record_defaults(self):
        record = TradeRecord(ticker="AAPL", direction="long", pnl=100.0)
        assert record.signal_type == "unknown"
        assert record.strategy == "unknown"

    def test_trade_record_with_all_fields(self):
        record = TradeRecord(
            ticker="NVDA",
            direction="short",
            pnl=-50.0,
            signal_type="ema_cloud",
            strategy="orb_breakout",
            entry_price=300.0,
            exit_price=305.0,
            shares=10.0,
            exit_reason="stop_loss",
        )
        assert record.ticker == "NVDA"
        assert record.strategy == "orb_breakout"
