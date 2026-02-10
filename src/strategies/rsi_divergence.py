"""PRD-177: RSI Divergence Strategy.

Detects bullish/bearish divergence between price and RSI,
confirmed by volume expansion.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.ema_signals.detector import TradeSignal, SignalType


@dataclass
class RSIDivergenceConfig:
    """Configuration for RSI Divergence strategy.

    Attributes:
        rsi_period: RSI lookback period.
        lookback_bars: Bars to search for divergence.
        rsi_oversold: RSI level for bullish divergence.
        rsi_overbought: RSI level for bearish divergence.
        min_price_change_pct: Minimum price change for divergence.
        volume_confirmation: Require volume above average.
        risk_reward: Target risk/reward ratio.
    """

    rsi_period: int = 14
    lookback_bars: int = 10
    rsi_oversold: float = 35.0
    rsi_overbought: float = 65.0
    min_price_change_pct: float = 1.0
    volume_confirmation: bool = True
    risk_reward: float = 2.0


class RSIDivergenceStrategy:
    """RSI divergence strategy with volume confirmation.

    Bullish divergence: price makes lower low but RSI makes higher low
    Bearish divergence: price makes higher high but RSI makes lower high
    """

    def __init__(self, config: RSIDivergenceConfig | None = None) -> None:
        self.config = config or RSIDivergenceConfig()

    @property
    def name(self) -> str:
        return "rsi_divergence"

    def analyze(
        self,
        ticker: str,
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
    ) -> Optional[TradeSignal]:
        """Analyze bars for RSI divergence."""
        min_bars = self.config.rsi_period + self.config.lookback_bars + 1
        if len(closes) < min_bars:
            return None

        rsi_values = self._compute_rsi_series(closes, self.config.rsi_period)
        if len(rsi_values) < self.config.lookback_bars:
            return None

        price = closes[-1]
        lookback = self.config.lookback_bars

        # Volume check
        if self.config.volume_confirmation and len(volumes) >= 20:
            avg_vol = sum(volumes[-20:]) / 20
            if volumes[-1] < avg_vol:
                return None

        # Bullish divergence: price lower low, RSI higher low
        recent_lows = lows[-lookback:]
        recent_rsi = rsi_values[-lookback:]
        price_low_idx = recent_lows.index(min(recent_lows))
        first_half_lows = lows[-(lookback * 2):-lookback] if len(lows) >= lookback * 2 else lows[:lookback]
        first_half_rsi = rsi_values[-(lookback * 2):-lookback] if len(rsi_values) >= lookback * 2 else rsi_values[:lookback]

        if first_half_lows and first_half_rsi:
            prev_price_low = min(first_half_lows)
            curr_price_low = min(recent_lows)
            prev_rsi_low = min(first_half_rsi)
            curr_rsi_low = min(recent_rsi)

            price_change_pct = (curr_price_low - prev_price_low) / max(prev_price_low, 0.01) * 100

            if (
                curr_price_low < prev_price_low
                and curr_rsi_low > prev_rsi_low
                and abs(price_change_pct) >= self.config.min_price_change_pct
                and curr_rsi_low < self.config.rsi_oversold
            ):
                stop = curr_price_low * 0.98
                target = price + (price - stop) * self.config.risk_reward
                conviction = min(85, 55 + abs(price_change_pct) * 3 + (prev_rsi_low - curr_rsi_low) * 0.5)
                return TradeSignal(
                    ticker=ticker,
                    direction="long",
                    signal_type=SignalType.MOMENTUM_EXHAUSTION,
                    entry_price=price,
                    stop_loss=stop,
                    target_price=target,
                    conviction=conviction,
                    timeframe="1d",
                    timestamp=datetime.now(timezone.utc),
                )

        # Bearish divergence: price higher high, RSI lower high
        recent_highs = highs[-lookback:]
        if first_half_lows and first_half_rsi:
            first_half_highs = highs[-(lookback * 2):-lookback] if len(highs) >= lookback * 2 else highs[:lookback]
            first_half_rsi_h = rsi_values[-(lookback * 2):-lookback] if len(rsi_values) >= lookback * 2 else rsi_values[:lookback]

            if first_half_highs and first_half_rsi_h:
                prev_price_high = max(first_half_highs)
                curr_price_high = max(recent_highs)
                prev_rsi_high = max(first_half_rsi_h)
                curr_rsi_high = max(recent_rsi)

                price_change_pct = (curr_price_high - prev_price_high) / max(prev_price_high, 0.01) * 100

                if (
                    curr_price_high > prev_price_high
                    and curr_rsi_high < prev_rsi_high
                    and abs(price_change_pct) >= self.config.min_price_change_pct
                    and curr_rsi_high > self.config.rsi_overbought
                ):
                    stop = curr_price_high * 1.02
                    target = price - (stop - price) * self.config.risk_reward
                    conviction = min(85, 55 + abs(price_change_pct) * 3 + (curr_rsi_high - prev_rsi_high) * 0.5)
                    return TradeSignal(
                        ticker=ticker,
                        direction="short",
                        signal_type=SignalType.MOMENTUM_EXHAUSTION,
                        entry_price=price,
                        stop_loss=stop,
                        target_price=target,
                        conviction=conviction,
                        timeframe="1d",
                        timestamp=datetime.now(timezone.utc),
                    )

        return None

    @staticmethod
    def _compute_rsi_series(closes: list[float], period: int) -> list[float]:
        """Compute RSI series from close prices."""
        if len(closes) < period + 1:
            return []

        changes = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        rsi_series = []

        for i in range(period, len(changes) + 1):
            window = changes[i - period:i]
            gains = [c for c in window if c > 0]
            losses = [-c for c in window if c < 0]
            avg_gain = sum(gains) / period if gains else 0
            avg_loss = sum(losses) / period if losses else 0
            if avg_loss < 1e-10:
                rsi_series.append(100.0 if avg_gain > 0 else 50.0)
            else:
                rs = avg_gain / avg_loss
                rsi_series.append(100 - (100 / (1 + rs)))

        return rsi_series
