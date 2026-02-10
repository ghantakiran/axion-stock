"""Tests for PRD-137: Trading Bot Dashboard & Control Center.

Tests bot state management, lifecycle control, performance metrics,
and chart rendering.
"""

import os
import sys
import unittest
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from src.bot_dashboard.state import (
    BotController,
    BotEvent,
    BotState,
    DashboardConfig,
)
from src.bot_dashboard.metrics import DailyMetrics, PerformanceMetrics
from src.bot_dashboard.charts import CloudChartRenderer


# ═══════════════════════════════════════════════════════════════════════
# 1. BotState
# ═══════════════════════════════════════════════════════════════════════


class TestBotState(unittest.TestCase):
    """Test bot state dataclass."""

    def test_default_state(self):
        state = BotState()
        self.assertEqual(state.status, "paper")
        self.assertFalse(state.kill_switch_active)
        self.assertEqual(state.data_feed_status, "disconnected")

    def test_is_active(self):
        state = BotState(status="live")
        self.assertTrue(state.is_active)
        state.status = "killed"
        self.assertFalse(state.is_active)

    def test_net_pnl(self):
        state = BotState(realized_pnl=500.0, unrealized_pnl=200.0)
        self.assertAlmostEqual(state.net_pnl, 700.0)

    def test_to_dict(self):
        state = BotState(account_equity=100_000.0, daily_pnl=500.0)
        d = state.to_dict()
        self.assertEqual(d["account_equity"], 100_000.0)
        self.assertIn("status", d)

    def test_bot_event_to_dict(self):
        event = BotEvent(event_type="trade", severity="info", message="Executed AAPL")
        d = event.to_dict()
        self.assertEqual(d["event_type"], "trade")
        self.assertEqual(d["severity"], "info")


# ═══════════════════════════════════════════════════════════════════════
# 2. BotController
# ═══════════════════════════════════════════════════════════════════════


class TestBotController(unittest.TestCase):
    """Test bot lifecycle control."""

    def test_initial_state_paper(self):
        ctrl = BotController()
        self.assertEqual(ctrl.state.status, "paper")

    def test_start_paper(self):
        ctrl = BotController()
        ctrl.start(paper_mode=True)
        self.assertEqual(ctrl.state.status, "paper")
        self.assertEqual(ctrl.state.active_broker, "paper")

    def test_start_live(self):
        ctrl = BotController(config=DashboardConfig(paper_mode=False))
        ctrl.start(paper_mode=False)
        self.assertEqual(ctrl.state.status, "live")
        self.assertEqual(ctrl.state.active_broker, "alpaca")

    def test_pause_resume(self):
        ctrl = BotController()
        ctrl.start(paper_mode=True)
        ctrl.pause()
        self.assertEqual(ctrl.state.status, "paused")
        ctrl.resume()
        self.assertEqual(ctrl.state.status, "paper")

    def test_kill(self):
        ctrl = BotController()
        ctrl.start()
        ctrl.kill("Test halt")
        self.assertEqual(ctrl.state.status, "killed")
        self.assertTrue(ctrl.state.kill_switch_active)

    def test_reset_kill_switch(self):
        ctrl = BotController()
        ctrl.kill("test")
        ctrl.reset_kill_switch()
        self.assertFalse(ctrl.state.kill_switch_active)
        self.assertEqual(ctrl.state.status, "paused")

    def test_update_config(self):
        ctrl = BotController()
        ctrl.update_config({"refresh_interval_seconds": 10})
        self.assertEqual(ctrl.config.refresh_interval_seconds, 10)

    def test_update_state(self):
        ctrl = BotController()
        ctrl.update_state(account_equity=150_000.0, daily_pnl=1500.0)
        self.assertEqual(ctrl.state.account_equity, 150_000.0)
        self.assertEqual(ctrl.state.daily_pnl, 1500.0)

    def test_events_recorded(self):
        ctrl = BotController()
        ctrl.start()
        ctrl.pause()
        ctrl.resume()
        events = ctrl.get_events()
        self.assertGreaterEqual(len(events), 3)

    def test_events_filter_by_severity(self):
        ctrl = BotController()
        ctrl.start()
        ctrl.kill("test")
        critical = ctrl.get_events(severity="critical")
        self.assertGreaterEqual(len(critical), 1)

    def test_uptime_tracking(self):
        ctrl = BotController()
        state = ctrl.state
        self.assertGreaterEqual(state.uptime_seconds, 0)

    def test_session_id_assigned(self):
        ctrl = BotController()
        self.assertTrue(len(ctrl.state.session_id) > 0)


# ═══════════════════════════════════════════════════════════════════════
# 3. PerformanceMetrics
# ═══════════════════════════════════════════════════════════════════════


class TestBotDashboardPerformanceMetrics(unittest.TestCase):
    """Test performance metric calculations."""

    def setUp(self):
        self.metrics = PerformanceMetrics()
        self.sample_trades = [
            {"ticker": "AAPL", "pnl": 200.0, "conviction": 80},
            {"ticker": "AAPL", "pnl": -100.0, "conviction": 60},
            {"ticker": "MSFT", "pnl": 300.0, "conviction": 90},
            {"ticker": "MSFT", "pnl": -50.0, "conviction": 45},
            {"ticker": "NVDA", "pnl": 150.0, "conviction": 75},
        ]

    def test_daily_metrics_empty(self):
        m = self.metrics.daily_metrics([])
        self.assertEqual(m.total_trades, 0)
        self.assertEqual(m.win_rate, 0.0)

    def test_daily_metrics_with_trades(self):
        m = self.metrics.daily_metrics(self.sample_trades)
        self.assertEqual(m.total_trades, 5)
        self.assertEqual(m.winners, 3)
        self.assertEqual(m.losers, 2)
        self.assertAlmostEqual(m.win_rate, 0.6)
        self.assertAlmostEqual(m.gross_profit, 650.0)
        self.assertAlmostEqual(m.net_pnl, 500.0)

    def test_win_rate_by_ticker(self):
        rates = self.metrics.win_rate_by_ticker(self.sample_trades)
        self.assertAlmostEqual(rates["AAPL"], 0.5)
        self.assertAlmostEqual(rates["NVDA"], 1.0)

    def test_win_rate_by_conviction(self):
        rates = self.metrics.win_rate_by_conviction(self.sample_trades)
        self.assertIn("high", rates)
        self.assertIn("medium", rates)
        self.assertIn("low", rates)

    def test_profit_factor(self):
        pf = self.metrics.profit_factor(self.sample_trades)
        self.assertGreater(pf, 1.0)

    def test_profit_factor_no_losses(self):
        winners = [{"pnl": 100.0}, {"pnl": 200.0}]
        pf = self.metrics.profit_factor(winners)
        self.assertEqual(pf, float("inf"))

    def test_expectancy(self):
        exp = self.metrics.expectancy(self.sample_trades)
        self.assertGreater(exp, 0)  # Net positive trades

    def test_expectancy_empty(self):
        exp = self.metrics.expectancy([])
        self.assertEqual(exp, 0.0)

    def test_sharpe_ratio(self):
        returns = [0.01, -0.005, 0.02, 0.005, -0.01, 0.015]
        sr = self.metrics.sharpe_ratio(returns)
        self.assertGreater(sr, 0)

    def test_sharpe_ratio_insufficient_data(self):
        sr = self.metrics.sharpe_ratio([0.01])
        self.assertEqual(sr, 0.0)

    def test_max_drawdown(self):
        equity = [100, 105, 102, 108, 95, 110]
        dd = self.metrics.max_drawdown(equity)
        # Peak 108, trough 95 → dd = 13/108 ≈ 0.1204
        self.assertAlmostEqual(dd, 13 / 108, places=3)

    def test_max_drawdown_empty(self):
        dd = self.metrics.max_drawdown([])
        self.assertEqual(dd, 0.0)

    def test_daily_metrics_to_dict(self):
        m = self.metrics.daily_metrics(self.sample_trades)
        d = m.to_dict()
        self.assertIn("win_rate", d)
        self.assertIn("profit_factor", d)


# ═══════════════════════════════════════════════════════════════════════
# 4. CloudChartRenderer
# ═══════════════════════════════════════════════════════════════════════


class TestCloudChartRenderer(unittest.TestCase):
    """Test chart rendering."""

    def setUp(self):
        self.renderer = CloudChartRenderer()

    def test_render_cloud_chart(self):
        df = pd.DataFrame({
            "open": [100, 101, 102],
            "high": [101, 102, 103],
            "low": [99, 100, 101],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000, 1100, 1200],
            "ema_5": [100, 100.5, 101],
        })
        chart = self.renderer.render_cloud_chart(df, "AAPL", "10m")
        self.assertEqual(chart["type"], "cloud_chart")
        self.assertEqual(chart["ticker"], "AAPL")
        self.assertEqual(chart["bars"], 3)
        self.assertTrue(chart["has_ema_data"])

    def test_render_cloud_chart_no_data(self):
        chart = self.renderer.render_cloud_chart(None, "AAPL")
        self.assertEqual(chart["bars"], 0)

    def test_render_equity_curve(self):
        daily_pnl = [100, -50, 200, 150, -30]
        chart = self.renderer.render_equity_curve(daily_pnl)
        self.assertEqual(chart["type"], "equity_curve")
        self.assertEqual(chart["data_points"], 5)
        self.assertEqual(chart["final_pnl"], 370.0)

    def test_render_equity_curve_empty(self):
        chart = self.renderer.render_equity_curve([])
        self.assertEqual(chart["data_points"], 0)

    def test_render_pnl_heatmap(self):
        trades = [
            {"ticker": "AAPL", "pnl": 100},
            {"ticker": "MSFT", "pnl": -50},
        ]
        chart = self.renderer.render_pnl_heatmap(trades)
        self.assertEqual(chart["trade_count"], 2)
        self.assertIn("AAPL", chart["tickers"])

    def test_render_exposure_gauge(self):
        chart = self.renderer.render_exposure_gauge(0.45)
        self.assertEqual(chart["level"], "medium")

    def test_render_signal_timeline(self):
        signals = [{"signal": "test"}] * 5
        chart = self.renderer.render_signal_timeline(signals)
        self.assertEqual(chart["signal_count"], 5)


# ═══════════════════════════════════════════════════════════════════════
# 5. Module Imports
# ═══════════════════════════════════════════════════════════════════════


class TestBotDashboardModuleImports(unittest.TestCase):
    """Test that all public symbols are importable."""

    def test_import_all(self):
        from src.bot_dashboard import (
            BotController, BotEvent, BotState, DashboardConfig,
            PerformanceMetrics, DailyMetrics, CloudChartRenderer,
        )
        self.assertTrue(callable(BotController))
        self.assertTrue(callable(PerformanceMetrics))
        self.assertTrue(callable(CloudChartRenderer))

    def test_dashboard_config_defaults(self):
        config = DashboardConfig()
        self.assertEqual(config.refresh_interval_seconds, 5)
        self.assertTrue(config.paper_mode)


if __name__ == "__main__":
    unittest.main()
