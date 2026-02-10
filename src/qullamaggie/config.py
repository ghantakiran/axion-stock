"""Qullamaggie strategy configuration dataclasses.

Each setup has its own config with sensible defaults derived from
Kristjan Kullamagi's documented trading rules.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BreakoutConfig:
    """Configuration for the Qullamaggie Breakout (flag/consolidation) setup.

    Attributes:
        prior_gain_pct: Minimum % gain in the prior move (1-3 months).
        consolidation_min_bars: Minimum consolidation duration (bars).
        consolidation_max_bars: Maximum consolidation duration (bars).
        pullback_max_pct: Max pullback from the high during consolidation.
        volume_contraction_ratio: Volume must contract below this ratio of avg.
        breakout_volume_mult: Volume on breakout day must exceed avg * this.
        adr_min_pct: Minimum Average Daily Range %.
        stop_atr_mult: Stop loss distance in ATR multiples.
        risk_per_trade: Risk per trade as fraction of equity.
        max_position_pct: Maximum position size as fraction of equity.
        price_min: Minimum share price.
        avg_volume_min: Minimum 20-day average volume.
    """

    prior_gain_pct: float = 30.0
    consolidation_min_bars: int = 10
    consolidation_max_bars: int = 60
    pullback_max_pct: float = 25.0
    volume_contraction_ratio: float = 0.7
    breakout_volume_mult: float = 1.5
    adr_min_pct: float = 5.0
    stop_atr_mult: float = 1.0
    risk_per_trade: float = 0.005
    max_position_pct: float = 0.20
    price_min: float = 5.0
    avg_volume_min: int = 300_000


@dataclass
class EpisodicPivotConfig:
    """Configuration for the Episodic Pivot (EP) setup.

    Attributes:
        gap_min_pct: Minimum gap-up percentage on catalyst day.
        volume_mult_min: Volume on gap day must be >= avg * this.
        prior_flat_bars: Lookback for flatness check (bars).
        prior_flat_max_range_pct: Max price range % over prior_flat_bars.
        adr_min_pct: Minimum ADR %.
        stop_at_lod: Place stop at low of the gap day.
        risk_per_trade: Risk per trade as fraction of equity.
        earnings_only: If True, only trigger on earnings catalysts.
    """

    gap_min_pct: float = 10.0
    volume_mult_min: float = 2.0
    prior_flat_bars: int = 60
    prior_flat_max_range_pct: float = 30.0
    adr_min_pct: float = 3.5
    stop_at_lod: bool = True
    risk_per_trade: float = 0.005
    earnings_only: bool = False


@dataclass
class ParabolicShortConfig:
    """Configuration for the Parabolic Short setup.

    Attributes:
        surge_min_pct: Minimum % surge to qualify (small caps).
        surge_max_bars: Maximum bars for the surge window.
        consecutive_up_days: Minimum consecutive green candles.
        vwap_entry: Use VWAP rejection as entry trigger.
        stop_at_hod: Place stop at high of the exhaustion day.
        target_sma_period: Target the N-period SMA for profit-taking.
        risk_per_trade: Risk per trade as fraction of equity.
    """

    surge_min_pct: float = 100.0
    surge_max_bars: int = 20
    consecutive_up_days: int = 3
    vwap_entry: bool = True
    stop_at_hod: bool = True
    target_sma_period: int = 20
    risk_per_trade: float = 0.005
