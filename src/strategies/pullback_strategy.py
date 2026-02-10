"""Pullback-to-Cloud Strategy — core Ripster entry pattern.

Waits for price in an established trend to pull back to a cloud layer,
confirms a bounce off the cloud, and enters on continuation. This is
the bread-and-butter Ripster setup: trade WITH the trend, enter on
pullbacks to support.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.ema_signals.detector import TradeSignal, SignalType


@dataclass
class PullbackConfig:
    """Configuration for pullback-to-cloud strategy.

    Attributes:
        trend_lookback: Bars to confirm established trend.
        pullback_threshold_pct: Max distance from cloud to count as pullback (%).
        min_volume_ratio: Minimum volume ratio on bounce bar.
        risk_reward: Target R:R ratio.
        fast_short: Fast cloud short EMA period.
        fast_long: Fast cloud long EMA period.
        macro_short: Macro cloud short EMA period.
        macro_long: Macro cloud long EMA period.
    """
    trend_lookback: int = 10
    pullback_threshold_pct: float = 0.3
    min_volume_ratio: float = 1.0
    risk_reward: float = 2.0
    fast_short: int = 5
    fast_long: int = 12
    macro_short: int = 34
    macro_long: int = 50


class PullbackToCloudStrategy:
    """Pullback-to-cloud entry strategy implementing BotStrategy protocol.

    Entry logic:
    1. Confirm established trend (price above/below macro cloud for N bars)
    2. Detect pullback: price retraces TO fast cloud (within threshold %)
    3. Confirm bounce: current bar closes back above/below fast cloud
    4. Volume check: bounce bar has above-average volume
    5. Signal with stop at macro cloud, target at risk_reward x risk

    This is the highest-probability Ripster setup.
    """

    def __init__(self, config: PullbackConfig | None = None) -> None:
        self.config = config or PullbackConfig()

    @property
    def name(self) -> str:
        return "pullback_to_cloud"

    def analyze(
        self,
        ticker: str,
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
    ) -> Optional[TradeSignal]:
        """Analyze bars for pullback-to-cloud entry."""
        min_bars = max(self.config.macro_long + self.config.trend_lookback, 52)
        if len(closes) < min_bars:
            return None

        # Compute EMAs
        fast_short_ema = self._ema(closes, self.config.fast_short)
        fast_long_ema = self._ema(closes, self.config.fast_long)
        macro_short_ema = self._ema(closes, self.config.macro_short)
        macro_long_ema = self._ema(closes, self.config.macro_long)

        # Fast cloud boundaries
        fast_upper = max(fast_short_ema[-1], fast_long_ema[-1])
        fast_lower = min(fast_short_ema[-1], fast_long_ema[-1])

        # Macro cloud boundaries
        macro_upper = max(macro_short_ema[-1], macro_long_ema[-1])
        macro_lower = min(macro_short_ema[-1], macro_long_ema[-1])

        price = closes[-1]
        prev_low = lows[-2]
        prev_close = closes[-2]

        # Volume check
        avg_vol = sum(volumes[-20:]) / max(len(volumes[-20:]), 1)
        vol_ratio = volumes[-1] / max(avg_vol, 1)
        if vol_ratio < self.config.min_volume_ratio:
            return None

        # --- BULLISH PULLBACK ---
        # 1. Established uptrend: price above macro cloud for N bars
        lookback = self.config.trend_lookback
        uptrend = all(
            closes[-(lookback + i)] > max(macro_short_ema[-(lookback + i)], macro_long_ema[-(lookback + i)])
            for i in range(lookback)
            if -(lookback + i) >= -len(closes)
        )

        if uptrend:
            threshold = fast_upper * (self.config.pullback_threshold_pct / 100)
            # 2. Previous bar pulled back to fast cloud (low touched or within threshold)
            pullback = prev_low <= fast_upper + threshold and prev_close >= fast_lower
            # 3. Current bar bounced back above fast cloud
            bounce = price > fast_upper

            if pullback and bounce:
                stop = macro_lower * 0.998
                risk = price - stop
                target = price + risk * self.config.risk_reward
                conviction = self._compute_conviction(vol_ratio, lookback, True)
                return TradeSignal(
                    signal_type=SignalType.CLOUD_BOUNCE_LONG,
                    direction="long",
                    ticker=ticker,
                    timeframe="5m",
                    conviction=conviction,
                    entry_price=price,
                    stop_loss=stop,
                    target_price=target,
                    timestamp=datetime.now(timezone.utc),
                    metadata={
                        "strategy": "pullback_to_cloud",
                        "trend": "uptrend",
                        "volume_ratio": round(vol_ratio, 2),
                    },
                )

        # --- BEARISH PULLBACK ---
        prev_high = highs[-2]
        downtrend = all(
            closes[-(lookback + i)] < min(macro_short_ema[-(lookback + i)], macro_long_ema[-(lookback + i)])
            for i in range(lookback)
            if -(lookback + i) >= -len(closes)
        )

        if downtrend:
            threshold = fast_lower * (self.config.pullback_threshold_pct / 100)
            pullback = prev_high >= fast_lower - threshold and prev_close <= fast_upper
            bounce = price < fast_lower

            if pullback and bounce:
                stop = macro_upper * 1.002
                risk = stop - price
                target = price - risk * self.config.risk_reward
                conviction = self._compute_conviction(vol_ratio, lookback, False)
                return TradeSignal(
                    signal_type=SignalType.CLOUD_BOUNCE_SHORT,
                    direction="short",
                    ticker=ticker,
                    timeframe="5m",
                    conviction=conviction,
                    entry_price=price,
                    stop_loss=stop,
                    target_price=target,
                    timestamp=datetime.now(timezone.utc),
                    metadata={
                        "strategy": "pullback_to_cloud",
                        "trend": "downtrend",
                        "volume_ratio": round(vol_ratio, 2),
                    },
                )

        return None

    def _compute_conviction(self, vol_ratio: float, trend_bars: int, is_bull: bool) -> int:
        """Compute conviction score based on setup quality."""
        base = 55
        if vol_ratio >= 2.0:
            base += 15
        elif vol_ratio >= 1.5:
            base += 10
        elif vol_ratio >= 1.2:
            base += 5
        if trend_bars >= 15:
            base += 10
        elif trend_bars >= 10:
            base += 5
        return min(90, base)

    @staticmethod
    def _ema(data: list[float], period: int) -> list[float]:
        """Compute EMA over a list of floats."""
        if not data or period <= 0:
            return data[:]
        multiplier = 2 / (period + 1)
        ema = [data[0]]
        for i in range(1, len(data)):
            ema.append(data[i] * multiplier + ema[-1] * (1 - multiplier))
        return ema
