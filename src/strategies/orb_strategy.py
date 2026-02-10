"""PRD-177: Opening Range Breakout (ORB) Strategy.

Trades breakouts of the opening 15-minute range with volume
confirmation and a 2-hour time stop.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.ema_signals.detector import TradeSignal, SignalType


@dataclass
class ORBConfig:
    """Configuration for Opening Range Breakout strategy.

    Attributes:
        opening_range_bars: Number of bars defining the opening range.
        breakout_threshold_pct: Min % above/below range to confirm breakout.
        volume_multiplier: Min volume ratio vs average for confirmation.
        time_stop_bars: Close position after this many bars.
        risk_reward: Target risk/reward ratio.
    """

    opening_range_bars: int = 3  # 3 x 5min = 15 min opening range
    breakout_threshold_pct: float = 0.1
    volume_multiplier: float = 1.5
    time_stop_bars: int = 24  # 24 x 5min = 2 hours
    risk_reward: float = 2.0


class ORBStrategy:
    """Opening Range Breakout strategy.

    Logic:
    1. Compute the high/low of the first N bars (opening range)
    2. Long if price breaks above range high with volume
    3. Short if price breaks below range low with volume
    4. Target = range width * risk_reward from entry
    5. Stop = opposite end of the range
    """

    def __init__(self, config: ORBConfig | None = None) -> None:
        self.config = config or ORBConfig()

    @property
    def name(self) -> str:
        return "orb_breakout"

    def analyze(
        self,
        ticker: str,
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
    ) -> Optional[TradeSignal]:
        """Analyze bars for an opening range breakout."""
        n = self.config.opening_range_bars
        if len(closes) < n + 2 or len(volumes) < n + 2:
            return None

        # Opening range from first N bars
        range_high = max(highs[:n])
        range_low = min(lows[:n])
        range_width = range_high - range_low

        if range_width < 0.01:
            return None

        price = closes[-1]
        avg_vol = sum(volumes[:n]) / max(n, 1)
        current_vol = volumes[-1]
        vol_ratio = current_vol / max(avg_vol, 1)

        # Volume confirmation
        if vol_ratio < self.config.volume_multiplier:
            return None

        breakout_margin = range_width * self.config.breakout_threshold_pct / 100

        if price > range_high + breakout_margin:
            # Bullish breakout
            target = price + range_width * self.config.risk_reward
            stop = range_low
            conviction = min(90, 60 + vol_ratio * 5 + ((price - range_high) / range_width) * 20)
            return TradeSignal(
                ticker=ticker,
                direction="long",
                signal_type=SignalType.CLOUD_CROSS_BULLISH,
                entry_price=price,
                stop_loss=stop,
                target_price=target,
                conviction=conviction,
                timeframe="5m",
                timestamp=datetime.now(timezone.utc),
            )

        if price < range_low - breakout_margin:
            # Bearish breakout
            target = price - range_width * self.config.risk_reward
            stop = range_high
            conviction = min(90, 60 + vol_ratio * 5 + ((range_low - price) / range_width) * 20)
            return TradeSignal(
                ticker=ticker,
                direction="short",
                signal_type=SignalType.CLOUD_CROSS_BEARISH,
                entry_price=price,
                stop_loss=stop,
                target_price=target,
                conviction=conviction,
                timeframe="5m",
                timestamp=datetime.now(timezone.utc),
            )

        return None
