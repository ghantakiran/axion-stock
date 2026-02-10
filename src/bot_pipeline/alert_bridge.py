"""PRD-174: Bot Alert Bridge — wires AlertManager into the bot pipeline.

Emits alerts from pipeline events: trade execution, position close,
kill switch activation, daily loss warning, guard rejections, errors.
Uses dedup_key to avoid alert spam.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from src.alerting.config import AlertCategory, AlertSeverity
from src.alerting.manager import Alert, AlertManager

logger = logging.getLogger(__name__)


@dataclass
class AlertBridgeConfig:
    """Configuration for the bot alert bridge.

    Attributes:
        daily_loss_warning_pct: Fraction of daily limit that triggers warning.
        guard_rejection_threshold: Rejections in window to trigger alert.
        guard_rejection_window_seconds: Window for counting rejections.
    """

    daily_loss_warning_pct: float = 0.80
    guard_rejection_threshold: int = 5
    guard_rejection_window_seconds: float = 60.0


class BotAlertBridge:
    """Bridge between the bot pipeline and AlertManager.

    Translates pipeline events into structured alerts with proper
    severity, category, dedup keys, and metadata.

    Args:
        alert_manager: AlertManager instance (created if None).
        config: AlertBridgeConfig with thresholds.
    """

    def __init__(
        self,
        alert_manager: AlertManager | None = None,
        config: AlertBridgeConfig | None = None,
    ) -> None:
        self._manager = alert_manager or AlertManager()
        self.config = config or AlertBridgeConfig()
        self._guard_rejection_times: list[float] = []
        self._alert_history: list[dict[str, Any]] = []

    def on_trade_executed(
        self, ticker: str, direction: str, shares: float, price: float,
    ) -> Alert:
        """Alert when a position is opened."""
        alert = self._manager.fire(
            title=f"Trade Executed: {direction.upper()} {ticker}",
            message=f"Opened {direction} {shares:.0f} shares of {ticker} at ${price:.2f}",
            severity=AlertSeverity.INFO,
            category=AlertCategory.TRADING,
            source="bot_pipeline",
            tags={"ticker": ticker, "direction": direction},
            dedup_key=f"trade_exec_{ticker}_{direction}",
        )
        self._record(alert)
        return alert

    def on_position_closed(
        self, ticker: str, direction: str, pnl: float, exit_reason: str,
    ) -> Alert:
        """Alert when a position is closed."""
        severity = AlertSeverity.INFO if pnl >= 0 else AlertSeverity.WARNING
        alert = self._manager.fire(
            title=f"Position Closed: {ticker} P&L ${pnl:+.2f}",
            message=f"Closed {direction} {ticker}: P&L ${pnl:+.2f} — {exit_reason}",
            severity=severity,
            category=AlertCategory.TRADING,
            source="bot_pipeline",
            tags={"ticker": ticker, "pnl": str(round(pnl, 2))},
            dedup_key=f"pos_close_{ticker}",
        )
        self._record(alert)
        return alert

    def on_kill_switch(self, reason: str) -> Alert:
        """Alert when kill switch is activated."""
        alert = self._manager.fire(
            title="KILL SWITCH ACTIVATED",
            message=f"Bot kill switch activated: {reason}",
            severity=AlertSeverity.CRITICAL,
            category=AlertCategory.TRADING,
            source="bot_pipeline",
            tags={"event": "kill_switch"},
            dedup_key="kill_switch",
        )
        self._record(alert)
        return alert

    def on_daily_loss_warning(self, current_pnl: float, daily_limit: float) -> Alert:
        """Alert when P&L hits threshold percentage of daily limit."""
        pct = abs(current_pnl) / max(abs(daily_limit), 0.01) * 100
        alert = self._manager.fire(
            title=f"Daily Loss Warning: {pct:.0f}% of limit",
            message=(
                f"Daily P&L ${current_pnl:+.2f} has reached {pct:.0f}% "
                f"of the ${daily_limit:.2f} daily loss limit"
            ),
            severity=AlertSeverity.WARNING,
            category=AlertCategory.TRADING,
            source="bot_pipeline",
            tags={"daily_pnl": str(round(current_pnl, 2))},
            dedup_key="daily_loss_warning",
        )
        self._record(alert)
        return alert

    def on_guard_rejection_spike(self, rejection_count: int) -> Optional[Alert]:
        """Alert when guard rejections exceed threshold in time window.

        Returns None if threshold not reached.
        """
        now = time.time()
        self._guard_rejection_times.append(now)
        # Trim old entries
        cutoff = now - self.config.guard_rejection_window_seconds
        self._guard_rejection_times = [
            t for t in self._guard_rejection_times if t > cutoff
        ]
        if len(self._guard_rejection_times) >= self.config.guard_rejection_threshold:
            alert = self._manager.fire(
                title=f"Signal Guard: {len(self._guard_rejection_times)} rejections in {self.config.guard_rejection_window_seconds:.0f}s",
                message=(
                    f"{len(self._guard_rejection_times)} signals rejected by guard "
                    f"in the last {self.config.guard_rejection_window_seconds:.0f} seconds"
                ),
                severity=AlertSeverity.WARNING,
                category=AlertCategory.TRADING,
                source="bot_pipeline",
                tags={"event": "guard_spike"},
                dedup_key="guard_rejection_spike",
            )
            self._guard_rejection_times.clear()
            self._record(alert)
            return alert
        return None

    def on_emergency_close(self, positions_closed: int) -> Alert:
        """Alert when emergency close-all is triggered."""
        alert = self._manager.fire(
            title=f"EMERGENCY CLOSE: {positions_closed} positions",
            message=f"Emergency close-all executed: {positions_closed} positions closed",
            severity=AlertSeverity.CRITICAL,
            category=AlertCategory.TRADING,
            source="bot_pipeline",
            tags={"event": "emergency_close", "count": str(positions_closed)},
            dedup_key="emergency_close",
        )
        self._record(alert)
        return alert

    def on_error(self, stage: str, error: str) -> Alert:
        """Alert on pipeline error."""
        alert = self._manager.fire(
            title=f"Pipeline Error: {stage}",
            message=f"Error in pipeline stage '{stage}': {error}",
            severity=AlertSeverity.ERROR,
            category=AlertCategory.SYSTEM,
            source="bot_pipeline",
            tags={"stage": stage},
            dedup_key=f"pipeline_error_{stage}",
        )
        self._record(alert)
        return alert

    def get_alert_history(self, limit: int = 50) -> list[dict]:
        """Get recent bot alert history."""
        return self._alert_history[-limit:]

    def _record(self, alert: Alert) -> None:
        self._alert_history.append({
            "alert_id": alert.alert_id,
            "title": alert.title,
            "severity": alert.severity.value,
            "created_at": alert.created_at.isoformat(),
        })
        if len(self._alert_history) > 1000:
            self._alert_history = self._alert_history[-1000:]
