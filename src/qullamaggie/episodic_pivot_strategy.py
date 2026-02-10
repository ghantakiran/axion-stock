"""Qullamaggie Episodic Pivot Strategy — gap-up from a flat base.

Core pattern: a stock that has been flat (boring, no-one cares) gaps up
10%+ on a catalyst (earnings, FDA, contract) with massive volume (2x+).
Entry above opening range high, stop at low of the gap day.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from src.ema_signals.detector import TradeSignal, SignalType
from src.qullamaggie.config import EpisodicPivotConfig
from src.qullamaggie.indicators import compute_adr


class EpisodicPivotStrategy:
    """Qullamaggie Episodic Pivot (EP) strategy.

    Entry criteria:
      1. Gap-up: open[-1] vs close[-2] >= 10%.
      2. Volume: day's volume >= 2x 20-day average.
      3. Prior flatness: range of prior 60 bars <= 30%.
      4. ADR >= 3.5% (stock is volatile enough).

    Exit: Trail with 10/20 EMA. Stop at low of the gap day.
    """

    def __init__(self, config: EpisodicPivotConfig | None = None) -> None:
        self.config = config or EpisodicPivotConfig()

    @property
    def name(self) -> str:
        return "qullamaggie_ep"

    def analyze(
        self,
        ticker: str,
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
    ) -> Optional[TradeSignal]:
        """Analyze OHLCV data for an episodic pivot setup.

        Args:
            ticker: Symbol to analyze.
            opens: Open prices.
            highs: High prices.
            lows: Low prices.
            closes: Close prices.
            volumes: Volume data.

        Returns:
            TradeSignal if EP detected, None otherwise.
        """
        cfg = self.config
        n = len(closes)
        min_bars = cfg.prior_flat_bars + 2

        if n < min_bars:
            return None

        # 1. Gap-up detection: today's open vs yesterday's close
        gap_pct = (opens[-1] - closes[-2]) / closes[-2] * 100 if closes[-2] > 0 else 0
        if gap_pct < cfg.gap_min_pct:
            return None

        # 2. Volume confirmation
        avg_vol = sum(volumes[-21:-1]) / max(len(volumes[-21:-1]), 1)
        current_vol = volumes[-1]
        vol_mult = current_vol / max(avg_vol, 1)
        if vol_mult < cfg.volume_mult_min:
            return None

        # 3. Prior flatness: price range of prior N bars (before the gap day)
        prior_closes = closes[-(cfg.prior_flat_bars + 1): -1]
        if prior_closes:
            prior_high = max(prior_closes)
            prior_low = min(prior_closes)
            if prior_low > 0:
                prior_range_pct = (prior_high - prior_low) / prior_low * 100
                if prior_range_pct > cfg.prior_flat_max_range_pct:
                    return None
            else:
                return None
        else:
            return None

        # 4. ADR filter
        adr = compute_adr(highs, lows, period=20)
        if adr < cfg.adr_min_pct:
            return None

        # 5. Entry: opening range high (high of the gap day)
        entry = highs[-1]

        # 6. Stop: low of the gap day
        stop = lows[-1]

        # 7. Target: 2x risk from entry
        risk = entry - stop
        target = entry + risk * 2 if risk > 0 else entry * 1.10

        # 8. Conviction scoring
        conviction = self._score_conviction(gap_pct, vol_mult, prior_range_pct, adr)

        return TradeSignal(
            ticker=ticker,
            direction="long",
            signal_type=SignalType.CLOUD_CROSS_BULLISH,
            entry_price=entry,
            stop_loss=stop,
            target_price=target,
            conviction=conviction,
            timeframe="1d",
            timestamp=datetime.now(timezone.utc),
            metadata={
                "strategy": self.name,
                "gap_pct": round(gap_pct, 1),
                "volume_mult": round(vol_mult, 1),
                "prior_range_pct": round(prior_range_pct, 1),
                "adr_pct": round(adr, 1),
            },
        )

    @staticmethod
    def _score_conviction(
        gap_pct: float, vol_mult: float, flatness: float, adr: float
    ) -> int:
        """Score conviction 55-90 based on quality factors."""
        score = 55

        # Gap size bonus: +5 per 5% above minimum
        gap_bonus = min(15, int((gap_pct - 10) / 5) * 5)
        score += max(0, gap_bonus)

        # Volume bonus: +5 per 1x above minimum
        vol_bonus = min(10, int(vol_mult - 2) * 5)
        score += max(0, vol_bonus)

        # Flatness bonus: flatter base = better EP
        if flatness < 15:
            score += 5
        elif flatness < 20:
            score += 3

        # ADR bonus
        if adr > 6:
            score += 5

        return min(90, score)
