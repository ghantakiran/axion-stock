"""Qullamaggie Breakout Strategy — flag/consolidation breakout after a prior move.

Core pattern: stock makes a big move (30%+ in 1-3 months), consolidates
in a tight flag with volume contraction, then breaks out on high volume.
Stop at the low of day, trail with 10/20 SMA.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.ema_signals.detector import TradeSignal, SignalType
from src.qullamaggie.config import BreakoutConfig
from src.qullamaggie.indicators import (
    compute_adr,
    compute_atr,
    compute_sma,
    detect_consolidation,
    volume_contraction,
)


class QullamaggieBreakoutStrategy:
    """Qullamaggie breakout (flag pattern) strategy.

    Entry criteria:
      1. Prior move: >= 30% gain within a 1-3 month window.
      2. Consolidation: 2-8 weeks of tight, low-volume, higher-lows action.
      3. Breakout: Price closes above consolidation high on >= 1.5x avg volume.

    Exit: Trail with 10 or 20 SMA. Stop at low of day, capped at 1x ATR.
    """

    def __init__(self, config: BreakoutConfig | None = None) -> None:
        self.config = config or BreakoutConfig()

    @property
    def name(self) -> str:
        return "qullamaggie_breakout"

    def analyze(
        self,
        ticker: str,
        opens: list[float],
        highs: list[float],
        lows: list[float],
        closes: list[float],
        volumes: list[float],
    ) -> Optional[TradeSignal]:
        """Analyze OHLCV data for a breakout setup.

        Args:
            ticker: Symbol to analyze.
            opens: Open prices.
            highs: High prices.
            lows: Low prices.
            closes: Close prices.
            volumes: Volume data.

        Returns:
            TradeSignal if breakout detected, None otherwise.
        """
        cfg = self.config
        n = len(closes)

        # 1. Minimum data check
        min_bars = cfg.consolidation_max_bars + 7
        if n < min_bars:
            return None

        # 2. Price and volume filters
        price = closes[-1]
        if price < cfg.price_min:
            return None

        avg_vol = sum(volumes[-20:]) / max(len(volumes[-20:]), 1)
        if avg_vol < cfg.avg_volume_min:
            return None

        # 3. ADR filter
        adr = compute_adr(highs, lows, period=20)
        if adr < cfg.adr_min_pct:
            return None

        # 4. Prior move detection (look for >= prior_gain_pct in last 3 months)
        prior_gain = self._detect_prior_move(closes, n)
        if prior_gain < cfg.prior_gain_pct:
            return None

        # 5. Consolidation detection
        consolidation = detect_consolidation(highs, lows, closes, cfg)
        if consolidation is None or not consolidation.detected:
            return None

        # 6. Volume contraction during consolidation
        if consolidation.start_idx < n and consolidation.end_idx < n:
            cons_vols = volumes[consolidation.start_idx: consolidation.end_idx + 1]
            if cons_vols:
                cons_avg = sum(cons_vols) / len(cons_vols)
                vol_ratio = cons_avg / max(avg_vol, 1)
                consolidation.volume_ratio = vol_ratio
                if vol_ratio > cfg.volume_contraction_ratio:
                    return None

        # 7. Breakout confirmation
        breakout_high = consolidation.high
        if price <= breakout_high:
            return None

        current_vol = volumes[-1] if volumes else 0
        vol_mult = current_vol / max(avg_vol, 1)
        if vol_mult < cfg.breakout_volume_mult:
            return None

        # 8. Stop loss: low of day, capped at 1x ATR
        atr = compute_atr(highs, lows, closes, period=14)
        stop_lod = lows[-1]
        stop_atr = price - (atr * cfg.stop_atr_mult)
        stop = max(stop_lod, stop_atr)

        # 9. Target: 2x risk from entry
        risk = price - stop
        target = price + risk * 2 if risk > 0 else price * 1.05

        # 10. Conviction scoring
        conviction = self._score_conviction(
            vol_mult, adr, consolidation, prior_gain, cfg
        )

        # SMA trail info in metadata
        sma_10 = compute_sma(closes, 10)
        sma_20 = compute_sma(closes, 20)

        return TradeSignal(
            ticker=ticker,
            direction="long",
            signal_type=SignalType.TREND_ALIGNED_LONG,
            entry_price=price,
            stop_loss=stop,
            target_price=target,
            conviction=conviction,
            timeframe="1d",
            timestamp=datetime.now(timezone.utc),
            metadata={
                "strategy": self.name,
                "prior_gain_pct": round(prior_gain, 1),
                "consolidation_bars": consolidation.duration,
                "consolidation_range_pct": round(consolidation.range_pct, 1),
                "breakout_volume_mult": round(vol_mult, 1),
                "adr_pct": round(adr, 1),
                "trail_sma_10": round(sma_10[-1], 2) if sma_10 else None,
                "trail_sma_20": round(sma_20[-1], 2) if sma_20 else None,
                "higher_lows": consolidation.has_higher_lows,
            },
        )

    def _detect_prior_move(self, closes: list[float], n: int) -> float:
        """Detect the maximum gain in the prior 1-3 month window.

        Scans backwards from the start of potential consolidation
        to find the largest rally.
        """
        lookback = min(n, 67)  # ~3 months of daily bars
        window = closes[max(0, n - lookback): n]
        if len(window) < 5:
            return 0.0
        min_price = min(window)
        max_price = max(window)
        if min_price <= 0:
            return 0.0
        return (max_price - min_price) / min_price * 100

    @staticmethod
    def _score_conviction(
        vol_mult: float,
        adr: float,
        consolidation,
        prior_gain: float,
        cfg,
    ) -> int:
        """Score conviction 60-90 based on quality factors."""
        score = 60

        # Volume bonus: up to +10 for strong volume
        vol_bonus = min(10, (vol_mult - cfg.breakout_volume_mult) * 5)
        score += max(0, int(vol_bonus))

        # ADR bonus: up to +5 for volatile stocks
        if adr > 8:
            score += 5
        elif adr > 6:
            score += 3

        # Consolidation tightness: up to +10
        if consolidation.range_pct < 10:
            score += 10
        elif consolidation.range_pct < 15:
            score += 5

        # Higher lows bonus
        if consolidation.has_higher_lows:
            score += 5

        return min(90, score)
