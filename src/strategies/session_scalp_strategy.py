"""Session-Aware Scalp Strategy — Ripster's time-of-day routing.

Different market sessions require different tactics:
- Open bell (9:30-10:30): ORB + cloud alignment, aggressive entries
- Midday (10:30-14:00): Pullback-only, tighter stops, smaller size
- Power hour (14:00-16:00): Momentum continuation, wider targets
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.ema_signals.detector import TradeSignal, SignalType


@dataclass
class SessionScalpConfig:
    """Configuration for session-aware scalping.

    Attributes:
        open_bell_end_bar: Bar index marking end of open bell (e.g., 12 = 60min on 5m).
        power_hour_start_bar: Bar index marking start of power hour.
        midday_min_trend_bars: Min bars of trend needed for midday entry.
        ema_fast: Fast EMA period.
        ema_slow: Slow EMA period.
        pullback_short: Pullback cloud short period.
        pullback_long: Pullback cloud long period.
        macro_short: Macro cloud short period.
        macro_long: Macro cloud long period.
    """
    open_bell_end_bar: int = 12      # First 60 min on 5m chart
    power_hour_start_bar: int = 54   # ~4.5 hours into session on 5m
    midday_min_trend_bars: int = 8
    ema_fast: int = 5
    ema_slow: int = 12
    pullback_short: int = 8
    pullback_long: int = 9
    macro_short: int = 34
    macro_long: int = 50
    open_bell_conviction_boost: int = 10
    midday_conviction_penalty: int = 10
    power_hour_conviction_boost: int = 5


class SessionScalpStrategy:
    """Session-aware scalping strategy.

    Routes to different setups based on time of day:
    - OPEN BELL: ORB + cloud color -> aggressive entry
    - MIDDAY: Pullback-to-cloud in established trend only -> conservative
    - POWER HOUR: Momentum continuation with volume surge -> moderate
    """

    def __init__(self, config: SessionScalpConfig | None = None) -> None:
        self.config = config or SessionScalpConfig()

    @property
    def name(self) -> str:
        return "session_scalp"

    def analyze(
        self,
        ticker: str,
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
    ) -> Optional[TradeSignal]:
        """Analyze bars with session-aware logic."""
        min_bars = max(self.config.macro_long + 2, self.config.power_hour_start_bar + 2)
        if len(closes) < min_bars:
            return None

        # Determine session based on bar count within today's data
        # Use the length of data as a proxy for session position
        session_bars = len(closes)
        session = self._classify_session(session_bars)

        if session == "open_bell":
            return self._analyze_open_bell(ticker, opens, highs, lows, closes, volumes)
        elif session == "midday":
            return self._analyze_midday(ticker, opens, highs, lows, closes, volumes)
        else:  # power_hour
            return self._analyze_power_hour(ticker, opens, highs, lows, closes, volumes)

    def _classify_session(self, bar_count: int) -> str:
        """Classify which trading session we're in."""
        if bar_count <= self.config.open_bell_end_bar:
            return "open_bell"
        elif bar_count >= self.config.power_hour_start_bar:
            return "power_hour"
        return "midday"

    def _analyze_open_bell(
        self, ticker: str, opens: list[float], highs: list[float],
        lows: list[float], closes: list[float], volumes: list[float],
    ) -> Optional[TradeSignal]:
        """Open bell: ORB break + cloud alignment -> aggressive."""
        if len(closes) < 4:
            return None

        # First 3 bars = 15 min opening range
        or_high = max(highs[:3]) if len(highs) >= 3 else highs[0]
        or_low = min(lows[:3]) if len(lows) >= 3 else lows[0]
        price = closes[-1]

        # Cloud alignment
        fast_ema = self._ema(closes, self.config.ema_fast)
        slow_ema = self._ema(closes, self.config.ema_slow)
        macro_short_ema = self._ema(closes, self.config.macro_short)
        macro_long_ema = self._ema(closes, self.config.macro_long)

        clouds_bullish = fast_ema[-1] > slow_ema[-1]
        clouds_bearish = fast_ema[-1] < slow_ema[-1]

        macro_lower = min(macro_short_ema[-1], macro_long_ema[-1])
        macro_upper = max(macro_short_ema[-1], macro_long_ema[-1])

        # Volume check
        avg_vol = sum(volumes[-10:]) / max(len(volumes[-10:]), 1)
        vol_ratio = volumes[-1] / max(avg_vol, 1)

        if price > or_high and clouds_bullish and vol_ratio >= 1.2:
            stop = or_low * 0.998
            risk = price - stop
            target = price + risk * 2.0
            conviction = min(90, 65 + self.config.open_bell_conviction_boost)
            return TradeSignal(
                signal_type=SignalType.CLOUD_CROSS_BULLISH,
                direction="long",
                ticker=ticker,
                timeframe="5m",
                conviction=conviction,
                entry_price=price,
                stop_loss=stop,
                target_price=target,
                timestamp=datetime.now(timezone.utc),
                metadata={"strategy": "session_scalp", "session": "open_bell", "volume_ratio": round(vol_ratio, 2)},
            )

        if price < or_low and clouds_bearish and vol_ratio >= 1.2:
            stop = or_high * 1.002
            risk = stop - price
            target = price - risk * 2.0
            conviction = min(90, 65 + self.config.open_bell_conviction_boost)
            return TradeSignal(
                signal_type=SignalType.CLOUD_CROSS_BEARISH,
                direction="short",
                ticker=ticker,
                timeframe="5m",
                conviction=conviction,
                entry_price=price,
                stop_loss=stop,
                target_price=target,
                timestamp=datetime.now(timezone.utc),
                metadata={"strategy": "session_scalp", "session": "open_bell", "volume_ratio": round(vol_ratio, 2)},
            )

        return None

    def _analyze_midday(
        self, ticker: str, opens: list[float], highs: list[float],
        lows: list[float], closes: list[float], volumes: list[float],
    ) -> Optional[TradeSignal]:
        """Midday: pullback-to-cloud in established trend only."""
        pullback_short_ema = self._ema(closes, self.config.pullback_short)
        pullback_long_ema = self._ema(closes, self.config.pullback_long)
        macro_short_ema = self._ema(closes, self.config.macro_short)
        macro_long_ema = self._ema(closes, self.config.macro_long)

        price = closes[-1]
        pb_upper = max(pullback_short_ema[-1], pullback_long_ema[-1])
        pb_lower = min(pullback_short_ema[-1], pullback_long_ema[-1])
        macro_lower = min(macro_short_ema[-1], macro_long_ema[-1])
        macro_upper = max(macro_short_ema[-1], macro_long_ema[-1])

        trend_bars = self.config.midday_min_trend_bars

        # Check uptrend
        uptrend = all(
            closes[-(trend_bars + i)] > max(macro_short_ema[-(trend_bars + i)], macro_long_ema[-(trend_bars + i)])
            for i in range(trend_bars)
            if -(trend_bars + i) >= -len(closes)
        )

        if uptrend and lows[-2] <= pb_upper * 1.002 and price > pb_upper:
            stop = macro_lower * 0.998
            risk = price - stop
            target = price + risk * 1.5  # Tighter target for midday
            conviction = max(40, 55 - self.config.midday_conviction_penalty)
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
                metadata={"strategy": "session_scalp", "session": "midday"},
            )

        # Check downtrend
        downtrend = all(
            closes[-(trend_bars + i)] < min(macro_short_ema[-(trend_bars + i)], macro_long_ema[-(trend_bars + i)])
            for i in range(trend_bars)
            if -(trend_bars + i) >= -len(closes)
        )

        if downtrend and highs[-2] >= pb_lower * 0.998 and price < pb_lower:
            stop = macro_upper * 1.002
            risk = stop - price
            target = price - risk * 1.5
            conviction = max(40, 55 - self.config.midday_conviction_penalty)
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
                metadata={"strategy": "session_scalp", "session": "midday"},
            )

        return None

    def _analyze_power_hour(
        self, ticker: str, opens: list[float], highs: list[float],
        lows: list[float], closes: list[float], volumes: list[float],
    ) -> Optional[TradeSignal]:
        """Power hour: momentum continuation with volume surge."""
        fast_ema = self._ema(closes, self.config.ema_fast)
        slow_ema = self._ema(closes, self.config.ema_slow)
        macro_short_ema = self._ema(closes, self.config.macro_short)
        macro_long_ema = self._ema(closes, self.config.macro_long)

        price = closes[-1]
        macro_lower = min(macro_short_ema[-1], macro_long_ema[-1])
        macro_upper = max(macro_short_ema[-1], macro_long_ema[-1])

        # Volume surge in power hour
        avg_vol = sum(volumes[-20:]) / max(len(volumes[-20:]), 1)
        vol_ratio = volumes[-1] / max(avg_vol, 1)
        if vol_ratio < 1.3:
            return None

        # Strong trend: all EMAs aligned and price trending
        bullish = (fast_ema[-1] > slow_ema[-1] and macro_short_ema[-1] > macro_long_ema[-1]
                   and price > fast_ema[-1])
        bearish = (fast_ema[-1] < slow_ema[-1] and macro_short_ema[-1] < macro_long_ema[-1]
                   and price < fast_ema[-1])

        if bullish:
            stop = min(fast_ema[-1], slow_ema[-1]) * 0.998
            risk = price - stop
            target = price + risk * 2.5  # Wider target for power hour
            conviction = min(85, 60 + self.config.power_hour_conviction_boost)
            return TradeSignal(
                signal_type=SignalType.TREND_ALIGNED_LONG,
                direction="long",
                ticker=ticker,
                timeframe="5m",
                conviction=conviction,
                entry_price=price,
                stop_loss=stop,
                target_price=target,
                timestamp=datetime.now(timezone.utc),
                metadata={"strategy": "session_scalp", "session": "power_hour", "volume_ratio": round(vol_ratio, 2)},
            )

        if bearish:
            stop = max(fast_ema[-1], slow_ema[-1]) * 1.002
            risk = stop - price
            target = price - risk * 2.5
            conviction = min(85, 60 + self.config.power_hour_conviction_boost)
            return TradeSignal(
                signal_type=SignalType.TREND_ALIGNED_SHORT,
                direction="short",
                ticker=ticker,
                timeframe="5m",
                conviction=conviction,
                entry_price=price,
                stop_loss=stop,
                target_price=target,
                timestamp=datetime.now(timezone.utc),
                metadata={"strategy": "session_scalp", "session": "power_hour", "volume_ratio": round(vol_ratio, 2)},
            )

        return None

    @staticmethod
    def _ema(data: list[float], period: int) -> list[float]:
        if not data or period <= 0:
            return data[:]
        multiplier = 2 / (period + 1)
        ema = [data[0]]
        for i in range(1, len(data)):
            ema.append(data[i] * multiplier + ema[-1] * (1 - multiplier))
        return ema
