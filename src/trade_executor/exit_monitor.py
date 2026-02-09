"""Continuous position monitoring for exit conditions.

Monitors open positions against 7 exit strategies:
1. Stop loss
2. Momentum exhaustion
3. Cloud flip
4. Profit target
5. Time stop
6. EOD close
7. Trailing stop
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Optional

import pandas as pd

from src.ema_signals.clouds import CloudState
from src.trade_executor.executor import ExecutorConfig, Position

logger = logging.getLogger(__name__)


@dataclass
class ExitSignal:
    """Signal to exit a position."""

    ticker: str
    exit_type: str  # stop_loss, exhaustion, cloud_flip, target, time_stop, eod, trailing
    priority: int  # 1 = highest
    reason: str

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "exit_type": self.exit_type,
            "priority": self.priority,
            "reason": self.reason,
        }


class ExitMonitor:
    """Monitor open positions for exit signals.

    Checks all 7 exit conditions and returns the highest-priority
    exit signal if any conditions are met.
    """

    def __init__(self, config: Optional[ExecutorConfig] = None):
        self.config = config or ExecutorConfig()

    def check_all(
        self,
        position: Position,
        current_price: float,
        cloud_states: Optional[list[CloudState]] = None,
        bars: Optional[pd.DataFrame] = None,
    ) -> Optional[ExitSignal]:
        """Check all exit conditions for a position.

        Returns the highest-priority ExitSignal, or None if no exit.
        """
        signals: list[ExitSignal] = []

        # 1. Stop loss (priority 1)
        sig = self.check_stop_loss(position, current_price)
        if sig:
            signals.append(sig)

        # 2. Momentum exhaustion (priority 2)
        if bars is not None:
            sig = self.check_momentum_exhaustion(position, bars)
            if sig:
                signals.append(sig)

        # 3. Cloud flip (priority 3)
        if cloud_states:
            sig = self.check_cloud_flip(position, cloud_states)
            if sig:
                signals.append(sig)

        # 4. Profit target (priority 4)
        sig = self.check_profit_target(position, current_price)
        if sig:
            signals.append(sig)

        # 5. Time stop (priority 5)
        sig = self.check_time_stop(position)
        if sig:
            signals.append(sig)

        # 6. EOD close (priority 6)
        sig = self.check_eod_close(position)
        if sig:
            signals.append(sig)

        # 7. Trailing stop (priority 7)
        if bars is not None:
            sig = self.check_trailing_stop(position, bars)
            if sig:
                signals.append(sig)

        if not signals:
            return None

        # Return highest priority (lowest number)
        return min(signals, key=lambda s: s.priority)

    def check_stop_loss(
        self, position: Position, current_price: float
    ) -> Optional[ExitSignal]:
        """Price closes below/above stop loss level."""
        if position.direction == "long" and current_price <= position.stop_loss:
            return ExitSignal(
                ticker=position.ticker,
                exit_type="stop_loss",
                priority=1,
                reason=f"Stop loss hit: ${current_price:.2f} <= ${position.stop_loss:.2f}",
            )
        if position.direction == "short" and current_price >= position.stop_loss:
            return ExitSignal(
                ticker=position.ticker,
                exit_type="stop_loss",
                priority=1,
                reason=f"Stop loss hit: ${current_price:.2f} >= ${position.stop_loss:.2f}",
            )
        return None

    def check_momentum_exhaustion(
        self, position: Position, bars: pd.DataFrame
    ) -> Optional[ExitSignal]:
        """3+ consecutive candles closing outside the fast cloud."""
        if len(bars) < 3:
            return None

        if "ema_5" not in bars.columns or "ema_12" not in bars.columns:
            return None

        upper = bars[["ema_5", "ema_12"]].max(axis=1)
        lower = bars[["ema_5", "ema_12"]].min(axis=1)
        recent = bars.iloc[-3:]

        if position.direction == "long":
            # 3 candles above fast cloud = exhaustion (exit long)
            if all(recent["close"].values > upper.iloc[-3:].values):
                return ExitSignal(
                    ticker=position.ticker,
                    exit_type="exhaustion",
                    priority=2,
                    reason="3 consecutive candles above fast cloud (momentum exhaustion)",
                )
        else:
            if all(recent["close"].values < lower.iloc[-3:].values):
                return ExitSignal(
                    ticker=position.ticker,
                    exit_type="exhaustion",
                    priority=2,
                    reason="3 consecutive candles below fast cloud (momentum exhaustion)",
                )
        return None

    def check_cloud_flip(
        self, position: Position, cloud_states: list[CloudState]
    ) -> Optional[ExitSignal]:
        """Fast cloud (5/12) flips against position direction."""
        fast_cloud = next((cs for cs in cloud_states if cs.cloud_name == "fast"), None)
        if not fast_cloud:
            return None

        if position.direction == "long" and not fast_cloud.is_bullish:
            return ExitSignal(
                ticker=position.ticker,
                exit_type="cloud_flip",
                priority=3,
                reason="Fast cloud flipped bearish (5/12 EMA)",
            )
        if position.direction == "short" and fast_cloud.is_bullish:
            return ExitSignal(
                ticker=position.ticker,
                exit_type="cloud_flip",
                priority=3,
                reason="Fast cloud flipped bullish (5/12 EMA)",
            )
        return None

    def check_profit_target(
        self, position: Position, current_price: float
    ) -> Optional[ExitSignal]:
        """2:1 reward-to-risk target reached."""
        if position.target_price is None:
            # Calculate from R:R ratio
            risk = abs(position.entry_price - position.stop_loss)
            reward = risk * self.config.reward_to_risk_target

            if position.direction == "long":
                target = position.entry_price + reward
            else:
                target = position.entry_price - reward
        else:
            target = position.target_price

        if position.direction == "long" and current_price >= target:
            return ExitSignal(
                ticker=position.ticker,
                exit_type="target",
                priority=4,
                reason=f"Profit target hit: ${current_price:.2f} >= ${target:.2f}",
            )
        if position.direction == "short" and current_price <= target:
            return ExitSignal(
                ticker=position.ticker,
                exit_type="target",
                priority=4,
                reason=f"Profit target hit: ${current_price:.2f} <= ${target:.2f}",
            )
        return None

    def check_time_stop(self, position: Position) -> Optional[ExitSignal]:
        """Position open too long with no progress (day trades only)."""
        if position.trade_type != "day":
            return None

        hold_minutes = position.hold_time.total_seconds() / 60
        if hold_minutes < self.config.time_stop_minutes:
            return None

        # Only trigger if position is flat or negative
        if position.unrealized_pnl_pct <= 0.005:  # Less than 0.5% gain
            return ExitSignal(
                ticker=position.ticker,
                exit_type="time_stop",
                priority=5,
                reason=f"Time stop: held {hold_minutes:.0f}min with no progress",
            )
        return None

    def check_eod_close(self, position: Position) -> Optional[ExitSignal]:
        """Day trades closed by 3:55 PM ET."""
        if position.trade_type != "day":
            return None

        now_utc = datetime.now(timezone.utc)
        et_hour = (now_utc.hour - 5) % 24
        et_minute = now_utc.minute

        parts = self.config.eod_close_time.split(":")
        close_hour = int(parts[0])
        close_minute = int(parts[1])

        if et_hour > close_hour or (et_hour == close_hour and et_minute >= close_minute):
            return ExitSignal(
                ticker=position.ticker,
                exit_type="eod",
                priority=6,
                reason=f"EOD close: past {self.config.eod_close_time} ET",
            )
        return None

    def check_trailing_stop(
        self, position: Position, bars: pd.DataFrame
    ) -> Optional[ExitSignal]:
        """Swing trades: trail stop at pullback cloud (8/9)."""
        if position.trade_type != "swing":
            return None

        if "ema_8" not in bars.columns or "ema_9" not in bars.columns:
            return None

        pullback_lower = bars[["ema_8", "ema_9"]].min(axis=1).iloc[-1]
        pullback_upper = bars[["ema_8", "ema_9"]].max(axis=1).iloc[-1]
        current_close = float(bars["close"].iloc[-1])

        if position.direction == "long" and current_close < pullback_lower:
            return ExitSignal(
                ticker=position.ticker,
                exit_type="trailing",
                priority=7,
                reason=f"Trailing stop: price ${current_close:.2f} below pullback cloud ${pullback_lower:.2f}",
            )
        if position.direction == "short" and current_close > pullback_upper:
            return ExitSignal(
                ticker=position.ticker,
                exit_type="trailing",
                priority=7,
                reason=f"Trailing stop: price ${current_close:.2f} above pullback cloud ${pullback_upper:.2f}",
            )
        return None
