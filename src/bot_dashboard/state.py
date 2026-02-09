"""Centralized bot state management.

Provides BotState snapshot, BotController for lifecycle management,
and DashboardConfig for display settings.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class DashboardConfig:
    """Configuration for the bot dashboard."""

    refresh_interval_seconds: int = 5
    pnl_chart_lookback_days: int = 30
    max_signals_displayed: int = 50
    max_events_displayed: int = 100
    enable_sound_alerts: bool = True
    paper_mode: bool = True
    require_confirmation_for_live: bool = True


# ═══════════════════════════════════════════════════════════════════════
# Bot State
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class BotState:
    """Current state of the trading bot, refreshed every tick."""

    status: Literal["live", "paused", "killed", "paper"] = "paper"
    instrument_mode: Literal["options", "leveraged_etf", "both"] = "both"
    uptime_seconds: int = 0
    account_equity: float = 0.0
    starting_equity: float = 0.0
    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_trades_today: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    current_exposure_pct: float = 0.0
    max_drawdown_today: float = 0.0
    kill_switch_active: bool = False
    last_signal_time: Optional[datetime] = None
    last_trade_time: Optional[datetime] = None
    active_broker: str = "paper"
    data_feed_status: str = "disconnected"
    errors: list[str] = field(default_factory=list)
    open_position_count: int = 0
    open_scalp_count: int = 0
    pending_signal_count: int = 0
    session_id: str = ""

    @property
    def is_active(self) -> bool:
        return self.status in ("live", "paper")

    @property
    def net_pnl(self) -> float:
        return self.realized_pnl + self.unrealized_pnl

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "instrument_mode": self.instrument_mode,
            "uptime_seconds": self.uptime_seconds,
            "account_equity": round(self.account_equity, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "daily_pnl_pct": round(self.daily_pnl_pct, 4),
            "win_rate": round(self.win_rate, 4),
            "total_trades_today": self.total_trades_today,
            "open_positions": self.open_position_count,
            "kill_switch_active": self.kill_switch_active,
            "data_feed_status": self.data_feed_status,
        }


# ═══════════════════════════════════════════════════════════════════════
# Bot Event
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class BotEvent:
    """A recorded bot event."""

    event_type: str
    severity: Literal["info", "warning", "error", "critical"]
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type,
            "severity": self.severity,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════
# Bot Controller
# ═══════════════════════════════════════════════════════════════════════


class BotController:
    """Control interface for the trading bot."""

    def __init__(self, config: Optional[DashboardConfig] = None):
        self.config = config or DashboardConfig()
        self._state = BotState(
            session_id=uuid.uuid4().hex[:12],
            status="paper" if self.config.paper_mode else "paused",
        )
        self._start_time = datetime.now(timezone.utc)
        self._events: list[BotEvent] = []
        self._config_history: list[dict] = []

    @property
    def state(self) -> BotState:
        self._state.uptime_seconds = int(
            (datetime.now(timezone.utc) - self._start_time).total_seconds()
        )
        return self._state

    def start(self, paper_mode: bool = True) -> None:
        """Start the bot in paper or live mode."""
        self._state.status = "paper" if paper_mode else "live"
        self._state.active_broker = "paper" if paper_mode else "alpaca"
        self._start_time = datetime.now(timezone.utc)
        self._record_event("lifecycle", "info", f"Bot started in {'paper' if paper_mode else 'live'} mode")

    def pause(self) -> None:
        """Pause signal processing (keep monitoring existing positions)."""
        if self._state.status in ("live", "paper"):
            prev = self._state.status
            self._state.status = "paused"
            self._record_event("lifecycle", "warning", f"Bot paused from {prev} mode")

    def resume(self) -> None:
        """Resume signal processing."""
        if self._state.status == "paused":
            self._state.status = "paper" if self.config.paper_mode else "live"
            self._record_event("lifecycle", "info", "Bot resumed")

    def kill(self, reason: str = "Manual kill switch") -> None:
        """Emergency stop: halt all trading."""
        self._state.status = "killed"
        self._state.kill_switch_active = True
        self._record_event("kill", "critical", f"Kill switch activated: {reason}")
        logger.critical("BOT KILLED: %s", reason)

    def reset_kill_switch(self) -> None:
        """Reset kill switch (manual only)."""
        self._state.kill_switch_active = False
        self._state.status = "paused"
        self._record_event("lifecycle", "info", "Kill switch reset — bot paused")

    def update_config(self, updates: dict) -> None:
        """Hot-update configuration without restart."""
        for key, value in updates.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self._config_history.append(updates)
        self._record_event("config_change", "info", f"Config updated: {list(updates.keys())}")

    def update_state(self, **kwargs) -> None:
        """Update bot state fields."""
        for key, value in kwargs.items():
            if hasattr(self._state, key):
                setattr(self._state, key, value)

    def get_events(self, limit: int = 50, severity: Optional[str] = None) -> list[BotEvent]:
        """Get recent events, optionally filtered by severity."""
        events = self._events
        if severity:
            events = [e for e in events if e.severity == severity]
        return events[-limit:]

    def _record_event(self, event_type: str, severity: str, message: str, metadata: dict = None) -> None:
        self._events.append(BotEvent(
            event_type=event_type,
            severity=severity,
            message=message,
            metadata=metadata or {},
        ))
