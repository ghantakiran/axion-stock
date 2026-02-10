"""Tests for PRD-171: Bot Lifecycle Hardening.

Tests cover:
- SignalGuard: freshness, dedup, window expiry, concurrent access
- LifecycleManager: price updates, exit detection, emergency close, portfolio snapshot
- BotOrchestrator lifecycle: stale signal rejection, duplicate rejection, journal
  wiring, instrument routing, daily loss auto-kill, history cap
- Paper mode fix: market order pricing, limit order pricing, entry_price fallback
"""

from __future__ import annotations

import tempfile
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.ema_signals.detector import SignalType, TradeSignal
from src.trade_executor.executor import AccountState, ExecutorConfig, Position
from src.trade_executor.router import Order, OrderResult, OrderRouter


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════


def _make_signal(
    ticker: str = "AAPL",
    direction: str = "long",
    conviction: int = 80,
    entry_price: float = 150.0,
    stop_loss: float = 145.0,
    timeframe: str = "1d",
    signal_type: SignalType = SignalType.CLOUD_BOUNCE_LONG,
    timestamp: datetime | None = None,
) -> TradeSignal:
    return TradeSignal(
        signal_type=signal_type,
        direction=direction,
        ticker=ticker,
        timeframe=timeframe,
        conviction=conviction,
        entry_price=entry_price,
        stop_loss=stop_loss,
        target_price=entry_price * 1.04,
        timestamp=timestamp or datetime.now(timezone.utc),
    )


def _make_account() -> AccountState:
    return AccountState(
        equity=100_000.0,
        cash=50_000.0,
        buying_power=200_000.0,
        starting_equity=100_000.0,
    )


def _make_position(
    ticker: str = "AAPL",
    direction: str = "long",
    entry_price: float = 150.0,
    current_price: float = 150.0,
    shares: int = 100,
    stop_loss: float = 145.0,
) -> Position:
    return Position(
        ticker=ticker,
        direction=direction,
        entry_price=entry_price,
        current_price=current_price,
        shares=shares,
        stop_loss=stop_loss,
        target_price=entry_price * 1.04,
        entry_time=datetime.now(timezone.utc),
        signal_id="test-signal-1",
        trade_type="swing",
    )


# ═══════════════════════════════════════════════════════════════════════
# TestSignalGuard
# ═══════════════════════════════════════════════════════════════════════


class TestSignalGuard:
    """Tests for signal freshness and deduplication."""

    def test_fresh_signal_passes(self):
        from src.bot_pipeline.signal_guard import SignalGuard

        guard = SignalGuard(max_age_seconds=120)
        signal = _make_signal()
        assert guard.is_fresh(signal) is True

    def test_stale_signal_rejected(self):
        from src.bot_pipeline.signal_guard import SignalGuard

        guard = SignalGuard(max_age_seconds=60)
        stale_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        signal = _make_signal(timestamp=stale_time)
        assert guard.is_fresh(signal) is False

    def test_signal_at_boundary_passes(self):
        from src.bot_pipeline.signal_guard import SignalGuard

        guard = SignalGuard(max_age_seconds=120)
        # 119 seconds old — just under the limit
        ts = datetime.now(timezone.utc) - timedelta(seconds=119)
        signal = _make_signal(timestamp=ts)
        assert guard.is_fresh(signal) is True

    def test_first_signal_not_duplicate(self):
        from src.bot_pipeline.signal_guard import SignalGuard

        guard = SignalGuard(dedup_window_seconds=300)
        signal = _make_signal()
        assert guard.is_duplicate(signal) is False

    def test_same_signal_is_duplicate(self):
        from src.bot_pipeline.signal_guard import SignalGuard

        guard = SignalGuard(dedup_window_seconds=300)
        signal = _make_signal()
        guard.is_duplicate(signal)  # First call — records it
        assert guard.is_duplicate(signal) is True  # Second call — duplicate

    def test_different_ticker_not_duplicate(self):
        from src.bot_pipeline.signal_guard import SignalGuard

        guard = SignalGuard(dedup_window_seconds=300)
        guard.is_duplicate(_make_signal(ticker="AAPL"))
        assert guard.is_duplicate(_make_signal(ticker="NVDA")) is False

    def test_different_direction_not_duplicate(self):
        from src.bot_pipeline.signal_guard import SignalGuard

        guard = SignalGuard(dedup_window_seconds=300)
        guard.is_duplicate(_make_signal(direction="long"))
        assert guard.is_duplicate(_make_signal(direction="short")) is False

    def test_different_signal_type_not_duplicate(self):
        from src.bot_pipeline.signal_guard import SignalGuard

        guard = SignalGuard(dedup_window_seconds=300)
        guard.is_duplicate(_make_signal(signal_type=SignalType.CLOUD_BOUNCE_LONG))
        assert guard.is_duplicate(_make_signal(signal_type=SignalType.CLOUD_FLIP_BULLISH)) is False

    def test_dedup_window_expiry(self):
        from src.bot_pipeline.signal_guard import SignalGuard

        guard = SignalGuard(dedup_window_seconds=0.1)  # 100ms window
        signal = _make_signal()
        guard.is_duplicate(signal)
        time.sleep(0.15)  # Wait for window to expire
        assert guard.is_duplicate(signal) is False  # Should pass after expiry

    def test_combined_check_passes(self):
        from src.bot_pipeline.signal_guard import SignalGuard

        guard = SignalGuard()
        signal = _make_signal()
        assert guard.check(signal) is None

    def test_combined_check_rejects_stale(self):
        from src.bot_pipeline.signal_guard import SignalGuard

        guard = SignalGuard(max_age_seconds=30)
        stale = _make_signal(timestamp=datetime.now(timezone.utc) - timedelta(seconds=60))
        result = guard.check(stale)
        assert result is not None
        assert "Stale" in result

    def test_combined_check_rejects_duplicate(self):
        from src.bot_pipeline.signal_guard import SignalGuard

        guard = SignalGuard()
        signal = _make_signal()
        guard.check(signal)  # First pass
        result = guard.check(signal)  # Duplicate
        assert result is not None
        assert "Duplicate" in result

    def test_concurrent_access(self):
        from src.bot_pipeline.signal_guard import SignalGuard

        guard = SignalGuard(dedup_window_seconds=300)
        results = []

        def check_signal(ticker):
            sig = _make_signal(ticker=ticker)
            results.append(guard.is_duplicate(sig))

        threads = [
            threading.Thread(target=check_signal, args=(f"T{i}",))
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All first-seen signals should not be duplicates
        assert all(r is False for r in results)

    def test_get_stats(self):
        from src.bot_pipeline.signal_guard import SignalGuard

        guard = SignalGuard(max_age_seconds=60, dedup_window_seconds=120)
        guard.is_duplicate(_make_signal(ticker="AAPL"))
        guard.is_duplicate(_make_signal(ticker="NVDA"))
        stats = guard.get_stats()
        assert stats["active_dedup_entries"] == 2
        assert stats["max_age_seconds"] == 60

    def test_clear(self):
        from src.bot_pipeline.signal_guard import SignalGuard

        guard = SignalGuard()
        signal = _make_signal()
        guard.is_duplicate(signal)
        guard.clear()
        # After clear, the same signal should not be considered duplicate
        assert guard.is_duplicate(signal) is False


# ═══════════════════════════════════════════════════════════════════════
# TestLifecycleManager
# ═══════════════════════════════════════════════════════════════════════


class TestLifecycleManager:
    """Tests for active position lifecycle management."""

    def _make_orchestrator(self):
        from src.bot_pipeline.orchestrator import BotOrchestrator, PipelineConfig

        self._tmpdir = tempfile.mkdtemp()
        config = PipelineConfig(
            enable_signal_recording=False,
            enable_unified_risk=False,
            enable_feedback_loop=False,
            enable_instrument_routing=False,
            enable_journaling=False,
            auto_kill_on_daily_loss=False,
            state_dir=self._tmpdir,
        )
        return BotOrchestrator(config=config)

    def test_update_prices(self):
        from src.bot_pipeline.lifecycle_manager import LifecycleManager

        orch = self._make_orchestrator()
        pos = _make_position(ticker="AAPL", current_price=150.0)
        orch.positions.append(pos)

        mgr = LifecycleManager(orch)
        updated = mgr.update_prices({"AAPL": 155.0})
        assert updated == 1
        assert orch.positions[0].current_price == 155.0

    def test_update_prices_partial(self):
        from src.bot_pipeline.lifecycle_manager import LifecycleManager

        orch = self._make_orchestrator()
        orch.positions.append(_make_position(ticker="AAPL"))
        orch.positions.append(_make_position(ticker="NVDA"))

        mgr = LifecycleManager(orch)
        updated = mgr.update_prices({"AAPL": 160.0})
        assert updated == 1  # Only AAPL updated

    def test_check_exits_detects_stop_loss(self):
        from src.bot_pipeline.lifecycle_manager import LifecycleManager

        orch = self._make_orchestrator()
        pos = _make_position(
            ticker="AAPL", direction="long",
            entry_price=150.0, stop_loss=145.0,
        )
        orch.positions.append(pos)

        mgr = LifecycleManager(orch)
        exits = mgr.check_exits({"AAPL": 140.0})  # Below stop
        assert len(exits) == 1
        assert exits[0].exit_type == "stop_loss"

    def test_check_exits_no_trigger(self):
        from src.bot_pipeline.lifecycle_manager import LifecycleManager

        orch = self._make_orchestrator()
        pos = _make_position(
            ticker="AAPL", direction="long",
            entry_price=150.0, stop_loss=145.0,
        )
        orch.positions.append(pos)

        mgr = LifecycleManager(orch)
        exits = mgr.check_exits({"AAPL": 152.0})  # Above stop, below 1R target
        assert len(exits) == 0

    def test_execute_exits(self):
        from src.bot_pipeline.lifecycle_manager import LifecycleManager
        from src.trade_executor.exit_monitor import ExitSignal

        orch = self._make_orchestrator()
        orch.positions.append(_make_position(ticker="AAPL"))

        mgr = LifecycleManager(orch)
        exit_sig = ExitSignal(
            ticker="AAPL", exit_type="stop_loss",
            priority=1, reason="Test stop loss",
        )
        closed = mgr.execute_exits([exit_sig], {"AAPL": 140.0})
        assert len(closed) == 1
        assert closed[0].ticker == "AAPL"
        assert len(orch.positions) == 0

    def test_emergency_close_all(self):
        from src.bot_pipeline.lifecycle_manager import LifecycleManager

        orch = self._make_orchestrator()
        orch.positions.append(_make_position(ticker="AAPL"))
        orch.positions.append(_make_position(ticker="NVDA"))

        mgr = LifecycleManager(orch)
        closed = mgr.emergency_close_all("Test shutdown")
        assert len(closed) == 2
        assert len(orch.positions) == 0
        assert orch._state.kill_switch_active is True

    def test_emergency_close_empty(self):
        from src.bot_pipeline.lifecycle_manager import LifecycleManager

        orch = self._make_orchestrator()
        mgr = LifecycleManager(orch)
        closed = mgr.emergency_close_all("No positions")
        assert len(closed) == 0
        # Kill switch should still activate
        assert orch._state.kill_switch_active is True

    def test_get_portfolio_snapshot(self):
        from src.bot_pipeline.lifecycle_manager import LifecycleManager

        orch = self._make_orchestrator()
        pos = _make_position(
            ticker="AAPL", entry_price=150.0, current_price=155.0, shares=100,
        )
        orch.positions.append(pos)

        mgr = LifecycleManager(orch)
        snap = mgr.get_portfolio_snapshot()
        assert snap.open_positions == 1
        assert snap.total_unrealized_pnl == 500.0  # (155-150)*100
        assert snap.total_exposure == 15500.0  # 155*100
        assert len(snap.positions) == 1

    def test_portfolio_snapshot_empty(self):
        from src.bot_pipeline.lifecycle_manager import LifecycleManager

        orch = self._make_orchestrator()
        mgr = LifecycleManager(orch)
        snap = mgr.get_portfolio_snapshot()
        assert snap.open_positions == 0
        assert snap.total_unrealized_pnl == 0.0
        assert snap.total_exposure == 0.0

    def test_portfolio_snapshot_to_dict(self):
        from src.bot_pipeline.lifecycle_manager import LifecycleManager

        orch = self._make_orchestrator()
        mgr = LifecycleManager(orch)
        snap = mgr.get_portfolio_snapshot()
        d = snap.to_dict()
        assert "timestamp" in d
        assert "open_positions" in d

    def test_check_exits_updates_prices_first(self):
        """Verify check_exits refreshes prices before checking exit conditions."""
        from src.bot_pipeline.lifecycle_manager import LifecycleManager

        orch = self._make_orchestrator()
        pos = _make_position(
            ticker="AAPL", direction="long",
            entry_price=150.0, current_price=150.0, stop_loss=145.0,
        )
        # Set target_price high so it doesn't trigger
        pos.target_price = 200.0
        orch.positions.append(pos)

        mgr = LifecycleManager(orch)
        # Price is between stop (145) and target (200), so no exit
        exits = mgr.check_exits({"AAPL": 152.0})
        assert len(exits) == 0
        # Price was updated
        assert orch.positions[0].current_price == 152.0

    def test_execute_exits_missing_price(self):
        """Execute exits without price_map should use current_price."""
        from src.bot_pipeline.lifecycle_manager import LifecycleManager
        from src.trade_executor.exit_monitor import ExitSignal

        orch = self._make_orchestrator()
        pos = _make_position(ticker="AAPL", current_price=155.0)
        orch.positions.append(pos)

        mgr = LifecycleManager(orch)
        exit_sig = ExitSignal(
            ticker="AAPL", exit_type="target",
            priority=4, reason="Test",
        )
        closed = mgr.execute_exits([exit_sig])  # No price_map
        assert len(closed) == 1

    def test_multiple_exits(self):
        from src.bot_pipeline.lifecycle_manager import LifecycleManager
        from src.trade_executor.exit_monitor import ExitSignal

        orch = self._make_orchestrator()
        orch.positions.append(_make_position(ticker="AAPL"))
        orch.positions.append(_make_position(ticker="NVDA"))

        mgr = LifecycleManager(orch)
        exits = [
            ExitSignal(ticker="AAPL", exit_type="stop_loss", priority=1, reason="Stop"),
            ExitSignal(ticker="NVDA", exit_type="target", priority=4, reason="Target"),
        ]
        closed = mgr.execute_exits(exits, {"AAPL": 140.0, "NVDA": 200.0})
        assert len(closed) == 2
        assert len(orch.positions) == 0


# ═══════════════════════════════════════════════════════════════════════
# TestOrchestratorLifecycle
# ═══════════════════════════════════════════════════════════════════════


class TestOrchestratorLifecycle:
    """Tests for PRD-171 orchestrator enhancements."""

    def _make_orchestrator(self, **overrides):
        from src.bot_pipeline.orchestrator import BotOrchestrator, PipelineConfig

        self._tmpdir = tempfile.mkdtemp()
        defaults = dict(
            enable_signal_recording=False,
            enable_unified_risk=False,
            enable_feedback_loop=False,
            enable_instrument_routing=False,
            enable_journaling=False,
            auto_kill_on_daily_loss=False,
            state_dir=self._tmpdir,
        )
        defaults.update(overrides)
        config = PipelineConfig(**defaults)
        return BotOrchestrator(config=config)

    def test_stale_signal_rejected(self):
        orch = self._make_orchestrator(max_signal_age_seconds=30)
        stale_signal = _make_signal(
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=60),
        )
        result = orch.process_signal(stale_signal, _make_account())
        assert result.success is False
        assert result.pipeline_stage == "signal_guard"
        assert "Stale" in result.rejection_reason

    def test_duplicate_signal_rejected(self):
        orch = self._make_orchestrator(dedup_window_seconds=300)
        signal = _make_signal()
        # First signal passes
        result1 = orch.process_signal(signal, _make_account())
        assert result1.success is True
        # Same signal rejected as duplicate
        signal2 = _make_signal()  # Same ticker/type/direction
        result2 = orch.process_signal(signal2, _make_account())
        assert result2.success is False
        assert result2.pipeline_stage == "signal_guard"
        assert "Duplicate" in result2.rejection_reason

    def test_fresh_unique_signal_passes_guard(self):
        orch = self._make_orchestrator()
        signal = _make_signal()
        result = orch.process_signal(signal, _make_account())
        assert result.success is True
        assert result.pipeline_stage == "completed"

    def test_journal_entry_recorded(self):
        journal = MagicMock()
        from src.bot_pipeline.orchestrator import BotOrchestrator, PipelineConfig

        config = PipelineConfig(
            enable_signal_recording=False,
            enable_unified_risk=False,
            enable_feedback_loop=False,
            enable_instrument_routing=False,
            enable_journaling=True,
            auto_kill_on_daily_loss=False,
            state_dir=tempfile.mkdtemp(),
        )
        orch = BotOrchestrator(config=config, journal=journal)
        signal = _make_signal()
        result = orch.process_signal(signal, _make_account())
        assert result.success is True
        journal.record_entry.assert_called_once()

    def test_journal_exit_recorded(self):
        journal = MagicMock()
        from src.bot_pipeline.orchestrator import BotOrchestrator, PipelineConfig

        config = PipelineConfig(
            enable_signal_recording=False,
            enable_unified_risk=False,
            enable_feedback_loop=False,
            enable_instrument_routing=False,
            enable_journaling=True,
            auto_kill_on_daily_loss=False,
            state_dir=tempfile.mkdtemp(),
        )
        orch = BotOrchestrator(config=config, journal=journal)
        signal = _make_signal()
        orch.process_signal(signal, _make_account())
        orch.close_position("AAPL", "test_exit", 155.0)
        journal.record_exit.assert_called_once()

    def test_instrument_routing_leveraged_etf(self):
        """When instrument routing is enabled, ETF signals should be routed."""
        from src.trade_executor.instrument_router import InstrumentDecision, InstrumentRouter

        mock_router = MagicMock(spec=InstrumentRouter)
        mock_router.route.return_value = InstrumentDecision(
            instrument_type="leveraged_etf",
            ticker="TQQQ",
            original_signal_ticker="AAPL",
            leverage=3.0,
            is_inverse=False,
            etf_metadata={"tracks": "NASDAQ-100", "leverage": 3.0},
        )

        from src.bot_pipeline.orchestrator import BotOrchestrator, PipelineConfig

        config = PipelineConfig(
            enable_signal_recording=False,
            enable_unified_risk=False,
            enable_feedback_loop=False,
            enable_instrument_routing=True,
            enable_journaling=False,
            auto_kill_on_daily_loss=False,
            state_dir=tempfile.mkdtemp(),
        )
        orch = BotOrchestrator(
            config=config,
            instrument_router=mock_router,
        )
        signal = _make_signal(ticker="AAPL")
        result = orch.process_signal(signal, _make_account())
        assert result.success is True
        # Position should be on the routed ticker
        assert result.position.ticker == "TQQQ"
        assert result.position.instrument_type == "leveraged_etf"
        assert result.position.leverage == 3.0

    def test_daily_loss_auto_kill(self):
        """Kill switch activates when daily P&L exceeds limit."""
        orch = self._make_orchestrator(auto_kill_on_daily_loss=True)
        account = _make_account()

        # Open and close position with a large loss
        signal = _make_signal(entry_price=150.0)
        result = orch.process_signal(signal, account)
        assert result.success is True

        # Simulate a massive loss that exceeds 10% of equity ($10,000)
        # Force-set daily_pnl to simulate accumulated losses
        orch._state._state["daily_pnl"] = -11_000.0
        orch._state._save()

        # The check happens on close_position
        orch.close_position("AAPL", "big_loss", exit_price=50.0)

        # Kill switch should now be active
        assert orch._state.kill_switch_active is True

    def test_daily_loss_auto_kill_disabled(self):
        orch = self._make_orchestrator(auto_kill_on_daily_loss=False)
        account = _make_account()

        signal = _make_signal(entry_price=150.0)
        orch.process_signal(signal, account)
        orch._state._state["daily_pnl"] = -20_000.0
        orch._state._save()
        orch.close_position("AAPL", "big_loss", exit_price=50.0)

        # Kill switch should NOT activate
        assert orch._state.kill_switch_active is False

    def test_execution_history_capped(self):
        """Execution history uses deque with maxlen, preventing unbounded growth."""
        orch = self._make_orchestrator(max_history_size=5)
        account = _make_account()

        for i in range(10):
            signal = _make_signal(ticker=f"T{i}", signal_type=SignalType.CLOUD_BOUNCE_LONG)
            orch.process_signal(signal, account)

        assert len(orch.execution_history) == 5  # Capped at 5
        assert isinstance(orch.execution_history, deque)

    def test_execution_history_is_deque(self):
        orch = self._make_orchestrator(max_history_size=100)
        assert isinstance(orch.execution_history, deque)
        assert orch.execution_history.maxlen == 100

    def test_state_records_signal_time(self):
        orch = self._make_orchestrator()
        assert orch._state.last_signal_time is None

        signal = _make_signal()
        orch.process_signal(signal, _make_account())

        assert orch._state.last_signal_time is not None

    def test_state_records_trade_time(self):
        orch = self._make_orchestrator()
        assert orch._state.last_trade_time is None

        signal = _make_signal()
        orch.process_signal(signal, _make_account())

        assert orch._state.last_trade_time is not None

    def test_pipeline_stats_include_guard(self):
        orch = self._make_orchestrator()
        stats = orch.get_pipeline_stats()
        assert "signal_guard" in stats
        assert "active_dedup_entries" in stats["signal_guard"]

    def test_pipeline_stats_include_history_size(self):
        orch = self._make_orchestrator(max_history_size=500)
        stats = orch.get_pipeline_stats()
        assert stats["history_max_size"] == 500

    def test_signal_guard_injected(self):
        """Custom signal guard can be injected."""
        from src.bot_pipeline.signal_guard import SignalGuard

        custom_guard = SignalGuard(max_age_seconds=10, dedup_window_seconds=10)
        from src.bot_pipeline.orchestrator import BotOrchestrator, PipelineConfig

        config = PipelineConfig(
            enable_signal_recording=False,
            enable_unified_risk=False,
            enable_feedback_loop=False,
            enable_instrument_routing=False,
            enable_journaling=False,
            state_dir=tempfile.mkdtemp(),
        )
        orch = BotOrchestrator(config=config, signal_guard=custom_guard)
        assert orch._signal_guard is custom_guard


# ═══════════════════════════════════════════════════════════════════════
# TestPaperModeFix
# ═══════════════════════════════════════════════════════════════════════


class TestPaperModeFix:
    """Tests for paper mode pricing fix (PRD-171)."""

    def test_market_order_uses_entry_price(self):
        """Market orders should use entry_price from metadata, not $100."""
        router = OrderRouter(paper_mode=True)
        order = Order(
            ticker="AAPL", side="buy", qty=10,
            order_type="market",
            metadata={"entry_price": 195.50},
        )
        result = router.submit_order(order)
        assert result.filled_price == 195.50
        assert result.status == "filled"

    def test_limit_order_uses_limit_price(self):
        router = OrderRouter(paper_mode=True)
        order = Order(
            ticker="AAPL", side="buy", qty=10,
            order_type="limit",
            limit_price=190.0,
        )
        result = router.submit_order(order)
        assert result.filled_price == 190.0

    def test_stop_order_uses_stop_price(self):
        router = OrderRouter(paper_mode=True)
        order = Order(
            ticker="AAPL", side="sell", qty=10,
            order_type="stop",
            stop_price=185.0,
        )
        result = router.submit_order(order)
        assert result.filled_price == 185.0

    def test_market_order_no_metadata_fallback(self):
        """Without metadata, should fall back to $100."""
        router = OrderRouter(paper_mode=True)
        order = Order(
            ticker="AAPL", side="buy", qty=10,
            order_type="market",
        )
        result = router.submit_order(order)
        assert result.filled_price == 100.0  # Last resort fallback

    def test_market_order_empty_metadata(self):
        """Empty metadata should fall back to $100."""
        router = OrderRouter(paper_mode=True)
        order = Order(
            ticker="AAPL", side="buy", qty=10,
            order_type="market",
            metadata={},
        )
        result = router.submit_order(order)
        assert result.filled_price == 100.0

    def test_market_order_zero_entry_price(self):
        """Zero entry_price in metadata should fall back to $100."""
        router = OrderRouter(paper_mode=True)
        order = Order(
            ticker="AAPL", side="buy", qty=10,
            order_type="market",
            metadata={"entry_price": 0.0},
        )
        result = router.submit_order(order)
        assert result.filled_price == 100.0

    def test_limit_price_takes_precedence(self):
        """limit_price should take precedence over metadata entry_price."""
        router = OrderRouter(paper_mode=True)
        order = Order(
            ticker="AAPL", side="buy", qty=10,
            order_type="limit",
            limit_price=200.0,
            metadata={"entry_price": 195.0},
        )
        result = router.submit_order(order)
        assert result.filled_price == 200.0  # limit_price wins

    def test_orchestrator_passes_entry_price_metadata(self):
        """BotOrchestrator should pass entry_price in order metadata."""
        from src.bot_pipeline.orchestrator import BotOrchestrator, PipelineConfig

        config = PipelineConfig(
            enable_signal_recording=False,
            enable_unified_risk=False,
            enable_feedback_loop=False,
            enable_instrument_routing=False,
            enable_journaling=False,
            auto_kill_on_daily_loss=False,
            state_dir=tempfile.mkdtemp(),
        )
        # Use a spy to capture the order
        captured_orders = []
        original_submit = OrderRouter.submit_order

        def spy_submit(self_router, order):
            captured_orders.append(order)
            return original_submit(self_router, order)

        with patch.object(OrderRouter, "submit_order", spy_submit):
            orch = BotOrchestrator(config=config)
            signal = _make_signal(entry_price=250.0)
            result = orch.process_signal(signal, _make_account())

        assert len(captured_orders) == 1
        assert captured_orders[0].metadata.get("entry_price") == 250.0


# ═══════════════════════════════════════════════════════════════════════
# TestStateManagerLifecycle
# ═══════════════════════════════════════════════════════════════════════


class TestStateManagerLifecycle:
    """Tests for PRD-171 state manager additions."""

    def test_total_realized_pnl_tracked(self):
        import tempfile

        from src.bot_pipeline.state_manager import PersistentStateManager

        with tempfile.TemporaryDirectory() as td:
            mgr = PersistentStateManager(td)
            mgr.record_trade_pnl(100.0)
            mgr.record_trade_pnl(-30.0)
            assert mgr.total_realized_pnl == 70.0

    def test_total_realized_pnl_survives_daily_reset(self):
        import tempfile

        from src.bot_pipeline.state_manager import PersistentStateManager

        with tempfile.TemporaryDirectory() as td:
            mgr = PersistentStateManager(td)
            mgr.record_trade_pnl(500.0)
            mgr.reset_daily()
            assert mgr.daily_pnl == 0.0
            assert mgr.total_realized_pnl == 500.0

    def test_signal_time_recorded(self):
        import tempfile

        from src.bot_pipeline.state_manager import PersistentStateManager

        with tempfile.TemporaryDirectory() as td:
            mgr = PersistentStateManager(td)
            assert mgr.last_signal_time is None
            mgr.record_signal_time()
            assert mgr.last_signal_time is not None

    def test_trade_time_recorded(self):
        import tempfile

        from src.bot_pipeline.state_manager import PersistentStateManager

        with tempfile.TemporaryDirectory() as td:
            mgr = PersistentStateManager(td)
            assert mgr.last_trade_time is None
            mgr.record_trade_time()
            assert mgr.last_trade_time is not None

    def test_default_state_includes_new_fields(self):
        import tempfile

        from src.bot_pipeline.state_manager import PersistentStateManager

        with tempfile.TemporaryDirectory() as td:
            mgr = PersistentStateManager(td)
            snap = mgr.get_snapshot()
            assert "total_realized_pnl" in snap
            assert "last_signal_time" in snap
            assert "last_trade_time" in snap
