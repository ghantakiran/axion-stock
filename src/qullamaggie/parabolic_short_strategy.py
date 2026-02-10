"""Qullamaggie Parabolic Short Strategy — shorting vertical exhaustion moves.

Core pattern: a stock surges 100%+ in under 20 bars (parabolic move),
shows consecutive green days (3+), then prints a first red candle or
fails at VWAP. Short at the close of the exhaustion bar, stop at HOD,
target the 10 or 20 SMA.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.ema_signals.detector import TradeSignal, SignalType
from src.qullamaggie.config import ParabolicShortConfig
from src.qullamaggie.indicators import compute_sma, compute_vwap


class ParabolicShortStrategy:
    """Qullamaggie Parabolic Short strategy.

    Entry criteria:
      1. Surge: price up >= 100% within 20 bars.
      2. Consecutive up days: >= 3 green candles in a row.
      3. Exhaustion: first red candle OR close below VWAP.
      4. Short entry at close of the exhaustion bar.

    Exit: Cover at 10/20 SMA. Stop at high of day.
    """

    def __init__(self, config: ParabolicShortConfig | None = None) -> None:
        self.config = config or ParabolicShortConfig()

    @property
    def name(self) -> str:
        return "qullamaggie_parabolic_short"

    def analyze(
        self,
        ticker: str,
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
    ) -> Optional[TradeSignal]:
        """Analyze OHLCV data for a parabolic short setup.

        Args:
            ticker: Symbol to analyze.
            opens: Open prices.
            highs: High prices.
            lows: Low prices.
            closes: Close prices.
            volumes: Volume data.

        Returns:
            TradeSignal if parabolic exhaustion detected, None otherwise.
        """
        cfg = self.config
        n = len(closes)
        min_bars = cfg.surge_max_bars + 5

        if n < min_bars:
            return None

        # 1. Surge detection: price up >= surge_min_pct in last surge_max_bars
        surge_window = closes[-(cfg.surge_max_bars + 1):]
        surge_low = min(surge_window[:-1]) if len(surge_window) > 1 else surge_window[0]
        surge_high = max(closes[-cfg.surge_max_bars:])

        if surge_low <= 0:
            return None
        surge_pct = (surge_high - surge_low) / surge_low * 100
        if surge_pct < cfg.surge_min_pct:
            return None

        # 2. Consecutive up days
        up_days = self._count_consecutive_up(closes)
        if up_days < cfg.consecutive_up_days:
            return None

        # 3. Exhaustion detection: first red candle
        is_red = closes[-1] < opens[-1]

        # Or VWAP failure (close below VWAP)
        vwap = compute_vwap(highs[-20:], lows[-20:], closes[-20:], volumes[-20:])
        below_vwap = closes[-1] < vwap if cfg.vwap_entry else False

        if not is_red and not below_vwap:
            return None

        # 4. Short entry at close of exhaustion bar
        entry = closes[-1]

        # 5. Stop: high of day
        stop = highs[-1] if cfg.stop_at_hod else max(highs[-3:])

        # 6. Target: 10/20 SMA
        sma = compute_sma(closes, cfg.target_sma_period)
        target = sma[-1] if sma else entry * 0.85

        # Ensure target is below entry for a short
        if target >= entry:
            target = entry * 0.90

        # 7. Conviction scoring
        conviction = self._score_conviction(surge_pct, up_days, is_red, below_vwap)

        return TradeSignal(
            ticker=ticker,
            direction="short",
            signal_type=SignalType.MOMENTUM_EXHAUSTION,
            entry_price=entry,
            stop_loss=stop,
            target_price=target,
            conviction=conviction,
            timeframe="1d",
            timestamp=datetime.now(timezone.utc),
            metadata={
                "strategy": self.name,
                "surge_pct": round(surge_pct, 1),
                "consecutive_up_days": up_days,
                "is_red_candle": is_red,
                "below_vwap": below_vwap,
                "vwap": round(vwap, 2),
                "target_sma": cfg.target_sma_period,
            },
        )

    @staticmethod
    def _count_consecutive_up(closes: list[float]) -> int:
        """Count consecutive up (green) days ending at the second-to-last bar.

        We check bars before the current one, since the current bar is the
        potential exhaustion/reversal bar.
        """
        if len(closes) < 3:
            return 0
        count = 0
        # Count from the bar before last going backwards
        for i in range(len(closes) - 2, 0, -1):
            if closes[i] > closes[i - 1]:
                count += 1
            else:
                break
        return count

    @staticmethod
    def _score_conviction(
        surge_pct: float, up_days: int, is_red: bool, below_vwap: bool
    ) -> int:
        """Score conviction 55-90 based on exhaustion quality."""
        score = 55

        # Surge magnitude bonus
        if surge_pct > 200:
            score += 10
        elif surge_pct > 150:
            score += 5

        # Consecutive up days bonus
        if up_days >= 5:
            score += 10
        elif up_days >= 4:
            score += 5

        # Red candle confirmation
        if is_red:
            score += 5

        # VWAP failure confirmation
        if below_vwap:
            score += 5

        return min(90, score)
