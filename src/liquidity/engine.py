"""Liquidity Engine.

Computes bid-ask spread statistics, volume analysis, and VWAP
from market data series.
"""

import logging
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from src.liquidity.config import (
    SpreadConfig,
    VolumeConfig,
    DEFAULT_SPREAD_CONFIG,
    DEFAULT_VOLUME_CONFIG,
)
from src.liquidity.models import SpreadAnalysis, VolumeAnalysis

logger = logging.getLogger(__name__)


class LiquidityEngine:
    """Computes spread and volume liquidity metrics."""

    def __init__(
        self,
        spread_config: Optional[SpreadConfig] = None,
        volume_config: Optional[VolumeConfig] = None,
    ) -> None:
        self.spread_config = spread_config or DEFAULT_SPREAD_CONFIG
        self.volume_config = volume_config or DEFAULT_VOLUME_CONFIG

    def analyze_spread(
        self,
        bid: pd.Series,
        ask: pd.Series,
        symbol: str = "",
    ) -> SpreadAnalysis:
        """Compute bid-ask spread statistics.

        Args:
            bid: Bid price series.
            ask: Ask price series.
            symbol: Asset symbol.

        Returns:
            SpreadAnalysis with spread metrics.
        """
        n = min(len(bid), len(ask))
        if n < self.spread_config.min_observations:
            return SpreadAnalysis(symbol=symbol, n_observations=n)

        spreads = ask.values[:n] - bid.values[:n]
        mid = (ask.values[:n] + bid.values[:n]) / 2.0

        # Filter outliers
        pct_limit = np.percentile(spreads, self.spread_config.outlier_percentile)
        mask = spreads <= pct_limit
        clean_spreads = spreads[mask]
        clean_mid = mid[mask]

        if len(clean_spreads) == 0:
            return SpreadAnalysis(symbol=symbol, n_observations=n)

        avg_spread = float(np.mean(clean_spreads))
        median_spread = float(np.median(clean_spreads))
        spread_vol = float(np.std(clean_spreads, ddof=1)) if len(clean_spreads) > 1 else 0.0

        # Relative spread = spread / mid
        avg_mid = float(np.mean(clean_mid))
        relative_spread = avg_spread / avg_mid if avg_mid > 0 else 0.0

        # Effective spread (using last N observations)
        eff_window = min(self.spread_config.effective_spread_window, len(clean_spreads))
        effective_spread = float(np.mean(clean_spreads[-eff_window:]))

        return SpreadAnalysis(
            symbol=symbol,
            avg_spread=round(avg_spread, 6),
            median_spread=round(median_spread, 6),
            spread_volatility=round(spread_vol, 6),
            relative_spread=round(relative_spread, 6),
            effective_spread=round(effective_spread, 6),
            n_observations=int(len(clean_spreads)),
            date=date.today(),
        )

    def analyze_volume(
        self,
        volume: pd.Series,
        close: pd.Series,
        symbol: str = "",
    ) -> VolumeAnalysis:
        """Compute volume statistics.

        Args:
            volume: Daily volume series.
            close: Closing price series.
            symbol: Asset symbol.

        Returns:
            VolumeAnalysis with volume metrics.
        """
        n = min(len(volume), len(close))
        if n < self.volume_config.min_observations:
            return VolumeAnalysis(symbol=symbol, n_observations=n)

        vol = volume.values[:n].astype(float)
        cls = close.values[:n].astype(float)

        window = min(self.volume_config.window, n)
        recent_vol = vol[-window:]

        avg_volume = float(np.mean(recent_vol))
        median_volume = float(np.median(recent_vol))

        # Volume ratio: latest / average
        current_vol = float(vol[-1])
        volume_ratio = current_vol / avg_volume if avg_volume > 0 else 1.0

        # Dollar volume
        dollar_vol = vol * cls
        avg_dollar_volume = float(np.mean(dollar_vol[-window:]))

        # VWAP (using vwap_window days)
        vwap_window = min(self.volume_config.vwap_window, n)
        vwap_vol = vol[-vwap_window:]
        vwap_cls = cls[-vwap_window:]
        total_volume = float(np.sum(vwap_vol))
        vwap = float(np.sum(vwap_vol * vwap_cls) / total_volume) if total_volume > 0 else 0.0

        return VolumeAnalysis(
            symbol=symbol,
            avg_volume=round(avg_volume, 0),
            median_volume=round(median_volume, 0),
            volume_ratio=round(volume_ratio, 3),
            avg_dollar_volume=round(avg_dollar_volume, 0),
            vwap=round(vwap, 4),
            n_observations=n,
            date=date.today(),
        )

    def compute_vwap(
        self,
        price: pd.Series,
        volume: pd.Series,
    ) -> float:
        """Compute VWAP for a price/volume series.

        Args:
            price: Price series.
            volume: Volume series.

        Returns:
            VWAP value.
        """
        n = min(len(price), len(volume))
        if n == 0:
            return 0.0

        p = price.values[:n].astype(float)
        v = volume.values[:n].astype(float)
        total_vol = float(np.sum(v))

        if total_vol == 0:
            return 0.0

        return round(float(np.sum(p * v) / total_vol), 4)
