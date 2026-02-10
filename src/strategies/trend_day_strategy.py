"""Trend Day Strategy — detect and trade trend days.

Implements Ripster's trend day detection: "If the market reaches a new
high or low by 10:00-10:30 AM, it's likely a trend day. Go full size."

Detects opening range breakout within the first hour, confirms with
cloud alignment and volume, and generates a high-conviction signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.ema_signals.detector import TradeSignal, SignalType


@dataclass
class TrendDayConfig:
    """Configuration for trend day strategy.

    Attributes:
        opening_range_bars: Number of bars forming the opening range.
        breakout_deadline_bars: Max bars to wait for range breakout.
        volume_threshold: Min volume ratio for breakout confirmation.
        atr_expansion: Min ATR expansion ratio for trend day.
        atr_period: ATR lookback period.
        ema_short: Short EMA for cloud check.
        ema_long: Long EMA for cloud check.
        macro_short: Macro cloud short period.
        macro_long: Macro cloud long period.
    """
    opening_range_bars: int = 6   # 6 bars on 5m = 30 min
    breakout_deadline_bars: int = 12  # 12 bars on 5m = 60 min
    volume_threshold: float = 1.5
    atr_expansion: float = 1.2
    atr_period: int = 14
    ema_short: int = 5
    ema_long: int = 12
    macro_short: int = 34
    macro_long: int = 50


class TrendDayStrategy:
    """Trend day detection and full-size entry strategy.

    Entry logic:
    1. Identify opening range (first N bars)
    2. Detect breakout above/below range within deadline
    3. Confirm all clouds aligned in breakout direction
    4. Volume confirmation on breakout bar
    5. ATR check: intraday range expansion above normal
    6. High-conviction signal (80+) for trend day trades
    7. Wide stop at macro cloud, no fixed target (trail with fast cloud)
    """

    def __init__(self, config: TrendDayConfig | None = None) -> None:
        self.config = config or TrendDayConfig()

    @property
    def name(self) -> str:
        return "trend_day"

    def analyze(
        self,
        ticker: str,
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
    ) -> Optional[TradeSignal]:
        """Analyze bars for trend day breakout."""
        min_bars = max(self.config.breakout_deadline_bars + self.config.atr_period + 5, self.config.macro_long + 2)
        if len(closes) < min_bars:
            return None

        # Opening range from the first N bars at the end (simulating today's session)
        or_bars = self.config.opening_range_bars
        deadline = self.config.breakout_deadline_bars

        # We work with the most recent `deadline` bars
        session_highs = highs[-deadline:]
        session_lows = lows[-deadline:]
        session_closes = closes[-deadline:]
        session_volumes = volumes[-deadline:]

        # Opening range high/low
        or_high = max(session_highs[:or_bars])
        or_low = min(session_lows[:or_bars])

        # Check if price broke out of range after opening range
        breakout_up = False
        breakout_down = False
        breakout_bar_idx = None

        for i in range(or_bars, len(session_closes)):
            if session_closes[i] > or_high and not breakout_up:
                breakout_up = True
                breakout_bar_idx = i
                break
            if session_closes[i] < or_low and not breakout_down:
                breakout_down = True
                breakout_bar_idx = i
                break

        if not (breakout_up or breakout_down):
            return None

        # Volume confirmation
        avg_vol = sum(volumes[-20:]) / max(len(volumes[-20:]), 1)
        breakout_vol = session_volumes[breakout_bar_idx] if breakout_bar_idx is not None else 0
        vol_ratio = breakout_vol / max(avg_vol, 1)
        if vol_ratio < self.config.volume_threshold:
            return None

        # ATR expansion check
        atr = self._compute_atr(highs, lows, closes, self.config.atr_period)
        today_range = max(session_highs) - min(session_lows)
        if atr > 0 and today_range / atr < self.config.atr_expansion:
            return None

        # Cloud alignment check
        ema_short = self._ema(closes, self.config.ema_short)
        ema_long = self._ema(closes, self.config.ema_long)
        macro_short_ema = self._ema(closes, self.config.macro_short)
        macro_long_ema = self._ema(closes, self.config.macro_long)

        clouds_bullish = (
            ema_short[-1] > ema_long[-1]
            and macro_short_ema[-1] > macro_long_ema[-1]
        )
        clouds_bearish = (
            ema_short[-1] < ema_long[-1]
            and macro_short_ema[-1] < macro_long_ema[-1]
        )

        price = closes[-1]
        macro_lower = min(macro_short_ema[-1], macro_long_ema[-1])
        macro_upper = max(macro_short_ema[-1], macro_long_ema[-1])

        if breakout_up and clouds_bullish:
            stop = macro_lower * 0.995
            conviction = self._compute_conviction(vol_ratio, today_range / max(atr, 0.01))
            return TradeSignal(
                signal_type=SignalType.TREND_ALIGNED_LONG,
                direction="long",
                ticker=ticker,
                timeframe="5m",
                conviction=conviction,
                entry_price=price,
                stop_loss=stop,
                target_price=None,  # Trail with fast cloud on trend days
                timestamp=datetime.now(timezone.utc),
                metadata={
                    "strategy": "trend_day",
                    "or_high": round(or_high, 2),
                    "or_low": round(or_low, 2),
                    "volume_ratio": round(vol_ratio, 2),
                    "atr_expansion": round(today_range / max(atr, 0.01), 2),
                },
            )

        if breakout_down and clouds_bearish:
            stop = macro_upper * 1.005
            conviction = self._compute_conviction(vol_ratio, today_range / max(atr, 0.01))
            return TradeSignal(
                signal_type=SignalType.TREND_ALIGNED_SHORT,
                direction="short",
                ticker=ticker,
                timeframe="5m",
                conviction=conviction,
                entry_price=price,
                stop_loss=stop,
                target_price=None,
                timestamp=datetime.now(timezone.utc),
                metadata={
                    "strategy": "trend_day",
                    "or_high": round(or_high, 2),
                    "or_low": round(or_low, 2),
                    "volume_ratio": round(vol_ratio, 2),
                    "atr_expansion": round(today_range / max(atr, 0.01), 2),
                },
            )

        return None

    def _compute_conviction(self, vol_ratio: float, atr_expansion: float) -> int:
        """Trend days get high conviction — 80+ base."""
        base = 80
        if vol_ratio >= 2.5:
            base += 10
        elif vol_ratio >= 2.0:
            base += 5
        if atr_expansion >= 2.0:
            base += 5
        return min(95, base)

    @staticmethod
    def _ema(data: list[float], period: int) -> list[float]:
        if not data or period <= 0:
            return data[:]
        multiplier = 2 / (period + 1)
        ema = [data[0]]
        for i in range(1, len(data)):
            ema.append(data[i] * multiplier + ema[-1] * (1 - multiplier))
        return ema

    @staticmethod
    def _compute_atr(highs: list[float], lows: list[float], closes: list[float], period: int) -> float:
        if len(highs) < period + 1:
            return 0.0
        trs = []
        for i in range(1, len(highs)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)
        if len(trs) < period:
            return sum(trs) / max(len(trs), 1)
        return sum(trs[-period:]) / period
