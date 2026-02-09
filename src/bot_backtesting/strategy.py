"""EMA Cloud Strategy adapter for backtesting.

Wraps the EMA Cloud signal detection pipeline into the backtesting
engine's Strategy Protocol, enabling historical validation of the
same signal logic used by the live autonomous trading bot.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd

from src.backtesting.models import (
    Fill,
    MarketEvent,
    OrderSide,
    Signal,
)
from src.backtesting.portfolio import SimulatedPortfolio
from src.ema_signals.clouds import CloudConfig, EMACloudCalculator
from src.ema_signals.conviction import ConvictionScorer
from src.ema_signals.detector import SignalDetector, SignalType, TradeSignal

logger = logging.getLogger(__name__)


@dataclass
class StrategyConfig:
    """Configuration for the EMA Cloud backtesting strategy."""

    cloud_config: CloudConfig = field(default_factory=CloudConfig)
    enabled_signal_types: list[SignalType] = field(
        default_factory=lambda: list(SignalType)
    )
    min_conviction: int = 50
    max_positions: int = 10
    max_position_weight: float = 0.15
    reward_to_risk: float = 2.0
    timeframe: str = "1d"
    lookback_bars: int = 100

    # Exit toggles
    stop_loss_exit: bool = True
    target_exit: bool = True
    cloud_flip_exit: bool = True
    exhaustion_exit: bool = True


@dataclass
class _OpenEntry:
    """Internal tracking for an open position."""

    entry_price: float
    stop_loss: float
    target_price: float
    signal_type: SignalType
    direction: str
    conviction: int
    entry_time: datetime

    def to_dict(self) -> dict:
        return {
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target_price": self.target_price,
            "signal_type": self.signal_type.value,
            "direction": self.direction,
            "conviction": self.conviction,
        }


class EMACloudStrategy:
    """Backtesting adapter for the EMA Cloud Signal Engine.

    Implements the backtesting Strategy Protocol (on_bar / on_fill)
    while internally reusing the same signal detection, cloud
    computation, and conviction scoring from src/ema_signals/.

    Accepts **kwargs in __init__ for WalkForwardOptimizer compatibility.
    """

    def __init__(self, **kwargs):
        # Build config from kwargs
        config_kwargs = {}
        cloud_kwargs = {}
        cloud_fields = {f.name for f in CloudConfig.__dataclass_fields__.values()}

        for key, value in kwargs.items():
            if key in cloud_fields:
                cloud_kwargs[key] = value
            elif hasattr(StrategyConfig, key):
                config_kwargs[key] = value

        if cloud_kwargs:
            config_kwargs["cloud_config"] = CloudConfig(**cloud_kwargs)

        self.config = StrategyConfig(**config_kwargs)

        # EMA signal components
        self.calculator = EMACloudCalculator(self.config.cloud_config)
        self.detector = SignalDetector(self.config.cloud_config)
        self.scorer = ConvictionScorer()

        # Per-symbol bar history
        self._bar_history: dict[str, pd.DataFrame] = {}

        # Open position tracking
        self._open_entries: dict[str, _OpenEntry] = {}

        # Pending signals awaiting fill confirmation
        self._pending_signals: dict[str, TradeSignal] = {}

        # Signal log for attribution
        self._signal_log: list[dict] = []

    def on_bar(
        self, event: MarketEvent, portfolio: SimulatedPortfolio
    ) -> list[Signal]:
        """Generate signals on new bar data.

        Process:
        1. Accumulate bars into per-symbol DataFrames
        2. Check exits for open positions
        3. Detect new entries via SignalDetector + ConvictionScorer
        4. Filter by enabled types + min conviction
        5. Convert TradeSignal -> backtesting Signal
        """
        signals: list[Signal] = []

        for symbol, bar in event.bars.items():
            # Accumulate bar history
            self._append_bar(symbol, bar)

            # Check exits first
            if symbol in self._open_entries:
                exit_signal = self._check_exits(symbol, event)
                if exit_signal:
                    signals.append(exit_signal)
                continue  # Don't enter new positions for held symbols

            # Skip if at max positions
            if len(self._open_entries) >= self.config.max_positions:
                continue

            # Need enough bars for EMA computation
            df = self._bar_history[symbol]
            if len(df) < self.calculator.config.max_period + 3:
                continue

            # Detect entries
            entry_signals = self._detect_entries(symbol, df, event.timestamp)
            signals.extend(entry_signals)

        return signals

    def on_fill(self, fill: Fill):
        """Called when an order is filled.

        On BUY fills: create _OpenEntry from pending signal.
        On SELL fills: remove _OpenEntry, log attribution.
        """
        symbol = fill.symbol

        if fill.side == OrderSide.BUY:
            # Match to pending signal
            if symbol in self._pending_signals:
                sig = self._pending_signals.pop(symbol)
                risk = abs(sig.entry_price - sig.stop_loss)
                target = sig.entry_price + risk * self.config.reward_to_risk

                self._open_entries[symbol] = _OpenEntry(
                    entry_price=fill.price,
                    stop_loss=sig.stop_loss,
                    target_price=target,
                    signal_type=sig.signal_type,
                    direction=sig.direction,
                    conviction=sig.conviction,
                    entry_time=fill.timestamp,
                )

                self._signal_log.append({
                    "symbol": symbol,
                    "signal_type": sig.signal_type.value,
                    "direction": sig.direction,
                    "conviction": sig.conviction,
                    "entry_price": fill.price,
                    "entry_date": fill.timestamp,
                    "stop_loss": sig.stop_loss,
                    "target_price": target,
                })

        elif fill.side == OrderSide.SELL:
            if symbol in self._open_entries:
                entry = self._open_entries.pop(symbol)
                # Update signal log with exit info
                for log_entry in reversed(self._signal_log):
                    if log_entry["symbol"] == symbol and "exit_date" not in log_entry:
                        log_entry["exit_date"] = fill.timestamp
                        log_entry["exit_price"] = fill.price
                        log_entry["exit_reason"] = fill.order_id if hasattr(fill, '_exit_reason') else "unknown"
                        break

    def get_signal_log(self) -> list[dict]:
        """Return signal log for attribution analysis."""
        return list(self._signal_log)

    def _conviction_to_weight(self, conviction: int) -> float:
        """Map conviction score (0-100) to portfolio weight (0.02-max_weight)."""
        raw = conviction / 100 * self.config.max_position_weight
        return max(0.02, min(raw, self.config.max_position_weight))

    def _check_exits(
        self, symbol: str, event: MarketEvent
    ) -> Optional[Signal]:
        """Check exit conditions for an open position.

        4 exit strategies:
        1. Stop loss: price breaches stop level
        2. Profit target: price reaches R:R target
        3. Cloud flip: fast cloud flips against position
        4. Momentum exhaustion: 3 bars extended outside cloud
        """
        entry = self._open_entries[symbol]
        bar = event.get_bar(symbol)
        if not bar:
            return None

        exit_reason = None

        # 1. Stop loss
        if self.config.stop_loss_exit:
            if entry.direction == "long" and bar.low <= entry.stop_loss:
                exit_reason = "stop_loss"
            elif entry.direction == "short" and bar.high >= entry.stop_loss:
                exit_reason = "stop_loss"

        # 2. Profit target
        if not exit_reason and self.config.target_exit:
            if entry.direction == "long" and bar.high >= entry.target_price:
                exit_reason = "profit_target"
            elif entry.direction == "short" and bar.low <= entry.target_price:
                exit_reason = "profit_target"

        # 3. Cloud flip (fast cloud 5/12 flips against position)
        if not exit_reason and self.config.cloud_flip_exit:
            df = self._bar_history.get(symbol)
            if df is not None and len(df) >= 3:
                cloud_df = self.calculator.compute_clouds(df)
                fast_short = self.config.cloud_config.fast_short
                fast_long = self.config.cloud_config.fast_long
                prev_bull = cloud_df[f"ema_{fast_short}"].iloc[-2] > cloud_df[f"ema_{fast_long}"].iloc[-2]
                curr_bull = cloud_df[f"ema_{fast_short}"].iloc[-1] > cloud_df[f"ema_{fast_long}"].iloc[-1]

                if entry.direction == "long" and prev_bull and not curr_bull:
                    exit_reason = "cloud_flip"
                elif entry.direction == "short" and not prev_bull and curr_bull:
                    exit_reason = "cloud_flip"

        # 4. Momentum exhaustion (3 bars outside fast cloud)
        if not exit_reason and self.config.exhaustion_exit:
            df = self._bar_history.get(symbol)
            if df is not None and len(df) >= 4:
                cloud_df = self.calculator.compute_clouds(df)
                fast_short = self.config.cloud_config.fast_short
                fast_long = self.config.cloud_config.fast_long
                upper = cloud_df[[f"ema_{fast_short}", f"ema_{fast_long}"]].max(axis=1)
                lower = cloud_df[[f"ema_{fast_short}", f"ema_{fast_long}"]].min(axis=1)

                closes = cloud_df["close"].iloc[-3:]
                upper_vals = upper.iloc[-3:]
                lower_vals = lower.iloc[-3:]

                if entry.direction == "long" and all(closes.values > upper_vals.values):
                    exit_reason = "exhaustion"
                elif entry.direction == "short" and all(closes.values < lower_vals.values):
                    exit_reason = "exhaustion"

        if exit_reason:
            # Update signal log with exit reason
            for log_entry in reversed(self._signal_log):
                if log_entry["symbol"] == symbol and "exit_reason" not in log_entry:
                    log_entry["exit_reason"] = exit_reason
                    break

            return Signal(
                symbol=symbol,
                timestamp=event.timestamp,
                side=OrderSide.SELL,
                target_weight=0.0,
                reason=exit_reason,
            )

        return None

    def _detect_entries(
        self, symbol: str, df: pd.DataFrame, timestamp: datetime
    ) -> list[Signal]:
        """Detect entry signals for a symbol using SignalDetector."""
        raw_signals = self.detector.detect(df, symbol, self.config.timeframe)

        if not raw_signals:
            return []

        results: list[Signal] = []

        for trade_signal in raw_signals:
            # Filter by enabled signal types
            if trade_signal.signal_type not in self.config.enabled_signal_types:
                continue

            # Skip exit signals (momentum_exhaustion can be exit)
            if trade_signal.direction == "short" and trade_signal.signal_type == SignalType.MOMENTUM_EXHAUSTION:
                continue

            # Score conviction
            volume_data = None
            if "volume" in df.columns and len(df) > 20:
                volume_data = {
                    "current_volume": float(df["volume"].iloc[-1]),
                    "avg_volume": float(df["volume"].iloc[-20:].mean()),
                }
            score = self.scorer.score(trade_signal, volume_data=volume_data)
            trade_signal.conviction = score.total

            # Filter by min conviction
            if score.total < self.config.min_conviction:
                continue

            # Only take long signals for simplicity in backtesting
            if trade_signal.direction != "long":
                continue

            # Convert to backtesting Signal
            weight = self._conviction_to_weight(score.total)
            bt_signal = Signal(
                symbol=symbol,
                timestamp=timestamp,
                side=OrderSide.BUY,
                target_weight=weight,
                reason=trade_signal.signal_type.value,
            )

            # Track pending signal for fill correlation
            self._pending_signals[symbol] = trade_signal
            results.append(bt_signal)

            # Only one entry per symbol per bar
            break

        return results

    def _append_bar(self, symbol: str, bar) -> None:
        """Accumulate a bar into the per-symbol DataFrame."""
        new_row = pd.DataFrame(
            [{
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }],
            index=[bar.timestamp],
        )

        if symbol not in self._bar_history:
            self._bar_history[symbol] = new_row
        else:
            self._bar_history[symbol] = pd.concat(
                [self._bar_history[symbol], new_row]
            )
            # Trim to lookback
            if len(self._bar_history[symbol]) > self.config.lookback_bars:
                self._bar_history[symbol] = self._bar_history[symbol].iloc[
                    -self.config.lookback_bars:
                ]
