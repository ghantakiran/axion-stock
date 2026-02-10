"""Tests for Paper Trading System."""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timezone

from src.paper_trading.config import (
    SessionStatus,
    DataFeedType,
    RebalanceSchedule,
    StrategyType,
    PerformancePeriod,
    DataFeedConfig,
    StrategyConfig,
    SessionConfig,
    DEFAULT_SESSION_CONFIG,
)
from src.paper_trading.models import (
    SessionTrade,
    PortfolioPosition,
    SessionSnapshot,
    SessionMetrics,
    PaperSession,
    SessionComparison,
)
from src.paper_trading.data_feed import DataFeed
from src.paper_trading.performance import PerformanceTracker
from src.paper_trading.session import SessionManager


# =============================================================================
# Config Tests
# =============================================================================


class TestPaperTradingConfig:
    """Test configuration enums and defaults."""

    def test_session_statuses(self):
        assert len(SessionStatus) == 5

    def test_data_feed_types(self):
        assert len(DataFeedType) == 3

    def test_rebalance_schedules(self):
        assert len(RebalanceSchedule) == 4

    def test_strategy_types(self):
        assert len(StrategyType) == 6

    def test_default_session_config(self):
        config = DEFAULT_SESSION_CONFIG
        assert config.initial_capital == 100_000
        assert len(config.symbols) == 5
        assert config.benchmark == "SPY"
        assert config.slippage_bps == 2.0

    def test_data_feed_config_defaults(self):
        config = DataFeedConfig()
        assert config.feed_type == DataFeedType.SIMULATED
        assert config.volatility == 0.015
        assert config.drift == 0.0004

    def test_strategy_config_defaults(self):
        config = StrategyConfig()
        assert config.strategy_type == StrategyType.MANUAL
        assert config.max_positions == 20
        assert config.stop_loss_pct == -0.15


# =============================================================================
# Model Tests
# =============================================================================


class TestPaperTradingModels:
    """Test data models."""

    def test_portfolio_position_properties(self):
        pos = PortfolioPosition(
            symbol="AAPL", qty=100, avg_cost=150.0, current_price=160.0
        )
        assert pos.market_value == 16_000
        assert pos.cost_basis == 15_000
        assert pos.unrealized_pnl == 1_000
        assert abs(pos.unrealized_pnl_pct - 0.0667) < 0.001

    def test_session_trade_total_cost(self):
        trade = SessionTrade(commission=1.50, slippage=0.50)
        assert trade.total_cost == 2.0

    def test_paper_session_lifecycle(self):
        session = PaperSession(initial_capital=50_000)

        assert session.status == SessionStatus.CREATED
        assert not session.is_active

        session.start()
        assert session.status == SessionStatus.RUNNING
        assert session.is_active
        assert session.cash == 50_000

        session.pause()
        assert session.status == SessionStatus.PAUSED
        assert session.is_active

        session.resume()
        assert session.status == SessionStatus.RUNNING

        session.complete()
        assert session.status == SessionStatus.COMPLETED
        assert not session.is_active
        assert session.completed_at is not None

    def test_paper_session_equity(self):
        session = PaperSession(initial_capital=100_000)
        session.start()

        session.positions["AAPL"] = PortfolioPosition(
            symbol="AAPL", qty=100, avg_cost=150.0, current_price=160.0
        )

        assert session.positions_value == 16_000
        assert session.equity == 100_000 + 16_000  # cash + positions

    def test_paper_session_drawdown(self):
        session = PaperSession(initial_capital=100_000)
        session.start()
        session.peak_equity = 120_000

        # Cash dropped to 90k, no positions
        session.cash = 90_000
        assert abs(session.drawdown - (-0.25)) < 0.001  # (90k-120k)/120k

    def test_paper_session_cancel(self):
        session = PaperSession()
        session.start()
        session.cancel()
        assert session.status == SessionStatus.CANCELLED

    def test_session_metrics_to_dict(self):
        metrics = SessionMetrics(total_return=0.15, sharpe_ratio=1.2)
        d = metrics.to_dict()
        assert d["total_return"] == 0.15
        assert d["sharpe_ratio"] == 1.2


# =============================================================================
# Data Feed Tests
# =============================================================================


class TestDataFeed:
    """Test market data feed."""

    def test_initialize(self):
        feed = DataFeed()
        feed.initialize(["AAPL", "MSFT"], {"AAPL": 150.0, "MSFT": 300.0})

        assert feed.get_price("AAPL") == 150.0
        assert feed.get_price("MSFT") == 300.0

    def test_simulated_next_tick(self):
        config = DataFeedConfig(feed_type=DataFeedType.SIMULATED, seed=42)
        feed = DataFeed(config)
        feed.initialize(["AAPL"], {"AAPL": 100.0})

        prices = feed.next_tick()
        assert "AAPL" in prices
        assert prices["AAPL"] != 100.0  # Should have moved
        assert prices["AAPL"] > 0
        assert feed.bar_count == 1

    def test_random_walk_no_drift(self):
        config = DataFeedConfig(feed_type=DataFeedType.RANDOM_WALK, seed=42)
        feed = DataFeed(config)
        feed.initialize(["AAPL"], {"AAPL": 100.0})

        # Run many ticks - with no drift, should stay around 100
        prices_sum = 0
        n = 1000
        for _ in range(n):
            prices = feed.next_tick()
            prices_sum += prices["AAPL"]

        avg = prices_sum / n
        # Should be roughly around 100 (within reasonable bounds)
        assert 50 < avg < 200

    def test_historical_replay(self):
        config = DataFeedConfig(feed_type=DataFeedType.HISTORICAL_REPLAY)
        feed = DataFeed(config)

        # Create replay data
        dates = pd.date_range("2024-01-01", periods=5, freq="B")
        data = pd.DataFrame(
            {"AAPL": [150, 152, 148, 155, 153]},
            index=dates,
        )
        feed.load_replay_data(data)

        assert feed.has_more_data

        prices = feed.next_tick()
        assert prices["AAPL"] == 152  # Second row (first was loaded on init)

        prices = feed.next_tick()
        assert prices["AAPL"] == 148

    def test_replay_exhaustion(self):
        config = DataFeedConfig(feed_type=DataFeedType.HISTORICAL_REPLAY)
        feed = DataFeed(config)

        dates = pd.date_range("2024-01-01", periods=3, freq="B")
        data = pd.DataFrame({"AAPL": [100, 101, 102]}, index=dates)
        feed.load_replay_data(data)

        feed.next_tick()
        feed.next_tick()
        assert not feed.has_more_data

    def test_price_history(self):
        feed = DataFeed()
        feed.initialize(["AAPL"], {"AAPL": 100.0})
        feed.next_tick()
        feed.next_tick()

        history = feed.get_price_history("AAPL")
        assert len(history) == 3  # Initial + 2 ticks

    def test_reset(self):
        feed = DataFeed()
        feed.initialize(["AAPL"], {"AAPL": 100.0})
        feed.next_tick()
        feed.reset()

        assert feed.bar_count == 0
        assert feed.get_price("AAPL") == 0.0


# =============================================================================
# Performance Tracker Tests
# =============================================================================


class TestPaperTradingPerformanceTracker:
    """Test performance computation."""

    def _make_session_with_snapshots(self, n=50, mean_return=0.001):
        """Helper to create session with synthetic snapshots."""
        session = PaperSession(initial_capital=100_000)
        session.start()

        rng = np.random.RandomState(42)
        equity = 100_000.0
        peak = equity
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)

        for i in range(n):
            ret = rng.normal(mean_return, 0.01)
            equity *= (1 + ret)
            peak = max(peak, equity)
            dd = (equity - peak) / peak

            session.snapshots.append(SessionSnapshot(
                session_id=session.session_id,
                timestamp=now,
                equity=equity,
                cash=equity * 0.2,
                positions_value=equity * 0.8,
                n_positions=5,
                drawdown=dd,
                peak_equity=peak,
                daily_return=ret,
            ))

            from datetime import timedelta
            now += timedelta(days=1)

        session.cash = equity * 0.2
        session.positions["AAPL"] = PortfolioPosition(
            symbol="AAPL", qty=100, avg_cost=150.0,
            current_price=equity * 0.8 / 100,
        )
        session.peak_equity = peak

        return session

    def test_compute_basic_metrics(self):
        session = self._make_session_with_snapshots(n=100, mean_return=0.001)
        tracker = PerformanceTracker()
        metrics = tracker.compute(session)

        assert metrics.total_return != 0
        assert metrics.volatility > 0
        assert metrics.sharpe_ratio != 0
        assert metrics.total_days > 0
        assert metrics.start_equity == 100_000

    def test_compute_with_trades(self):
        session = self._make_session_with_snapshots(n=50)

        # Add some closing trades
        session.trades = [
            SessionTrade(pnl=500, pnl_pct=0.05, commission=1.0, slippage=0.5, notional=10000),
            SessionTrade(pnl=-200, pnl_pct=-0.02, commission=1.0, slippage=0.5, notional=10000),
            SessionTrade(pnl=300, pnl_pct=0.03, commission=1.0, slippage=0.5, notional=10000),
            SessionTrade(pnl=-100, pnl_pct=-0.01, commission=1.0, slippage=0.5, notional=10000),
            SessionTrade(pnl=400, pnl_pct=0.04, commission=1.0, slippage=0.5, notional=10000),
        ]

        tracker = PerformanceTracker()
        metrics = tracker.compute(session)

        assert metrics.total_trades == 5
        assert metrics.winning_trades == 3
        assert metrics.losing_trades == 2
        assert metrics.win_rate == 0.6
        assert metrics.total_commission == 5.0
        assert metrics.total_slippage == 2.5

    def test_compute_drawdown_duration(self):
        session = PaperSession(initial_capital=100_000)
        session.start()

        now = datetime(2024, 1, 1, tzinfo=timezone.utc)
        from datetime import timedelta

        # Create drawdown period
        drawdowns = [0, 0, -0.01, -0.02, -0.03, -0.02, 0, 0, -0.01, 0]
        for dd in drawdowns:
            session.snapshots.append(SessionSnapshot(
                drawdown=dd, equity=100_000 * (1 + dd),
                timestamp=now, peak_equity=100_000,
            ))
            now += timedelta(days=1)

        tracker = PerformanceTracker()
        metrics = tracker.compute(session)
        assert metrics.max_drawdown_duration_days == 4  # Longest streak

    def test_compare_sessions(self):
        tracker = PerformanceTracker()

        s1 = self._make_session_with_snapshots(n=50, mean_return=0.001)
        s1.name = "Conservative"

        s2 = self._make_session_with_snapshots(n=50, mean_return=0.002)
        s2.name = "Aggressive"

        comparison = tracker.compare_sessions({
            "Conservative": s1,
            "Aggressive": s2,
        })

        assert len(comparison.sessions) == 2
        assert len(comparison.metrics_table) == 2
        assert len(comparison.ranking) == 2
        assert "total_return" in comparison.winner_by_metric


# =============================================================================
# Session Manager Tests
# =============================================================================


class TestSessionManager:
    """Test session management."""

    def test_create_session(self):
        manager = SessionManager()
        session = manager.create_session("Test Session")

        assert session.name == "Test Session"
        assert session.status == SessionStatus.CREATED
        assert session.initial_capital == 100_000

    def test_session_lifecycle(self):
        manager = SessionManager()
        session = manager.create_session("Test")
        sid = session.session_id

        assert manager.start_session(sid)
        assert session.status == SessionStatus.RUNNING

        assert manager.pause_session(sid)
        assert session.status == SessionStatus.PAUSED

        assert manager.resume_session(sid)
        assert session.status == SessionStatus.RUNNING

        assert manager.stop_session(sid)
        assert session.status == SessionStatus.COMPLETED

    def test_execute_buy(self):
        manager = SessionManager()
        session = manager.create_session("Test")
        manager.start_session(session.session_id)

        trade = manager.execute_buy(session.session_id, "AAPL", 10)

        assert trade is not None
        assert trade.side == "buy"
        assert trade.qty == 10
        assert "AAPL" in session.positions
        assert session.positions["AAPL"].qty == 10
        assert session.cash < 100_000

    def test_execute_sell(self):
        manager = SessionManager()
        session = manager.create_session("Test")
        manager.start_session(session.session_id)

        # Buy first
        manager.execute_buy(session.session_id, "AAPL", 10)
        cash_after_buy = session.cash

        # Sell
        trade = manager.execute_sell(session.session_id, "AAPL", 10)

        assert trade is not None
        assert trade.side == "sell"
        assert trade.pnl is not None
        assert "AAPL" not in session.positions
        assert session.cash > cash_after_buy

    def test_sell_insufficient_shares(self):
        manager = SessionManager()
        session = manager.create_session("Test")
        manager.start_session(session.session_id)

        # Try to sell without position
        trade = manager.execute_sell(session.session_id, "AAPL", 10)
        assert trade is None

    def test_buy_insufficient_cash(self):
        manager = SessionManager()
        config = SessionConfig(initial_capital=100)
        session = manager.create_session("Test", config)
        manager.start_session(session.session_id)

        # Try to buy more than we can afford
        trade = manager.execute_buy(session.session_id, "AAPL", 10000)
        assert trade is None

    def test_advance_feed(self):
        manager = SessionManager()
        session = manager.create_session("Test")
        manager.start_session(session.session_id)
        manager.execute_buy(session.session_id, "AAPL", 10)

        initial_price = session.positions["AAPL"].current_price

        prices = manager.advance_feed(session.session_id)
        assert "AAPL" in prices
        # Price should have changed
        assert session.positions["AAPL"].current_price == prices["AAPL"]

    def test_record_snapshot(self):
        manager = SessionManager()
        session = manager.create_session("Test")
        manager.start_session(session.session_id)

        snap = manager.record_snapshot(session.session_id)
        assert snap is not None
        assert snap.equity == 100_000
        assert len(session.snapshots) == 1

    def test_equal_weight_rebalance(self):
        manager = SessionManager()
        config = SessionConfig(
            symbols=["AAPL", "MSFT", "GOOGL"],
            initial_capital=100_000,
        )
        session = manager.create_session("Rebalance Test", config)
        manager.start_session(session.session_id)

        trades = manager.run_equal_weight_rebalance(session.session_id)

        assert len(trades) > 0
        assert len(session.positions) > 0

    def test_list_sessions(self):
        manager = SessionManager()
        s1 = manager.create_session("Session 1")
        s2 = manager.create_session("Session 2")
        manager.start_session(s1.session_id)

        all_sessions = manager.list_sessions()
        assert len(all_sessions) == 2

        running = manager.list_sessions(SessionStatus.RUNNING)
        assert len(running) == 1

    def test_delete_session(self):
        manager = SessionManager()
        session = manager.create_session("To Delete")
        sid = session.session_id

        assert manager.delete_session(sid)
        assert manager.get_session(sid) is None

    def test_get_metrics(self):
        manager = SessionManager()
        session = manager.create_session("Test")
        manager.start_session(session.session_id)

        # Simulate some activity
        manager.execute_buy(session.session_id, "AAPL", 10)
        for _ in range(5):
            manager.advance_feed(session.session_id)
            manager.record_snapshot(session.session_id)

        metrics = manager.get_metrics(session.session_id)
        assert metrics is not None
        assert "total_return" in metrics


# =============================================================================
# Integration Tests
# =============================================================================


class TestPaperTradingFullWorkflow:
    """Integration tests."""

    def test_complete_paper_trading_workflow(self):
        """End-to-end: create session, trade, rebalance, compute metrics."""
        manager = SessionManager()

        # 1. Create and start session
        config = SessionConfig(
            initial_capital=100_000,
            symbols=["AAPL", "MSFT", "GOOGL"],
        )
        session = manager.create_session("E2E Test", config)
        manager.start_session(session.session_id)

        # 2. Initial rebalance
        trades = manager.run_equal_weight_rebalance(session.session_id)
        assert len(trades) > 0
        manager.record_snapshot(session.session_id)

        # 3. Simulate 20 days of market movement
        for _ in range(20):
            manager.advance_feed(session.session_id)
            manager.record_snapshot(session.session_id)

        # 4. Rebalance again
        trades2 = manager.run_equal_weight_rebalance(session.session_id)
        manager.record_snapshot(session.session_id)

        # 5. Stop and compute metrics
        manager.stop_session(session.session_id)

        assert session.status == SessionStatus.COMPLETED
        assert session.metrics.total_return != 0
        assert len(session.snapshots) > 20
        assert len(session.trades) > 0


class TestPaperTradingModuleImports:
    """Test module exports."""

    def test_top_level_imports(self):
        from src.paper_trading import (
            SessionStatus,
            DataFeedType,
            RebalanceSchedule,
            StrategyType,
            SessionConfig,
            PaperSession,
            SessionTrade,
            SessionMetrics,
            DataFeed,
            PerformanceTracker,
            SessionManager,
        )

        assert SessionStatus.RUNNING.value == "running"
        assert DataFeedType.SIMULATED.value == "simulated"
