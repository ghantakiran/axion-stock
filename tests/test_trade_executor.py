"""Tests for PRD-135: Autonomous Trade Executor.

Tests the full trade lifecycle: validate -> size -> route -> monitor -> exit.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ema_signals.detector import SignalType, TradeSignal
from src.trade_executor.executor import (
    AccountState,
    ExecutionResult,
    ExecutorConfig,
    InstrumentMode,
    KillSwitch,
    Position,
    PositionSize,
    PositionSizer,
    TradeExecutor,
)
from src.trade_executor.exit_monitor import ExitMonitor, ExitSignal
from src.trade_executor.instrument_router import (
    ETFSelection,
    InstrumentDecision,
    InstrumentRouter,
    LEVERAGED_ETF_CATALOG,
    TICKER_SECTOR_MAP,
)
from src.trade_executor.etf_sizer import LeveragedETFSizer
from src.trade_executor.journal import DailySummary, TradeJournalWriter, TradeRecord
from src.trade_executor.risk_gate import RiskDecision, RiskGate
from src.trade_executor.router import Order, OrderResult, OrderRouter


def _make_signal(**overrides) -> TradeSignal:
    """Helper to create a TradeSignal with sensible defaults."""
    defaults = {
        "signal_type": SignalType.CLOUD_CROSS_BULLISH,
        "direction": "long",
        "ticker": "AAPL",
        "timeframe": "10m",
        "conviction": 80,
        "entry_price": 150.0,
        "stop_loss": 147.0,
        "target_price": 156.0,
        "cloud_states": [],
        "timestamp": datetime.now(timezone.utc),
        "metadata": {},
    }
    defaults.update(overrides)
    return TradeSignal(**defaults)


def _make_position(**overrides) -> Position:
    """Helper to create a Position with sensible defaults."""
    defaults = {
        "ticker": "AAPL",
        "direction": "long",
        "entry_price": 150.0,
        "current_price": 152.0,
        "shares": 100,
        "stop_loss": 147.0,
        "target_price": 156.0,
        "entry_time": datetime.now(timezone.utc) - timedelta(minutes=30),
        "signal_id": "sig-001",
        "trade_type": "day",
        "instrument_type": "stock",
        "leverage": 1.0,
    }
    defaults.update(overrides)
    return Position(**defaults)


def _make_account(**overrides) -> AccountState:
    """Helper to create an AccountState with sensible defaults."""
    defaults = {
        "equity": 100_000.0,
        "cash": 50_000.0,
        "buying_power": 50_000.0,
        "open_positions": [],
        "daily_pnl": 0.0,
        "daily_trades": 0,
        "starting_equity": 100_000.0,
    }
    defaults.update(overrides)
    return AccountState(**defaults)


# ═══════════════════════════════════════════════════════════════════════
# 1. ExecutorConfig & InstrumentMode
# ═══════════════════════════════════════════════════════════════════════


class TestExecutorConfig(unittest.TestCase):
    """Test configuration and enums."""

    def test_default_config_values(self):
        config = ExecutorConfig()
        self.assertEqual(config.max_risk_per_trade, 0.05)
        self.assertEqual(config.max_concurrent_positions, 10)
        self.assertEqual(config.daily_loss_limit, 0.10)
        self.assertEqual(config.min_account_equity, 25_000.0)

    def test_instrument_modes(self):
        self.assertEqual(InstrumentMode.OPTIONS.value, "options")
        self.assertEqual(InstrumentMode.LEVERAGED_ETF.value, "leveraged_etf")
        self.assertEqual(InstrumentMode.BOTH.value, "both")

    def test_custom_config(self):
        config = ExecutorConfig(max_risk_per_trade=0.03, max_concurrent_positions=5)
        self.assertEqual(config.max_risk_per_trade, 0.03)
        self.assertEqual(config.max_concurrent_positions, 5)

    def test_etf_config_defaults(self):
        config = ExecutorConfig()
        self.assertEqual(config.max_etf_hold_days_3x, 5)
        self.assertEqual(config.max_etf_hold_days_2x, 10)
        self.assertTrue(config.prefer_3x_for_day_trades)


# ═══════════════════════════════════════════════════════════════════════
# 2. Position & AccountState
# ═══════════════════════════════════════════════════════════════════════


class TestPosition(unittest.TestCase):
    """Test position data model and computed properties."""

    def test_unrealized_pnl_long_profit(self):
        pos = _make_position(entry_price=100.0, current_price=105.0, shares=50)
        self.assertAlmostEqual(pos.unrealized_pnl, 250.0)

    def test_unrealized_pnl_short_profit(self):
        pos = _make_position(direction="short", entry_price=100.0, current_price=95.0, shares=50)
        self.assertAlmostEqual(pos.unrealized_pnl, 250.0)

    def test_unrealized_pnl_pct(self):
        pos = _make_position(entry_price=100.0, current_price=110.0, shares=10)
        self.assertAlmostEqual(pos.unrealized_pnl_pct, 0.10)

    def test_hold_time(self):
        pos = _make_position(entry_time=datetime.now(timezone.utc) - timedelta(hours=2))
        hold = pos.hold_time
        self.assertGreater(hold.total_seconds(), 7000)

    def test_to_dict(self):
        pos = _make_position()
        d = pos.to_dict()
        self.assertIn("ticker", d)
        self.assertIn("unrealized_pnl", d)
        self.assertIn("trade_type", d)

    def test_account_daily_pnl_pct(self):
        acct = _make_account(daily_pnl=-5000.0, starting_equity=100_000.0)
        self.assertAlmostEqual(acct.daily_pnl_pct, -0.05)

    def test_account_exposure_pct(self):
        pos = _make_position(current_price=100.0, shares=200)
        acct = _make_account(equity=100_000.0, open_positions=[pos])
        self.assertAlmostEqual(acct.exposure_pct, 0.20)


# ═══════════════════════════════════════════════════════════════════════
# 3. PositionSizer
# ═══════════════════════════════════════════════════════════════════════


class TestPositionSizer(unittest.TestCase):
    """Test position sizing logic."""

    def setUp(self):
        self.config = ExecutorConfig()
        self.sizer = PositionSizer(self.config)

    def test_high_conviction_full_size(self):
        signal = _make_signal(conviction=80, entry_price=150.0, stop_loss=147.0)
        account = _make_account()
        size = self.sizer.calculate(signal, account)
        self.assertGreater(size.shares, 0)
        self.assertEqual(size.conviction_multiplier, 1.0)
        self.assertEqual(size.order_type, "market")

    def test_medium_conviction_half_size(self):
        signal = _make_signal(conviction=50, entry_price=150.0, stop_loss=147.0)
        account = _make_account()
        size = self.sizer.calculate(signal, account)
        self.assertGreater(size.shares, 0)
        self.assertLessEqual(size.conviction_multiplier, 0.5)

    def test_minimum_one_share(self):
        signal = _make_signal(conviction=50, entry_price=50_000.0, stop_loss=49_000.0)
        account = _make_account(equity=10_000.0)
        size = self.sizer.calculate(signal, account)
        self.assertEqual(size.shares, 1)

    def test_capped_by_exposure_limit(self):
        signal = _make_signal(conviction=90, entry_price=10.0, stop_loss=9.99)
        account = _make_account(equity=100_000.0)
        size = self.sizer.calculate(signal, account)
        max_shares = int(100_000 * 0.15 / 10.0)
        self.assertLessEqual(size.shares, max_shares)

    def test_tight_stop_uses_default(self):
        signal = _make_signal(conviction=80, entry_price=100.0, stop_loss=99.99)
        account = _make_account()
        size = self.sizer.calculate(signal, account)
        self.assertGreater(size.shares, 0)


# ═══════════════════════════════════════════════════════════════════════
# 4. RiskGate
# ═══════════════════════════════════════════════════════════════════════


class TestRiskGate(unittest.TestCase):
    """Test pre-trade risk validation."""

    def setUp(self):
        self.config = ExecutorConfig()
        self.gate = RiskGate(self.config)

    def _market_hours_dt(self):
        """Return a datetime during market hours (2 PM ET = 19:00 UTC)."""
        return datetime(2024, 6, 15, 19, 0, 0, tzinfo=timezone.utc)

    def test_approve_valid_signal(self):
        signal = _make_signal(timeframe="1d")
        account = _make_account()
        decision = self.gate.validate(signal, account)
        self.assertTrue(decision.approved)

    def test_reject_daily_loss_limit(self):
        signal = _make_signal()
        account = _make_account(daily_pnl=-11_000.0, starting_equity=100_000.0)
        decision = self.gate.validate(signal, account)
        self.assertFalse(decision.approved)
        self.assertIn("loss limit", decision.reason)

    def test_reject_max_positions(self):
        positions = [_make_position(ticker=f"T{i}") for i in range(10)]
        signal = _make_signal()
        account = _make_account(open_positions=positions)
        decision = self.gate.validate(signal, account)
        self.assertFalse(decision.approved)
        self.assertIn("Max positions", decision.reason)

    def test_reject_duplicate_losing_ticker(self):
        pos = _make_position(ticker="AAPL", current_price=148.0)  # losing
        signal = _make_signal(ticker="AAPL")
        account = _make_account(open_positions=[pos])
        decision = self.gate.validate(signal, account)
        self.assertFalse(decision.approved)

    def test_allow_adding_to_winner(self):
        pos = _make_position(ticker="AAPL", current_price=155.0, direction="long", shares=50)
        signal = _make_signal(ticker="AAPL", direction="long", timeframe="1d")
        account = _make_account(open_positions=[pos], equity=200_000.0)
        decision = self.gate.validate(signal, account)
        self.assertTrue(decision.approved)

    def test_reject_conflicting_direction(self):
        pos = _make_position(ticker="AAPL", direction="long", current_price=155.0)
        signal = _make_signal(ticker="AAPL", direction="short")
        account = _make_account(open_positions=[pos])
        decision = self.gate.validate(signal, account)
        self.assertFalse(decision.approved)

    def test_reject_low_equity(self):
        signal = _make_signal(timeframe="1d")
        account = _make_account(equity=20_000.0)
        decision = self.gate.validate(signal, account)
        self.assertFalse(decision.approved)
        self.assertIn("Equity", decision.reason)

    def test_reject_insufficient_buying_power(self):
        signal = _make_signal(entry_price=500.0, timeframe="1d")
        account = _make_account(buying_power=1_000.0)
        decision = self.gate.validate(signal, account)
        self.assertFalse(decision.approved)
        self.assertIn("buying power", decision.reason)

    def test_risk_decision_to_dict(self):
        d = RiskDecision(approved=True).to_dict()
        self.assertIn("approved", d)


# ═══════════════════════════════════════════════════════════════════════
# 5. OrderRouter
# ═══════════════════════════════════════════════════════════════════════


class TestOrderRouter(unittest.TestCase):
    """Test order routing with paper and live modes."""

    def test_paper_fill(self):
        router = OrderRouter(paper_mode=True)
        order = Order(
            ticker="AAPL", side="buy", qty=100,
            order_type="limit", limit_price=150.0,
        )
        result = router.submit_order(order)
        self.assertEqual(result.status, "filled")
        self.assertEqual(result.filled_qty, 100)
        self.assertEqual(result.broker, "paper")
        self.assertIn("PAPER", result.order_id)

    def test_paper_market_order_default_price(self):
        router = OrderRouter(paper_mode=True)
        order = Order(ticker="AAPL", side="buy", qty=50, order_type="market")
        result = router.submit_order(order)
        self.assertEqual(result.filled_price, 100.0)

    def test_live_mode_no_client_rejects(self):
        router = OrderRouter(paper_mode=False)
        order = Order(ticker="AAPL", side="buy", qty=100, order_type="market")
        result = router.submit_order(order)
        self.assertEqual(result.status, "rejected")

    def test_order_history_tracked(self):
        router = OrderRouter(paper_mode=True)
        order = Order(ticker="MSFT", side="buy", qty=10, order_type="market")
        router.submit_order(order)
        self.assertEqual(len(router.get_order_history()), 1)

    def test_cancel_order(self):
        router = OrderRouter(paper_mode=True)
        self.assertTrue(router.cancel_order("ORD-123"))

    def test_order_to_dict(self):
        order = Order(ticker="AAPL", side="buy", qty=100, order_type="market")
        d = order.to_dict()
        self.assertEqual(d["ticker"], "AAPL")

    def test_order_result_to_dict(self):
        result = OrderResult(
            order_id="O1", status="filled", filled_qty=10,
            filled_price=150.0, broker="paper",
        )
        d = result.to_dict()
        self.assertEqual(d["status"], "filled")


# ═══════════════════════════════════════════════════════════════════════
# 6. ExitMonitor
# ═══════════════════════════════════════════════════════════════════════


class TestExitMonitor(unittest.TestCase):
    """Test 7 exit strategies."""

    def setUp(self):
        self.monitor = ExitMonitor()

    def test_stop_loss_long_triggered(self):
        pos = _make_position(direction="long", stop_loss=145.0)
        sig = self.monitor.check_stop_loss(pos, 144.0)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.exit_type, "stop_loss")
        self.assertEqual(sig.priority, 1)

    def test_stop_loss_not_triggered(self):
        pos = _make_position(direction="long", stop_loss=145.0)
        sig = self.monitor.check_stop_loss(pos, 150.0)
        self.assertIsNone(sig)

    def test_stop_loss_short_triggered(self):
        pos = _make_position(direction="short", stop_loss=155.0)
        sig = self.monitor.check_stop_loss(pos, 156.0)
        self.assertIsNotNone(sig)

    def test_profit_target_long_hit(self):
        pos = _make_position(direction="long", entry_price=150.0, stop_loss=147.0,
                             target_price=156.0)
        sig = self.monitor.check_profit_target(pos, 157.0)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.exit_type, "target")

    def test_profit_target_calculated_from_rr(self):
        pos = _make_position(direction="long", entry_price=150.0, stop_loss=147.0,
                             target_price=None)
        # Default R:R = 2:1, risk = 3, target = 150 + 6 = 156
        sig = self.monitor.check_profit_target(pos, 157.0)
        self.assertIsNotNone(sig)

    def test_time_stop_triggered(self):
        pos = _make_position(
            trade_type="day",
            entry_time=datetime.now(timezone.utc) - timedelta(hours=3),
            current_price=150.0,
            entry_price=150.0,
        )
        sig = self.monitor.check_time_stop(pos)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.exit_type, "time_stop")

    def test_time_stop_not_for_swing(self):
        pos = _make_position(
            trade_type="swing",
            entry_time=datetime.now(timezone.utc) - timedelta(hours=3),
        )
        sig = self.monitor.check_time_stop(pos)
        self.assertIsNone(sig)

    def test_trailing_stop_swing_triggered(self):
        pos = _make_position(direction="long", trade_type="swing")
        bars = pd.DataFrame({
            "close": [150.0, 149.0, 148.0, 145.0],
            "ema_8": [150.0, 149.5, 149.0, 148.5],
            "ema_9": [150.5, 150.0, 149.5, 149.0],
        })
        sig = self.monitor.check_trailing_stop(pos, bars)
        self.assertIsNotNone(sig)
        self.assertEqual(sig.exit_type, "trailing")

    def test_check_all_returns_highest_priority(self):
        pos = _make_position(direction="long", stop_loss=155.0, target_price=140.0)
        sig = self.monitor.check_all(pos, current_price=140.0)
        # Both stop_loss and target should trigger; stop_loss has higher priority
        self.assertIsNotNone(sig)
        self.assertEqual(sig.exit_type, "stop_loss")

    def test_check_all_no_exit(self):
        pos = _make_position(direction="long", stop_loss=140.0, target_price=160.0,
                             trade_type="swing")
        sig = self.monitor.check_all(pos, current_price=150.0)
        self.assertIsNone(sig)

    def test_exit_signal_to_dict(self):
        sig = ExitSignal(ticker="AAPL", exit_type="stop_loss", priority=1, reason="test")
        d = sig.to_dict()
        self.assertEqual(d["exit_type"], "stop_loss")

    def test_momentum_exhaustion_no_data(self):
        pos = _make_position(direction="long")
        bars = pd.DataFrame({"close": [1, 2]})
        sig = self.monitor.check_momentum_exhaustion(pos, bars)
        self.assertIsNone(sig)

    def test_cloud_flip_triggers(self):
        from src.ema_signals.clouds import CloudState
        pos = _make_position(direction="long")
        cloud = CloudState(
            cloud_name="fast", short_ema=10.0, long_ema=12.0,
            is_bullish=False, thickness=2.0,
            price_above=False, price_inside=False, price_below=True,
        )
        sig = self.monitor.check_cloud_flip(pos, [cloud])
        self.assertIsNotNone(sig)
        self.assertEqual(sig.exit_type, "cloud_flip")


# ═══════════════════════════════════════════════════════════════════════
# 7. TradeJournalWriter
# ═══════════════════════════════════════════════════════════════════════


class TestTradeJournal(unittest.TestCase):
    """Test trade journaling and daily summaries."""

    def setUp(self):
        self.journal = TradeJournalWriter()

    def test_record_exit_computes_pnl(self):
        pos = _make_position(direction="long", entry_price=100.0, shares=100)
        record = self.journal.record_exit(pos, "target", exit_price=110.0)
        self.assertAlmostEqual(record.pnl, 1000.0)

    def test_record_exit_short(self):
        pos = _make_position(direction="short", entry_price=100.0, shares=50)
        record = self.journal.record_exit(pos, "stop_loss", exit_price=95.0)
        self.assertAlmostEqual(record.pnl, 250.0)

    def test_daily_summary_empty(self):
        from datetime import date
        summary = self.journal.get_daily_summary(date(2020, 1, 1))
        self.assertEqual(summary.total_trades, 0)
        self.assertEqual(summary.net_pnl, 0.0)

    def test_daily_summary_with_trades(self):
        # Add two trades
        pos1 = _make_position(direction="long", entry_price=100.0, shares=100)
        pos2 = _make_position(direction="long", entry_price=50.0, shares=200, signal_id="sig-002")
        self.journal.record_exit(pos1, "target", exit_price=110.0)
        self.journal.record_exit(pos2, "stop_loss", exit_price=48.0)

        # Use UTC date since record_exit uses datetime.now(timezone.utc)
        utc_today = datetime.now(timezone.utc).date()
        summary = self.journal.get_daily_summary(utc_today)
        self.assertEqual(summary.total_trades, 2)
        self.assertEqual(summary.winning_trades, 1)
        self.assertEqual(summary.losing_trades, 1)

    def test_trade_history_filter_by_ticker(self):
        pos1 = _make_position(ticker="AAPL")
        pos2 = _make_position(ticker="MSFT", signal_id="sig-002")
        self.journal.record_exit(pos1, "target", exit_price=155.0)
        self.journal.record_exit(pos2, "target", exit_price=300.0)
        history = self.journal.get_trade_history(ticker="AAPL")
        self.assertEqual(len(history), 1)

    def test_all_trades_property(self):
        pos = _make_position()
        self.journal.record_exit(pos, "target", exit_price=155.0)
        self.assertEqual(len(self.journal.all_trades), 1)

    def test_trade_record_to_dict(self):
        pos = _make_position()
        record = self.journal.record_exit(pos, "target", exit_price=155.0)
        d = record.to_dict()
        self.assertIn("pnl", d)
        self.assertIn("ticker", d)

    def test_daily_summary_to_dict(self):
        from datetime import date
        summary = self.journal.get_daily_summary(date.today())
        d = summary.to_dict()
        self.assertIn("date", d)
        self.assertIn("win_rate", d)


# ═══════════════════════════════════════════════════════════════════════
# 8. InstrumentRouter
# ═══════════════════════════════════════════════════════════════════════


class TestInstrumentRouter(unittest.TestCase):
    """Test instrument routing to correct trade vehicles."""

    def test_options_mode_scalp(self):
        router = InstrumentRouter(mode=InstrumentMode.OPTIONS)
        signal = _make_signal(ticker="AAPL")
        decision = router.route(signal, trade_type="scalp")
        self.assertEqual(decision.instrument_type, "option")

    def test_options_mode_day(self):
        router = InstrumentRouter(mode=InstrumentMode.OPTIONS)
        signal = _make_signal(ticker="AAPL")
        decision = router.route(signal, trade_type="day")
        self.assertEqual(decision.instrument_type, "stock")

    def test_etf_mode_routes_to_etf(self):
        router = InstrumentRouter(mode=InstrumentMode.LEVERAGED_ETF)
        signal = _make_signal(ticker="AAPL", direction="long")
        decision = router.route(signal)
        self.assertEqual(decision.instrument_type, "leveraged_etf")
        self.assertEqual(decision.ticker, "TECL")
        self.assertEqual(decision.leverage, 3.0)
        self.assertFalse(decision.is_inverse)

    def test_etf_mode_short_uses_inverse(self):
        router = InstrumentRouter(mode=InstrumentMode.LEVERAGED_ETF)
        signal = _make_signal(ticker="AAPL", direction="short")
        decision = router.route(signal)
        self.assertEqual(decision.ticker, "TECS")
        self.assertTrue(decision.is_inverse)

    def test_both_mode_scalp_to_options(self):
        router = InstrumentRouter(mode=InstrumentMode.BOTH)
        signal = _make_signal(ticker="AAPL")
        decision = router.route(signal, trade_type="scalp")
        self.assertEqual(decision.instrument_type, "option")

    def test_both_mode_day_to_etf(self):
        router = InstrumentRouter(mode=InstrumentMode.BOTH)
        signal = _make_signal(ticker="NVDA", direction="long")
        decision = router.route(signal, trade_type="day")
        self.assertEqual(decision.instrument_type, "leveraged_etf")
        self.assertEqual(decision.ticker, "SOXL")

    def test_both_mode_swing_to_stock(self):
        router = InstrumentRouter(mode=InstrumentMode.BOTH)
        signal = _make_signal(ticker="AAPL")
        decision = router.route(signal, trade_type="swing")
        self.assertEqual(decision.instrument_type, "stock")

    def test_select_etf_qqq(self):
        router = InstrumentRouter()
        signal = _make_signal(ticker="QQQ", direction="long")
        etf = router.select_etf(signal)
        self.assertIsNotNone(etf)
        self.assertEqual(etf.ticker, "TQQQ")

    def test_select_etf_unknown_defaults_nasdaq(self):
        router = InstrumentRouter()
        signal = _make_signal(ticker="UNKNOWN_TICKER", direction="long")
        etf = router.select_etf(signal)
        self.assertIsNotNone(etf)
        self.assertEqual(etf.tracks, "NASDAQ-100")

    def test_get_available_etfs(self):
        router = InstrumentRouter()
        all_etfs = router.get_available_etfs()
        self.assertEqual(len(all_etfs), len(LEVERAGED_ETF_CATALOG))

    def test_get_available_etfs_filtered(self):
        router = InstrumentRouter()
        semi_etfs = router.get_available_etfs(sector="Semiconductors")
        self.assertEqual(len(semi_etfs), 2)

    def test_etf_catalog_has_pairs(self):
        # Every sector should have bull + bear
        sectors = set(m["tracks"] for m in LEVERAGED_ETF_CATALOG.values())
        for sector in sectors:
            entries = [m for m in LEVERAGED_ETF_CATALOG.values() if m["tracks"] == sector]
            directions = {m["direction"] for m in entries}
            self.assertIn("bull", directions, f"No bull ETF for {sector}")
            self.assertIn("bear", directions, f"No bear ETF for {sector}")

    def test_instrument_decision_to_dict(self):
        d = InstrumentDecision(
            instrument_type="stock", ticker="AAPL",
            original_signal_ticker="AAPL",
        ).to_dict()
        self.assertEqual(d["instrument_type"], "stock")

    def test_etf_selection_to_dict(self):
        d = ETFSelection(
            ticker="TQQQ", leverage=3.0, tracks="NASDAQ-100", is_inverse=False,
        ).to_dict()
        self.assertEqual(d["leverage"], 3.0)


# ═══════════════════════════════════════════════════════════════════════
# 9. LeveragedETFSizer
# ═══════════════════════════════════════════════════════════════════════


class TestLeveragedETFSizer(unittest.TestCase):
    """Test leverage-adjusted position sizing."""

    def setUp(self):
        self.config = ExecutorConfig()
        self.sizer = LeveragedETFSizer(self.config)

    def test_3x_etf_sizing(self):
        signal = _make_signal(conviction=80, entry_price=50.0, stop_loss=48.0)
        etf = ETFSelection(ticker="TQQQ", leverage=3.0, tracks="NASDAQ-100", is_inverse=False)
        account = _make_account()
        size = self.sizer.calculate(signal, etf, account)
        self.assertGreater(size.shares, 0)

    def test_leverage_reduces_exposure(self):
        signal = _make_signal(conviction=80, entry_price=50.0, stop_loss=48.0)
        account = _make_account()
        etf_3x = ETFSelection(ticker="TQQQ", leverage=3.0, tracks="NASDAQ-100", is_inverse=False)
        etf_2x = ETFSelection(ticker="QLD", leverage=2.0, tracks="NASDAQ-100", is_inverse=False)
        size_3x = self.sizer.calculate(signal, etf_3x, account)
        size_2x = self.sizer.calculate(signal, etf_2x, account)
        # 3x should have fewer shares than 2x for same risk
        self.assertLessEqual(size_3x.shares, size_2x.shares)

    def test_max_hold_days(self):
        self.assertEqual(self.sizer.max_hold_days(3.0), 5)
        self.assertEqual(self.sizer.max_hold_days(2.0), 10)
        self.assertEqual(self.sizer.max_hold_days(1.5), 15)

    def test_decay_warning(self):
        warning = self.sizer.decay_warning(3.0, 7)
        self.assertIsNotNone(warning)
        self.assertIn("decay", warning)

    def test_no_decay_warning_within_limit(self):
        warning = self.sizer.decay_warning(3.0, 3)
        self.assertIsNone(warning)


# ═══════════════════════════════════════════════════════════════════════
# 10. KillSwitch & TradeExecutor
# ═══════════════════════════════════════════════════════════════════════


class TestKillSwitch(unittest.TestCase):
    """Test emergency stop conditions."""

    def test_not_active_initially(self):
        ks = KillSwitch(ExecutorConfig())
        self.assertFalse(ks.active)

    def test_daily_loss_triggers(self):
        ks = KillSwitch(ExecutorConfig())
        account = _make_account(daily_pnl=-11_000.0, starting_equity=100_000.0)
        self.assertTrue(ks.check(account))
        self.assertTrue(ks.active)

    def test_low_equity_triggers(self):
        ks = KillSwitch(ExecutorConfig())
        account = _make_account(equity=20_000.0, starting_equity=30_000.0)
        self.assertTrue(ks.check(account))

    def test_consecutive_losses_trigger(self):
        ks = KillSwitch(ExecutorConfig(consecutive_loss_threshold=3, consecutive_loss_pct=0.03))
        ks.record_trade_result(-0.05)
        ks.record_trade_result(-0.04)
        ks.record_trade_result(-0.03)
        account = _make_account()
        self.assertTrue(ks.check(account))

    def test_winning_trade_resets_streak(self):
        ks = KillSwitch(ExecutorConfig(consecutive_loss_threshold=3))
        ks.record_trade_result(-0.05)
        ks.record_trade_result(-0.04)
        ks.record_trade_result(0.02)  # Win resets
        ks.record_trade_result(-0.05)
        account = _make_account()
        self.assertFalse(ks.check(account))

    def test_deactivate(self):
        ks = KillSwitch(ExecutorConfig())
        ks.activate("test")
        self.assertTrue(ks.active)
        ks.deactivate()
        self.assertFalse(ks.active)


class TestTradeExecutor(unittest.TestCase):
    """Test the main execution engine."""

    def test_process_valid_signal(self):
        executor = TradeExecutor()
        signal = _make_signal(timeframe="1d")  # daily bypasses market hours check
        account = _make_account()
        result = executor.process_signal(signal, account)
        self.assertTrue(result.success)
        self.assertIsNotNone(result.position)
        self.assertEqual(len(executor.positions), 1)

    def test_kill_switch_blocks_signal(self):
        executor = TradeExecutor()
        executor.kill_switch.activate("test halt")
        signal = _make_signal()
        account = _make_account()
        result = executor.process_signal(signal, account)
        self.assertFalse(result.success)
        self.assertIn("Kill switch", result.rejection_reason)

    def test_close_position(self):
        executor = TradeExecutor()
        pos = _make_position(ticker="AAPL")
        executor.positions.append(pos)
        closed = executor.close_position("AAPL", "target")
        self.assertIsNotNone(closed)
        self.assertEqual(len(executor.positions), 0)

    def test_close_nonexistent_position(self):
        executor = TradeExecutor()
        closed = executor.close_position("XYZ", "target")
        self.assertIsNone(closed)

    def test_get_account_snapshot(self):
        executor = TradeExecutor()
        pos = _make_position()
        executor.positions.append(pos)
        snap = executor.get_account_snapshot(equity=100_000.0, cash=50_000.0)
        self.assertEqual(snap.equity, 100_000.0)
        self.assertEqual(len(snap.open_positions), 1)

    def test_classify_trade_type(self):
        self.assertEqual(TradeExecutor._classify_trade_type("1m"), "scalp")
        self.assertEqual(TradeExecutor._classify_trade_type("5m"), "scalp")
        self.assertEqual(TradeExecutor._classify_trade_type("10m"), "day")
        self.assertEqual(TradeExecutor._classify_trade_type("1h"), "swing")
        self.assertEqual(TradeExecutor._classify_trade_type("1d"), "swing")

    def test_execution_result_to_dict(self):
        signal = _make_signal()
        result = ExecutionResult(success=True, signal=signal, order_id="ORD-1")
        d = result.to_dict()
        self.assertTrue(d["success"])
        self.assertEqual(d["order_id"], "ORD-1")


# ═══════════════════════════════════════════════════════════════════════
# 11. Module Imports
# ═══════════════════════════════════════════════════════════════════════


class TestModuleImports(unittest.TestCase):
    """Test that all public symbols are importable."""

    def test_import_all(self):
        from src.trade_executor import (
            TradeExecutor, ExecutorConfig, InstrumentMode,
            AccountState, Position, PositionSize, ExecutionResult,
            PositionSizer, KillSwitch,
            RiskGate, RiskDecision,
            OrderRouter, Order, OrderResult,
            InstrumentRouter, InstrumentDecision, ETFSelection,
            LEVERAGED_ETF_CATALOG,
            LeveragedETFSizer,
            ExitMonitor, ExitSignal,
            TradeJournalWriter, TradeRecord, DailySummary,
        )
        self.assertTrue(callable(TradeExecutor))
        self.assertTrue(callable(InstrumentRouter))
        self.assertTrue(callable(LeveragedETFSizer))

    def test_leveraged_etf_catalog_not_empty(self):
        self.assertGreater(len(LEVERAGED_ETF_CATALOG), 10)


if __name__ == "__main__":
    unittest.main()
