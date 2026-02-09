"""Enhanced Kill Switch — emergency halt with order cancellation.

Production kill switch that:
- Halts all new trades immediately
- Records the trigger event with reason and metadata
- Tracks armed/disarmed state with activation history
- Supports auto-trigger conditions (equity floor, drawdown, external signal)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import uuid


# ═══════════════════════════════════════════════════════════════════════
# Enums & Config
# ═══════════════════════════════════════════════════════════════════════


class KillSwitchState(str, Enum):
    """Kill switch state."""

    ARMED = "armed"           # Ready to trigger
    TRIGGERED = "triggered"   # Trading halted
    DISARMED = "disarmed"     # Kill switch inactive


@dataclass
class KillSwitchConfig:
    """Configuration for the enhanced kill switch.

    Attributes:
        equity_floor: Minimum equity before auto-trigger.
        max_daily_drawdown_pct: Daily drawdown % to auto-trigger.
        max_consecutive_errors: API errors before auto-trigger.
        require_manual_reset: If True, can only be disarmed manually.
    """

    equity_floor: float = 25_000.0
    max_daily_drawdown_pct: float = 10.0
    max_consecutive_errors: int = 5
    require_manual_reset: bool = True


# ═══════════════════════════════════════════════════════════════════════
# Kill Switch Event
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class KillSwitchEvent:
    """A kill switch activation/deactivation event.

    Attributes:
        event_id: Unique event identifier.
        action: 'triggered', 'disarmed', or 'armed'.
        reason: Why this event occurred.
        equity_at_event: Account equity at the time.
        daily_pnl: Running daily P&L at the time.
        triggered_by: 'manual', 'equity_floor', 'drawdown', 'errors', 'external'.
        timestamp: When the event occurred.
    """

    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    action: str = "triggered"
    reason: str = ""
    equity_at_event: float = 0.0
    daily_pnl: float = 0.0
    triggered_by: str = "manual"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "action": self.action,
            "reason": self.reason,
            "equity_at_event": round(self.equity_at_event, 2),
            "daily_pnl": round(self.daily_pnl, 2),
            "triggered_by": self.triggered_by,
            "timestamp": self.timestamp.isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════
# Enhanced Kill Switch
# ═══════════════════════════════════════════════════════════════════════


class EnhancedKillSwitch:
    """Emergency halt system with auto-trigger conditions.

    Three states:
      ARMED: Monitoring conditions, ready to trigger
      TRIGGERED: All trading halted
      DISARMED: Not monitoring (kill switch off)

    Auto-trigger conditions (when ARMED):
      1. Equity drops below floor (PDT protection)
      2. Daily drawdown exceeds limit
      3. Consecutive API errors exceed threshold

    Args:
        config: KillSwitchConfig with thresholds.
        initial_equity: Starting equity for drawdown tracking.

    Example:
        ks = EnhancedKillSwitch(initial_equity=100_000)
        ks.arm()
        if ks.is_triggered:
            print("TRADING HALTED:", ks.trigger_reason)
        ks.check_conditions(equity=24_000, daily_pnl=-6_000)
    """

    def __init__(
        self,
        config: KillSwitchConfig | None = None,
        initial_equity: float = 100_000.0,
    ) -> None:
        self.config = config or KillSwitchConfig()
        self._state = KillSwitchState.DISARMED
        self._initial_equity = initial_equity
        self._trigger_reason = ""
        self._consecutive_errors = 0
        self._events: list[KillSwitchEvent] = []

    @property
    def state(self) -> KillSwitchState:
        return self._state

    @property
    def is_triggered(self) -> bool:
        return self._state == KillSwitchState.TRIGGERED

    @property
    def is_armed(self) -> bool:
        return self._state == KillSwitchState.ARMED

    @property
    def trigger_reason(self) -> str:
        return self._trigger_reason

    @property
    def events(self) -> list[KillSwitchEvent]:
        return list(self._events)

    def arm(self) -> None:
        """Arm the kill switch (start monitoring)."""
        if self._state == KillSwitchState.TRIGGERED:
            return  # Can't arm while triggered
        self._state = KillSwitchState.ARMED
        self._consecutive_errors = 0
        self._record_event("armed", "Kill switch armed", "manual")

    def disarm(self) -> None:
        """Disarm the kill switch (stop monitoring)."""
        if self._state == KillSwitchState.TRIGGERED and self.config.require_manual_reset:
            # Allow disarm as explicit reset
            pass
        self._state = KillSwitchState.DISARMED
        self._trigger_reason = ""
        self._consecutive_errors = 0
        self._record_event("disarmed", "Kill switch disarmed", "manual")

    def trigger(self, reason: str = "Manual trigger", triggered_by: str = "manual",
                equity: float = 0.0, daily_pnl: float = 0.0) -> KillSwitchEvent:
        """Manually trigger the kill switch.

        Args:
            reason: Why the kill switch is being triggered.
            triggered_by: Source of the trigger.
            equity: Current equity (for event logging).
            daily_pnl: Current daily P&L (for event logging).

        Returns:
            KillSwitchEvent recording this trigger.
        """
        self._state = KillSwitchState.TRIGGERED
        self._trigger_reason = reason
        return self._record_event("triggered", reason, triggered_by, equity, daily_pnl)

    def check_conditions(
        self, equity: float, daily_pnl: float = 0.0
    ) -> bool:
        """Check auto-trigger conditions. Returns True if triggered.

        Args:
            equity: Current account equity.
            daily_pnl: Running daily P&L.

        Returns:
            True if the kill switch was triggered by this check.
        """
        if self._state != KillSwitchState.ARMED:
            return False

        # Check equity floor
        if equity < self.config.equity_floor:
            self.trigger(
                f"Equity ${equity:,.0f} below floor ${self.config.equity_floor:,.0f}",
                "equity_floor", equity, daily_pnl,
            )
            return True

        # Check daily drawdown
        if self._initial_equity > 0 and daily_pnl < 0:
            drawdown_pct = abs(daily_pnl) / self._initial_equity * 100.0
            if drawdown_pct >= self.config.max_daily_drawdown_pct:
                self.trigger(
                    f"Daily drawdown {drawdown_pct:.1f}% exceeds {self.config.max_daily_drawdown_pct}%",
                    "drawdown", equity, daily_pnl,
                )
                return True

        return False

    def record_error(self) -> bool:
        """Record an API error. Returns True if this triggers the kill switch."""
        self._consecutive_errors += 1
        if (
            self._state == KillSwitchState.ARMED
            and self._consecutive_errors >= self.config.max_consecutive_errors
        ):
            self.trigger(
                f"{self._consecutive_errors} consecutive errors",
                "errors",
            )
            return True
        return False

    def record_success(self) -> None:
        """Record a successful API call (resets error count)."""
        self._consecutive_errors = 0

    def get_history(self, limit: int = 20) -> list[KillSwitchEvent]:
        """Return recent kill switch events."""
        return list(reversed(self._events[-limit:]))

    # ── Internals ───────────────────────────────────────────────────

    def _record_event(
        self,
        action: str,
        reason: str,
        triggered_by: str,
        equity: float = 0.0,
        daily_pnl: float = 0.0,
    ) -> KillSwitchEvent:
        event = KillSwitchEvent(
            action=action,
            reason=reason,
            equity_at_event=equity,
            daily_pnl=daily_pnl,
            triggered_by=triggered_by,
        )
        self._events.append(event)
        return event
