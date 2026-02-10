"""Signal detection from EMA cloud states.

Detects 12 signal types: cloud crosses, cloud flips, cloud bounces,
trend alignment, momentum exhaustion, multi-timeframe confluence,
and candlestick patterns at cloud boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

import numpy as np
import pandas as pd

from src.ema_signals.clouds import CloudConfig, CloudState, EMACloudCalculator


class SignalType(str, Enum):
    """Types of EMA cloud trade signals."""

    CLOUD_CROSS_BULLISH = "cloud_cross_bullish"
    CLOUD_CROSS_BEARISH = "cloud_cross_bearish"
    CLOUD_FLIP_BULLISH = "cloud_flip_bullish"
    CLOUD_FLIP_BEARISH = "cloud_flip_bearish"
    CLOUD_BOUNCE_LONG = "cloud_bounce_long"
    CLOUD_BOUNCE_SHORT = "cloud_bounce_short"
    TREND_ALIGNED_LONG = "trend_aligned_long"
    TREND_ALIGNED_SHORT = "trend_aligned_short"
    MOMENTUM_EXHAUSTION = "momentum_exhaustion"
    MTF_CONFLUENCE = "mtf_confluence"
    CANDLESTICK_BULLISH = "candlestick_bullish"
    CANDLESTICK_BEARISH = "candlestick_bearish"


@dataclass
class TradeSignal:
    """A structured trade signal emitted by the detection engine."""

    signal_type: SignalType
    direction: Literal["long", "short"]
    ticker: str
    timeframe: str
    conviction: int
    entry_price: float
    stop_loss: float
    target_price: Optional[float] = None
    cloud_states: list[CloudState] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "signal_type": self.signal_type.value,
            "direction": self.direction,
            "ticker": self.ticker,
            "timeframe": self.timeframe,
            "conviction": self.conviction,
            "entry_price": round(self.entry_price, 4),
            "stop_loss": round(self.stop_loss, 4),
            "target_price": round(self.target_price, 4) if self.target_price else None,
            "cloud_states": [cs.to_dict() for cs in self.cloud_states],
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════════════
# Signal Detector
# ═══════════════════════════════════════════════════════════════════════


class SignalDetector:
    """Detect trade signals from EMA cloud states.

    Scans the most recent bars of an OHLCV DataFrame for entry/exit
    signals based on cloud crosses, flips, bounces, alignment, and
    momentum exhaustion.
    """

    CLOUD_NAMES = ["fast", "pullback", "trend", "macro", "long_term"]
    BOUNCE_THRESHOLD = 0.002  # Price within 0.2% of cloud = "touching"
    EXHAUSTION_CANDLES = 3  # Consecutive candles outside cloud

    def __init__(self, config: Optional[CloudConfig] = None):
        self.calculator = EMACloudCalculator(config)

    def detect(
        self, df: pd.DataFrame, ticker: str, timeframe: str
    ) -> list[TradeSignal]:
        """Scan latest bars for entry/exit signals.

        Args:
            df: OHLCV DataFrame with at least 50+ bars.
            ticker: Ticker symbol.
            timeframe: Timeframe string ("1m", "5m", "10m", "1h", "1d").

        Returns:
            List of detected TradeSignal objects (may be empty).
        """
        if len(df) < self.calculator.config.max_period + 2:
            return []

        cloud_df = self.calculator.compute_clouds(df)
        cloud_states = self.calculator.get_cloud_states(cloud_df)
        signals: list[TradeSignal] = []

        # Detect each signal type across all cloud layers
        for cloud_name in self.CLOUD_NAMES:
            sig = self._detect_cloud_cross(cloud_df, cloud_name, ticker, timeframe, cloud_states)
            if sig:
                signals.append(sig)

            sig = self._detect_cloud_flip(cloud_df, cloud_name, ticker, timeframe, cloud_states)
            if sig:
                signals.append(sig)

            sig = self._detect_cloud_bounce(cloud_df, cloud_name, ticker, timeframe, cloud_states)
            if sig:
                signals.append(sig)

        # Trend alignment (all clouds agree)
        sig = self._detect_trend_alignment(cloud_df, ticker, timeframe, cloud_states)
        if sig:
            signals.append(sig)

        # Momentum exhaustion (exit signal)
        sig = self._detect_momentum_exhaustion(cloud_df, ticker, timeframe, cloud_states)
        if sig:
            signals.append(sig)

        # Candlestick patterns at cloud levels
        candle_signals = self._detect_candlestick_patterns(cloud_df, ticker, timeframe, cloud_states)
        signals.extend(candle_signals)

        return signals

    def _detect_cloud_cross(
        self,
        df: pd.DataFrame,
        cloud_name: str,
        ticker: str,
        timeframe: str,
        cloud_states: list[CloudState],
    ) -> Optional[TradeSignal]:
        """Price crosses above or below a cloud layer."""
        config = self.calculator.config
        pair = {name: (s, l) for name, s, l in config.get_pairs()}
        short_p, long_p = pair[cloud_name]

        upper = df[[f"ema_{short_p}", f"ema_{long_p}"]].max(axis=1)
        lower = df[[f"ema_{short_p}", f"ema_{long_p}"]].min(axis=1)

        prev_close = df["close"].iloc[-2]
        curr_close = df["close"].iloc[-1]
        prev_upper = upper.iloc[-2]
        prev_lower = lower.iloc[-2]
        curr_upper = upper.iloc[-1]
        curr_lower = lower.iloc[-1]

        # Bullish cross: previous close below cloud, current close above
        if prev_close <= prev_upper and curr_close > curr_upper:
            macro_ema = float(df[f"ema_{config.macro_long}"].iloc[-1])
            return TradeSignal(
                signal_type=SignalType.CLOUD_CROSS_BULLISH,
                direction="long",
                ticker=ticker,
                timeframe=timeframe,
                conviction=0,  # Scored later by ConvictionScorer
                entry_price=curr_close,
                stop_loss=macro_ema * 0.995,
                cloud_states=cloud_states,
                metadata={"cloud": cloud_name, "trigger": "cross_above"},
            )

        # Bearish cross: previous close above cloud, current close below
        if prev_close >= prev_lower and curr_close < curr_lower:
            macro_ema = float(df[f"ema_{config.macro_long}"].iloc[-1])
            return TradeSignal(
                signal_type=SignalType.CLOUD_CROSS_BEARISH,
                direction="short",
                ticker=ticker,
                timeframe=timeframe,
                conviction=0,
                entry_price=curr_close,
                stop_loss=macro_ema * 1.005,
                cloud_states=cloud_states,
                metadata={"cloud": cloud_name, "trigger": "cross_below"},
            )

        return None

    def _detect_cloud_flip(
        self,
        df: pd.DataFrame,
        cloud_name: str,
        ticker: str,
        timeframe: str,
        cloud_states: list[CloudState],
    ) -> Optional[TradeSignal]:
        """Fast EMA crosses above/below slow EMA (cloud changes color)."""
        config = self.calculator.config
        pair = {name: (s, l) for name, s, l in config.get_pairs()}
        short_p, long_p = pair[cloud_name]

        short_col = f"ema_{short_p}"
        long_col = f"ema_{long_p}"

        prev_short = df[short_col].iloc[-2]
        prev_long = df[long_col].iloc[-2]
        curr_short = df[short_col].iloc[-1]
        curr_long = df[long_col].iloc[-1]
        curr_close = float(df["close"].iloc[-1])

        # Bullish flip: short EMA crosses above long EMA
        if prev_short <= prev_long and curr_short > curr_long:
            macro_ema = float(df[f"ema_{config.macro_long}"].iloc[-1])
            return TradeSignal(
                signal_type=SignalType.CLOUD_FLIP_BULLISH,
                direction="long",
                ticker=ticker,
                timeframe=timeframe,
                conviction=0,
                entry_price=curr_close,
                stop_loss=macro_ema * 0.995,
                cloud_states=cloud_states,
                metadata={"cloud": cloud_name, "trigger": "flip_bullish"},
            )

        # Bearish flip: short EMA crosses below long EMA
        if prev_short >= prev_long and curr_short < curr_long:
            macro_ema = float(df[f"ema_{config.macro_long}"].iloc[-1])
            return TradeSignal(
                signal_type=SignalType.CLOUD_FLIP_BEARISH,
                direction="short",
                ticker=ticker,
                timeframe=timeframe,
                conviction=0,
                entry_price=curr_close,
                stop_loss=macro_ema * 1.005,
                cloud_states=cloud_states,
                metadata={"cloud": cloud_name, "trigger": "flip_bearish"},
            )

        return None

    def _detect_cloud_bounce(
        self,
        df: pd.DataFrame,
        cloud_name: str,
        ticker: str,
        timeframe: str,
        cloud_states: list[CloudState],
    ) -> Optional[TradeSignal]:
        """Price tests cloud from above/below and bounces away."""
        if len(df) < 4:
            return None

        config = self.calculator.config
        pair = {name: (s, l) for name, s, l in config.get_pairs()}
        short_p, long_p = pair[cloud_name]

        upper = df[[f"ema_{short_p}", f"ema_{long_p}"]].max(axis=1)
        lower = df[[f"ema_{short_p}", f"ema_{long_p}"]].min(axis=1)

        # Look at last 3 bars: approach → touch → bounce
        closes = df["close"].iloc[-3:].values
        lows = df["low"].iloc[-3:].values
        highs = df["high"].iloc[-3:].values
        upper_vals = upper.iloc[-3:].values
        lower_vals = lower.iloc[-3:].values

        curr_close = float(closes[-1])
        macro_ema = float(df[f"ema_{config.macro_long}"].iloc[-1])

        # Bounce long: price dips to cloud top, then bounces up
        # Previous bar's low touched or pierced upper cloud, current bar closes above
        if (lows[-2] <= upper_vals[-2] * (1 + self.BOUNCE_THRESHOLD)
                and closes[-2] >= lower_vals[-2]
                and curr_close > upper_vals[-1]
                and closes[-3] > upper_vals[-3]):
            return TradeSignal(
                signal_type=SignalType.CLOUD_BOUNCE_LONG,
                direction="long",
                ticker=ticker,
                timeframe=timeframe,
                conviction=0,
                entry_price=curr_close,
                stop_loss=macro_ema * 0.995,
                cloud_states=cloud_states,
                metadata={"cloud": cloud_name, "trigger": "bounce_long"},
            )

        # Bounce short: price rallies to cloud bottom, then drops
        if (highs[-2] >= lower_vals[-2] * (1 - self.BOUNCE_THRESHOLD)
                and closes[-2] <= upper_vals[-2]
                and curr_close < lower_vals[-1]
                and closes[-3] < lower_vals[-3]):
            return TradeSignal(
                signal_type=SignalType.CLOUD_BOUNCE_SHORT,
                direction="short",
                ticker=ticker,
                timeframe=timeframe,
                conviction=0,
                entry_price=curr_close,
                stop_loss=macro_ema * 1.005,
                cloud_states=cloud_states,
                metadata={"cloud": cloud_name, "trigger": "bounce_short"},
            )

        return None

    def _detect_trend_alignment(
        self,
        df: pd.DataFrame,
        ticker: str,
        timeframe: str,
        cloud_states: list[CloudState],
    ) -> Optional[TradeSignal]:
        """All 4 cloud layers aligned in the same direction."""
        if not cloud_states:
            return None

        all_bullish = all(cs.is_bullish for cs in cloud_states)
        all_bearish = all(not cs.is_bullish for cs in cloud_states)

        if not (all_bullish or all_bearish):
            return None

        # Also require price to be above all clouds (bullish) or below all (bearish)
        if all_bullish and not all(cs.price_above for cs in cloud_states):
            return None
        if all_bearish and not all(cs.price_below for cs in cloud_states):
            return None

        curr_close = float(df["close"].iloc[-1])
        macro_ema = float(df[f"ema_{self.calculator.config.macro_long}"].iloc[-1])

        direction: Literal["long", "short"] = "long" if all_bullish else "short"
        signal_type = SignalType.TREND_ALIGNED_LONG if all_bullish else SignalType.TREND_ALIGNED_SHORT

        stop_mult = 0.99 if direction == "long" else 1.01
        return TradeSignal(
            signal_type=signal_type,
            direction=direction,
            ticker=ticker,
            timeframe=timeframe,
            conviction=0,
            entry_price=curr_close,
            stop_loss=macro_ema * stop_mult,
            cloud_states=cloud_states,
            metadata={"trigger": "trend_alignment", "all_bullish": all_bullish},
        )

    def _detect_momentum_exhaustion(
        self,
        df: pd.DataFrame,
        ticker: str,
        timeframe: str,
        cloud_states: list[CloudState],
    ) -> Optional[TradeSignal]:
        """3+ consecutive candles closing outside the fast cloud — exhaustion/exit signal."""
        config = self.calculator.config
        short_p, long_p = config.fast_short, config.fast_long
        upper = df[[f"ema_{short_p}", f"ema_{long_p}"]].max(axis=1)
        lower = df[[f"ema_{short_p}", f"ema_{long_p}"]].min(axis=1)

        n = self.EXHAUSTION_CANDLES
        if len(df) < n + 1:
            return None

        recent_closes = df["close"].iloc[-n:]
        recent_upper = upper.iloc[-n:]
        recent_lower = lower.iloc[-n:]

        all_above = all(recent_closes.values > recent_upper.values)
        all_below = all(recent_closes.values < recent_lower.values)

        if not (all_above or all_below):
            return None

        # Check that we weren't already exhausted on the bar before
        prev_close = df["close"].iloc[-(n + 1)]
        prev_upper = upper.iloc[-(n + 1)]
        prev_lower = lower.iloc[-(n + 1)]

        if all_above and prev_close > prev_upper:
            return None  # Already signaled
        if all_below and prev_close < prev_lower:
            return None

        curr_close = float(df["close"].iloc[-1])
        macro_ema = float(df[f"ema_{config.macro_long}"].iloc[-1])

        # Exhaustion above cloud = potential short/exit long
        # Exhaustion below cloud = potential long/exit short
        direction: Literal["long", "short"] = "short" if all_above else "long"
        stop_mult = 1.01 if direction == "short" else 0.99

        return TradeSignal(
            signal_type=SignalType.MOMENTUM_EXHAUSTION,
            direction=direction,
            ticker=ticker,
            timeframe=timeframe,
            conviction=0,
            entry_price=curr_close,
            stop_loss=macro_ema * stop_mult,
            cloud_states=cloud_states,
            metadata={
                "trigger": "momentum_exhaustion",
                "exhaustion_side": "above" if all_above else "below",
                "consecutive_bars": n,
            },
        )

    def _detect_candlestick_patterns(
        self,
        df: pd.DataFrame,
        ticker: str,
        timeframe: str,
        cloud_states: list[CloudState],
    ) -> list[TradeSignal]:
        """Detect candlestick patterns occurring at cloud boundaries.

        Patterns: hammer, inverted hammer, bullish engulfing, bearish engulfing,
        doji at cloud, pin bar. Only emits signals when the pattern occurs
        within BOUNCE_THRESHOLD of a cloud level.
        """
        if len(df) < 3:
            return []

        signals: list[TradeSignal] = []
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        price = float(curr["close"])

        o, h, l, c = float(curr["open"]), float(curr["high"]), float(curr["low"]), float(curr["close"])
        body = abs(c - o)
        total_range = h - l
        if total_range < 1e-10:
            return signals

        body_ratio = body / total_range
        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l

        po, ph, pl, pc = float(prev["open"]), float(prev["high"]), float(prev["low"]), float(prev["close"])
        prev_body = abs(pc - po)

        # Check if price is near any cloud level
        near_cloud = False
        for cs in cloud_states:
            upper = max(cs.short_ema, cs.long_ema)
            lower = min(cs.short_ema, cs.long_ema)
            if (abs(price - upper) / max(price, 0.01) <= self.BOUNCE_THRESHOLD
                    or abs(price - lower) / max(price, 0.01) <= self.BOUNCE_THRESHOLD
                    or abs(l - upper) / max(price, 0.01) <= self.BOUNCE_THRESHOLD
                    or abs(h - lower) / max(price, 0.01) <= self.BOUNCE_THRESHOLD):
                near_cloud = True
                break

        if not near_cloud:
            return signals

        macro_ema = float(df[f"ema_{self.calculator.config.macro_long}"].iloc[-1])

        # Hammer (bullish): small body at top, long lower wick >= 2x body
        if body_ratio < 0.35 and lower_wick >= body * 2 and c > o:
            signals.append(TradeSignal(
                signal_type=SignalType.CANDLESTICK_BULLISH,
                direction="long",
                ticker=ticker,
                timeframe=timeframe,
                conviction=0,
                entry_price=price,
                stop_loss=l * 0.998,
                cloud_states=cloud_states,
                metadata={"pattern": "hammer", "body_ratio": round(body_ratio, 3)},
            ))

        # Inverted hammer (bullish): small body at bottom, long upper wick >= 2x body
        if body_ratio < 0.35 and upper_wick >= body * 2 and c > o:
            signals.append(TradeSignal(
                signal_type=SignalType.CANDLESTICK_BULLISH,
                direction="long",
                ticker=ticker,
                timeframe=timeframe,
                conviction=0,
                entry_price=price,
                stop_loss=l * 0.998,
                cloud_states=cloud_states,
                metadata={"pattern": "inverted_hammer", "body_ratio": round(body_ratio, 3)},
            ))

        # Bullish engulfing: current green candle engulfs previous red candle
        if c > o and pc < po and c > po and o < pc and body > prev_body:
            signals.append(TradeSignal(
                signal_type=SignalType.CANDLESTICK_BULLISH,
                direction="long",
                ticker=ticker,
                timeframe=timeframe,
                conviction=0,
                entry_price=price,
                stop_loss=min(l, pl) * 0.998,
                cloud_states=cloud_states,
                metadata={"pattern": "bullish_engulfing", "body_ratio": round(body_ratio, 3)},
            ))

        # Bearish engulfing: current red candle engulfs previous green candle
        if c < o and pc > po and o > pc and c < po and body > prev_body:
            signals.append(TradeSignal(
                signal_type=SignalType.CANDLESTICK_BEARISH,
                direction="short",
                ticker=ticker,
                timeframe=timeframe,
                conviction=0,
                entry_price=price,
                stop_loss=max(h, ph) * 1.002,
                cloud_states=cloud_states,
                metadata={"pattern": "bearish_engulfing", "body_ratio": round(body_ratio, 3)},
            ))

        # Pin bar bullish: long lower wick, small body, close near high
        if lower_wick > total_range * 0.6 and body_ratio < 0.3:
            signals.append(TradeSignal(
                signal_type=SignalType.CANDLESTICK_BULLISH,
                direction="long",
                ticker=ticker,
                timeframe=timeframe,
                conviction=0,
                entry_price=price,
                stop_loss=l * 0.998,
                cloud_states=cloud_states,
                metadata={"pattern": "pin_bar_bullish", "body_ratio": round(body_ratio, 3)},
            ))

        # Pin bar bearish: long upper wick, small body, close near low
        if upper_wick > total_range * 0.6 and body_ratio < 0.3:
            signals.append(TradeSignal(
                signal_type=SignalType.CANDLESTICK_BEARISH,
                direction="short",
                ticker=ticker,
                timeframe=timeframe,
                conviction=0,
                entry_price=price,
                stop_loss=h * 1.002,
                cloud_states=cloud_states,
                metadata={"pattern": "pin_bar_bearish", "body_ratio": round(body_ratio, 3)},
            ))

        return signals
