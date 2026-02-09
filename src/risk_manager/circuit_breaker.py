"""Trading Circuit Breaker — halts trading on cascading losses.

Implements a three-state circuit breaker pattern adapted for trading:
  CLOSED (normal) → OPEN (halted) → HALF_OPEN (reduced) → CLOSED

Trips on consecutive losses, daily drawdown, or rapid loss rate.
Supports configurable cooldown periods and automatic half-open testing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════════════
# Enums & Config
# ═══════════════════════════════════════════════════════════════════════


class CircuitBreakerStatus(str, Enum):
    """Current state of the circuit breaker."""

    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Trading halted
    HALF_OPEN = "half_open"  # Reduced size, testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for the trading circuit breaker.

    Attributes:
        max_consecutive_losses: Losses in a row before tripping.
        max_daily_drawdown_pct: Daily drawdown % to trip.
        max_loss_rate_per_hour: Losses per hour threshold.
        cooldown_seconds: How long OPEN state lasts before HALF_OPEN.
        half_open_max_trades: Trades allowed in HALF_OPEN before deciding.
        half_open_size_multiplier: Position size multiplier in HALF_OPEN (0-1).
        auto_reset_on_win: Whether a win in HALF_OPEN auto-resets to CLOSED.
    """

    max_consecutive_losses: int = 3
    max_daily_drawdown_pct: float = 5.0
    max_loss_rate_per_hour: int = 5
    cooldown_seconds: int = 300  # 5 minutes
    half_open_max_trades: int = 3
    half_open_size_multiplier: float = 0.5
    auto_reset_on_win: bool = True


# ═══════════════════════════════════════════════════════════════════════
# Circuit Breaker State
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class CircuitBreakerState:
    """Internal state of the circuit breaker.

    Attributes:
        status: Current circuit breaker status.
        consecutive_losses: Running count of consecutive losses.
        daily_losses: Total losses today.
        daily_pnl: Running daily P&L.
        loss_timestamps: Timestamps of recent losses for rate calculation.
        tripped_at: When the breaker tripped to OPEN.
        half_open_trades: Trades completed in HALF_OPEN.
        half_open_wins: Wins in HALF_OPEN.
        trip_count: Total times the breaker has tripped.
        trip_reason: Why the breaker last tripped.
    """

    status: CircuitBreakerStatus = CircuitBreakerStatus.CLOSED
    consecutive_losses: int = 0
    daily_losses: int = 0
    daily_pnl: float = 0.0
    loss_timestamps: list[float] = field(default_factory=list)
    tripped_at: float = 0.0
    half_open_trades: int = 0
    half_open_wins: int = 0
    trip_count: int = 0
    trip_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "consecutive_losses": self.consecutive_losses,
            "daily_losses": self.daily_losses,
            "daily_pnl": round(self.daily_pnl, 2),
            "trip_count": self.trip_count,
            "trip_reason": self.trip_reason,
            "half_open_trades": self.half_open_trades,
            "half_open_wins": self.half_open_wins,
        }


# ═══════════════════════════════════════════════════════════════════════
# Trading Circuit Breaker
# ═══════════════════════════════════════════════════════════════════════


class TradingCircuitBreaker:
    """Three-state circuit breaker for trading risk management.

    State transitions:
      CLOSED → OPEN: When trip conditions are met (losses, drawdown, rate)
      OPEN → HALF_OPEN: After cooldown_seconds elapsed
      HALF_OPEN → CLOSED: After a win (if auto_reset) or completing half_open_max_trades
      HALF_OPEN → OPEN: If another loss occurs in half_open

    Args:
        config: CircuitBreakerConfig with trip thresholds.
        equity: Account equity for drawdown calculations.

    Example:
        cb = TradingCircuitBreaker(equity=100_000)
        if cb.allow_trade():
            # Execute trade
            cb.record_result(pnl=-500)  # May trip
        else:
            # Trading halted
            pass
    """

    def __init__(
        self,
        config: CircuitBreakerConfig | None = None,
        equity: float = 100_000.0,
    ) -> None:
        self.config = config or CircuitBreakerConfig()
        self._equity = equity
        self._state = CircuitBreakerState()

    @property
    def state(self) -> CircuitBreakerState:
        return self._state

    @property
    def status(self) -> CircuitBreakerStatus:
        self._check_cooldown()
        return self._state.status

    @property
    def is_trading_allowed(self) -> bool:
        """Whether trading is currently allowed."""
        self._check_cooldown()
        return self._state.status != CircuitBreakerStatus.OPEN

    def allow_trade(self) -> bool:
        """Check if a trade is allowed and handle state transitions."""
        self._check_cooldown()
        return self._state.status != CircuitBreakerStatus.OPEN

    def get_size_multiplier(self) -> float:
        """Get position size multiplier for current state.

        CLOSED: 1.0 (full size)
        HALF_OPEN: config.half_open_size_multiplier
        OPEN: 0.0 (no trading)
        """
        self._check_cooldown()
        if self._state.status == CircuitBreakerStatus.CLOSED:
            return 1.0
        elif self._state.status == CircuitBreakerStatus.HALF_OPEN:
            return self.config.half_open_size_multiplier
        return 0.0

    def record_result(self, pnl: float) -> CircuitBreakerStatus:
        """Record a trade result and potentially trip the breaker.

        Args:
            pnl: Trade P&L (negative = loss).

        Returns:
            The new circuit breaker status after evaluation.
        """
        self._state.daily_pnl += pnl
        now = time.monotonic()

        if pnl < 0:
            # Loss
            self._state.consecutive_losses += 1
            self._state.daily_losses += 1
            self._state.loss_timestamps.append(now)
            # Trim old timestamps (keep last hour)
            self._state.loss_timestamps = [
                t for t in self._state.loss_timestamps if now - t < 3600
            ]

            if self._state.status == CircuitBreakerStatus.HALF_OPEN:
                # Loss during half-open: re-trip
                self._trip("Loss during half-open recovery")
                return self._state.status

            # Check trip conditions
            if self._state.consecutive_losses >= self.config.max_consecutive_losses:
                self._trip(f"{self._state.consecutive_losses} consecutive losses")
            elif self._check_drawdown():
                self._trip(f"Daily drawdown exceeded {self.config.max_daily_drawdown_pct}%")
            elif self._check_loss_rate():
                self._trip(f"Loss rate exceeded {self.config.max_loss_rate_per_hour}/hour")

        else:
            # Win
            self._state.consecutive_losses = 0

            if self._state.status == CircuitBreakerStatus.HALF_OPEN:
                self._state.half_open_trades += 1
                self._state.half_open_wins += 1
                if self.config.auto_reset_on_win:
                    self._reset()
                elif self._state.half_open_trades >= self.config.half_open_max_trades:
                    self._reset()

        return self._state.status

    def reset(self) -> None:
        """Manual reset to CLOSED state."""
        self._reset()

    def reset_daily(self) -> None:
        """Reset daily counters (call at start of trading day)."""
        self._state.daily_losses = 0
        self._state.daily_pnl = 0.0
        self._state.consecutive_losses = 0
        self._state.loss_timestamps.clear()
        if self._state.status == CircuitBreakerStatus.OPEN:
            self._reset()

    # ── Internals ───────────────────────────────────────────────────

    def _trip(self, reason: str) -> None:
        """Transition to OPEN state."""
        self._state.status = CircuitBreakerStatus.OPEN
        self._state.tripped_at = time.monotonic()
        self._state.trip_count += 1
        self._state.trip_reason = reason
        self._state.half_open_trades = 0
        self._state.half_open_wins = 0

    def _reset(self) -> None:
        """Transition to CLOSED state."""
        self._state.status = CircuitBreakerStatus.CLOSED
        self._state.consecutive_losses = 0
        self._state.half_open_trades = 0
        self._state.half_open_wins = 0

    def _check_cooldown(self) -> None:
        """Transition OPEN → HALF_OPEN if cooldown has elapsed."""
        if self._state.status == CircuitBreakerStatus.OPEN:
            elapsed = time.monotonic() - self._state.tripped_at
            if elapsed >= self.config.cooldown_seconds:
                self._state.status = CircuitBreakerStatus.HALF_OPEN
                self._state.half_open_trades = 0
                self._state.half_open_wins = 0

    def _check_drawdown(self) -> bool:
        """Check if daily drawdown has exceeded threshold."""
        if self._equity <= 0:
            return False
        drawdown_pct = abs(self._state.daily_pnl) / self._equity * 100.0
        return self._state.daily_pnl < 0 and drawdown_pct >= self.config.max_daily_drawdown_pct

    def _check_loss_rate(self) -> bool:
        """Check if loss rate per hour exceeds threshold."""
        return len(self._state.loss_timestamps) >= self.config.max_loss_rate_per_hour
