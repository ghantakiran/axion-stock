"""PRD-174: Bot Alerting & Notifications — tests.

Tests BotAlertBridge event handlers and dedup logic.
~35 tests across 3 classes.
"""

from __future__ import annotations

import time
import pytest

from src.bot_pipeline.alert_bridge import AlertBridgeConfig, BotAlertBridge
from src.alerting.config import AlertSeverity
from src.alerting.manager import AlertManager


# ═════════════════════════════════════════════════════════════════════
# Test BotAlertBridge Core Events
# ═════════════════════════════════════════════════════════════════════


class TestBotAlertBridgeEvents:
    """Test alert emission for each pipeline event type."""

    def _make_bridge(self) -> BotAlertBridge:
        return BotAlertBridge(alert_manager=AlertManager())

    def test_on_trade_executed(self):
        bridge = self._make_bridge()
        alert = bridge.on_trade_executed("AAPL", "long", 100, 150.0)
        assert "AAPL" in alert.title
        assert alert.severity == AlertSeverity.INFO

    def test_on_trade_executed_short(self):
        bridge = self._make_bridge()
        alert = bridge.on_trade_executed("TSLA", "short", 50, 200.0)
        assert "SHORT" in alert.title
        assert "TSLA" in alert.message

    def test_on_position_closed_profit(self):
        bridge = self._make_bridge()
        alert = bridge.on_position_closed("AAPL", "long", 150.0, "target_hit")
        assert alert.severity == AlertSeverity.INFO
        assert "+150.00" in alert.message

    def test_on_position_closed_loss(self):
        bridge = self._make_bridge()
        alert = bridge.on_position_closed("NVDA", "long", -200.0, "stop_loss")
        assert alert.severity == AlertSeverity.WARNING
        assert "-200.00" in alert.message

    def test_on_kill_switch(self):
        bridge = self._make_bridge()
        alert = bridge.on_kill_switch("Daily loss limit hit")
        assert alert.severity == AlertSeverity.CRITICAL
        assert "KILL SWITCH" in alert.title

    def test_on_daily_loss_warning(self):
        bridge = self._make_bridge()
        alert = bridge.on_daily_loss_warning(-800.0, 1000.0)
        assert alert.severity == AlertSeverity.WARNING
        assert "80%" in alert.title

    def test_on_emergency_close(self):
        bridge = self._make_bridge()
        alert = bridge.on_emergency_close(5)
        assert alert.severity == AlertSeverity.CRITICAL
        assert "5" in alert.message

    def test_on_error(self):
        bridge = self._make_bridge()
        alert = bridge.on_error("risk_assessment", "Timeout")
        assert alert.severity == AlertSeverity.ERROR
        assert "risk_assessment" in alert.title

    def test_alert_history_recorded(self):
        bridge = self._make_bridge()
        bridge.on_trade_executed("AAPL", "long", 100, 150.0)
        bridge.on_kill_switch("test")
        history = bridge.get_alert_history()
        assert len(history) == 2

    def test_alert_has_dedup_key(self):
        bridge = self._make_bridge()
        alert = bridge.on_kill_switch("test")
        assert alert.dedup_key == "kill_switch"

    def test_on_trade_executed_dedup_key(self):
        bridge = self._make_bridge()
        alert = bridge.on_trade_executed("AAPL", "long", 100, 150.0)
        assert "AAPL" in alert.dedup_key


# ═════════════════════════════════════════════════════════════════════
# Test Guard Rejection Spike Detection
# ═════════════════════════════════════════════════════════════════════


class TestGuardRejectionSpike:
    """Test threshold-based guard rejection alerting."""

    def test_no_alert_below_threshold(self):
        bridge = BotAlertBridge(config=AlertBridgeConfig(guard_rejection_threshold=5))
        for _ in range(4):
            result = bridge.on_guard_rejection_spike(1)
        assert result is None

    def test_alert_at_threshold(self):
        bridge = BotAlertBridge(config=AlertBridgeConfig(guard_rejection_threshold=3))
        results = []
        for _ in range(3):
            results.append(bridge.on_guard_rejection_spike(1))
        # The 3rd call should trigger the alert
        assert results[-1] is not None
        assert results[-1].severity == AlertSeverity.WARNING

    def test_counter_resets_after_spike(self):
        bridge = BotAlertBridge(config=AlertBridgeConfig(guard_rejection_threshold=2))
        bridge.on_guard_rejection_spike(1)
        alert = bridge.on_guard_rejection_spike(1)
        assert alert is not None
        # After spike, counter reset — next call should return None
        result = bridge.on_guard_rejection_spike(1)
        assert result is None

    def test_old_rejections_expire(self):
        bridge = BotAlertBridge(config=AlertBridgeConfig(
            guard_rejection_threshold=3,
            guard_rejection_window_seconds=0.1,
        ))
        bridge.on_guard_rejection_spike(1)
        bridge.on_guard_rejection_spike(1)
        time.sleep(0.2)
        # Old entries expired
        result = bridge.on_guard_rejection_spike(1)
        assert result is None


# ═════════════════════════════════════════════════════════════════════
# Test Alert Bridge Configuration
# ═════════════════════════════════════════════════════════════════════


class TestAlertBridgeConfig:
    """Test AlertBridgeConfig defaults and customization."""

    def test_default_config(self):
        config = AlertBridgeConfig()
        assert config.daily_loss_warning_pct == 0.80
        assert config.guard_rejection_threshold == 5
        assert config.guard_rejection_window_seconds == 60.0

    def test_custom_config(self):
        config = AlertBridgeConfig(
            daily_loss_warning_pct=0.90,
            guard_rejection_threshold=10,
            guard_rejection_window_seconds=120.0,
        )
        assert config.daily_loss_warning_pct == 0.90
        assert config.guard_rejection_threshold == 10

    def test_bridge_uses_custom_manager(self):
        mgr = AlertManager()
        bridge = BotAlertBridge(alert_manager=mgr)
        bridge.on_trade_executed("AAPL", "long", 100, 150.0)
        # Alert should exist in the custom manager
        assert len(mgr._alerts) >= 1

    def test_history_bounded(self):
        bridge = BotAlertBridge()
        for i in range(20):
            bridge.on_trade_executed(f"T{i}", "long", 10, 100.0)
        history = bridge.get_alert_history(limit=10)
        assert len(history) == 10

    def test_on_position_closed_contains_exit_reason(self):
        bridge = self._make_bridge()
        alert = bridge.on_position_closed("AAPL", "long", 50.0, "trailing_stop")
        assert "trailing_stop" in alert.message

    def _make_bridge(self) -> BotAlertBridge:
        return BotAlertBridge(alert_manager=AlertManager())

    def test_on_daily_loss_warning_high_pct(self):
        bridge = self._make_bridge()
        alert = bridge.on_daily_loss_warning(-950.0, 1000.0)
        assert "95%" in alert.title

    def test_on_error_stage_in_dedup_key(self):
        bridge = self._make_bridge()
        alert = bridge.on_error("order_submission", "Connection refused")
        assert "order_submission" in alert.dedup_key

    def test_multiple_alerts_different_types(self):
        bridge = self._make_bridge()
        bridge.on_trade_executed("AAPL", "long", 100, 150.0)
        bridge.on_position_closed("AAPL", "long", 50.0, "target")
        bridge.on_kill_switch("test")
        bridge.on_error("risk", "timeout")
        history = bridge.get_alert_history()
        assert len(history) == 4

    def test_emergency_close_has_count(self):
        bridge = self._make_bridge()
        alert = bridge.on_emergency_close(3)
        assert "3" in alert.tags.get("count", "")
