"""Persistent state manager for the trading bot.

File-backed state that survives process restarts. Tracks:
- Kill switch state (active/reason/timestamp)
- Daily P&L tracking (single source of truth)
- Consecutive loss counter
- Circuit breaker state
- Daily trade count

Uses atomic writes (tmp + rename) to prevent corruption.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PersistentStateManager:
    """File-backed persistent state for the trading bot.

    All state is stored in a single JSON file and loaded on startup.
    Writes are atomic (write to .tmp, then rename) to prevent corruption
    on crash.

    Thread-safe: all reads and writes are protected by an RLock.

    Args:
        state_dir: Directory for state files.

    Example:
        mgr = PersistentStateManager("/tmp/bot_state")
        mgr.activate_kill_switch("Daily loss limit hit")
        # ... restart process ...
        mgr2 = PersistentStateManager("/tmp/bot_state")
        assert mgr2.kill_switch_active  # State survives restart
    """

    def __init__(self, state_dir: str = ".bot_state") -> None:
        self._lock = threading.RLock()
        self._state_dir = Path(state_dir)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._state_dir / "bot_state.json"
        self._state = self._load()

    # ── Kill Switch ──────────────────────────────────────────────────

    @property
    def kill_switch_active(self) -> bool:
        with self._lock:
            return self._state.get("kill_switch_active", False)

    @property
    def kill_switch_reason(self) -> Optional[str]:
        with self._lock:
            return self._state.get("kill_switch_reason")

    def activate_kill_switch(self, reason: str) -> None:
        """Activate kill switch (persisted immediately)."""
        with self._lock:
            self._state["kill_switch_active"] = True
            self._state["kill_switch_reason"] = reason
            self._state["kill_switch_activated_at"] = datetime.now(timezone.utc).isoformat()
            self._save()
        logger.critical("KILL SWITCH ACTIVATED (persisted): %s", reason)

    def deactivate_kill_switch(self) -> None:
        """Deactivate kill switch (manual reset)."""
        with self._lock:
            self._state["kill_switch_active"] = False
            self._state["kill_switch_reason"] = None
            self._state["kill_switch_activated_at"] = None
            self._state["consecutive_losses"] = []
            self._save()
        logger.info("Kill switch deactivated (persisted)")

    # ── Daily P&L ────────────────────────────────────────────────────

    @property
    def daily_pnl(self) -> float:
        with self._lock:
            self._check_day_rollover()
            return self._state.get("daily_pnl", 0.0)

    @property
    def daily_trade_count(self) -> int:
        with self._lock:
            self._check_day_rollover()
            return self._state.get("daily_trade_count", 0)

    def record_trade_pnl(self, pnl: float) -> None:
        """Record a trade P&L and update daily tracking."""
        with self._lock:
            self._check_day_rollover()
            self._state["daily_pnl"] = self._state.get("daily_pnl", 0.0) + pnl
            self._state["daily_trade_count"] = self._state.get("daily_trade_count", 0) + 1

            # PRD-171: Track lifetime realized P&L
            self._state["total_realized_pnl"] = self._state.get("total_realized_pnl", 0.0) + pnl

            # Track consecutive losses for kill switch
            if pnl < 0:
                losses = self._state.get("consecutive_losses", [])
                losses.append(pnl)
                self._state["consecutive_losses"] = losses
            else:
                self._state["consecutive_losses"] = []

            self._save()

    def get_consecutive_losses(self) -> list[float]:
        """Get current consecutive loss streak."""
        with self._lock:
            return list(self._state.get("consecutive_losses", []))

    def reset_daily(self) -> None:
        """Manually reset daily tracking."""
        with self._lock:
            self._state["daily_pnl"] = 0.0
            self._state["daily_trade_count"] = 0
            self._state["daily_date"] = date.today().isoformat()
            self._save()

    # ── PRD-171: Lifetime & Timestamp Tracking ────────────────────────

    @property
    def total_realized_pnl(self) -> float:
        """Lifetime realized P&L (survives daily resets)."""
        with self._lock:
            return self._state.get("total_realized_pnl", 0.0)

    @property
    def last_signal_time(self) -> Optional[str]:
        """ISO timestamp of last signal received."""
        with self._lock:
            return self._state.get("last_signal_time")

    @property
    def last_trade_time(self) -> Optional[str]:
        """ISO timestamp of last trade executed."""
        with self._lock:
            return self._state.get("last_trade_time")

    def record_signal_time(self) -> None:
        """Record current time as last signal received."""
        with self._lock:
            self._state["last_signal_time"] = datetime.now(timezone.utc).isoformat()
            self._save()

    def record_trade_time(self) -> None:
        """Record current time as last trade executed."""
        with self._lock:
            self._state["last_trade_time"] = datetime.now(timezone.utc).isoformat()
            self._save()

    # ── Circuit Breaker ──────────────────────────────────────────────

    @property
    def circuit_breaker_status(self) -> str:
        with self._lock:
            return self._state.get("circuit_breaker_status", "closed")

    def set_circuit_breaker(self, status: str, reason: str = "") -> None:
        """Set circuit breaker state (closed/open/half_open)."""
        with self._lock:
            self._state["circuit_breaker_status"] = status
            self._state["circuit_breaker_reason"] = reason
            self._state["circuit_breaker_changed_at"] = datetime.now(timezone.utc).isoformat()
            self._save()
        logger.warning("Circuit breaker → %s: %s", status, reason)

    # ── State Snapshot ───────────────────────────────────────────────

    def get_snapshot(self) -> dict[str, Any]:
        """Get a read-only copy of the full state."""
        with self._lock:
            return dict(self._state)

    # ── Internal ─────────────────────────────────────────────────────

    def _check_day_rollover(self) -> None:
        """Auto-reset daily counters if the date has changed."""
        today = date.today().isoformat()
        if self._state.get("daily_date") != today:
            self._state["daily_pnl"] = 0.0
            self._state["daily_trade_count"] = 0
            self._state["daily_date"] = today
            # Don't clear kill switch on rollover — that's manual
            self._save()

    def _load(self) -> dict:
        """Load state from disk, or return defaults."""
        if self._state_file.exists():
            try:
                with open(self._state_file) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.error("Corrupt state file, starting fresh: %s", e)
        return self._default_state()

    def _save(self) -> None:
        """Atomic write: write to .tmp then rename."""
        tmp_file = self._state_file.with_suffix(".json.tmp")
        try:
            with open(tmp_file, "w") as f:
                json.dump(self._state, f, indent=2, default=str)
            tmp_file.rename(self._state_file)
        except OSError as e:
            logger.error("Failed to persist state: %s", e)

    @staticmethod
    def _default_state() -> dict:
        return {
            "kill_switch_active": False,
            "kill_switch_reason": None,
            "kill_switch_activated_at": None,
            "daily_pnl": 0.0,
            "daily_trade_count": 0,
            "daily_date": date.today().isoformat(),
            "consecutive_losses": [],
            "circuit_breaker_status": "closed",
            "circuit_breaker_reason": "",
            "circuit_breaker_changed_at": None,
            # PRD-171: Lifetime & timestamp tracking
            "total_realized_pnl": 0.0,
            "last_signal_time": None,
            "last_trade_time": None,
        }
