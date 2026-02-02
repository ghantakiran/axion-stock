"""Dark Pool Volume Tracking.

Tracks dark pool vs lit exchange volume, computes market
share, trend analysis, and short volume ratios.
"""

import logging
from typing import Optional

import numpy as np

from src.darkpool.config import VolumeConfig, DEFAULT_VOLUME_CONFIG
from src.darkpool.models import DarkPoolVolume, VolumeSummary

logger = logging.getLogger(__name__)


class VolumeTracker:
    """Tracks dark pool volume and market share."""

    def __init__(self, config: Optional[VolumeConfig] = None) -> None:
        self.config = config or DEFAULT_VOLUME_CONFIG
        self._history: dict[str, list[DarkPoolVolume]] = {}

    def add_record(self, record: DarkPoolVolume) -> None:
        """Add a volume record."""
        if record.symbol not in self._history:
            self._history[record.symbol] = []
        self._history[record.symbol].append(record)

    def add_records(self, records: list[DarkPoolVolume]) -> None:
        """Add multiple volume records."""
        for r in records:
            self.add_record(r)

    def summarize(self, symbol: str) -> VolumeSummary:
        """Compute volume summary for a symbol.

        Args:
            symbol: Stock symbol.

        Returns:
            VolumeSummary with aggregated dark pool metrics.
        """
        records = self._history.get(symbol, [])
        if not records:
            return self._empty_summary(symbol)

        recent = records[-self.config.lookback_days:]
        n = len(recent)

        dark_vols = np.array([r.dark_volume for r in recent])
        lit_vols = np.array([r.lit_volume for r in recent])
        total_vols = np.array([r.total_volume for r in recent])
        short_vols = np.array([r.short_volume for r in recent])

        # Dark share per day
        valid = total_vols > 0
        if np.any(valid):
            dark_shares = np.where(valid, dark_vols / total_vols, 0)
            avg_dark_share = float(np.mean(dark_shares[valid]))
        else:
            avg_dark_share = 0.0

        # Dark share trend (momentum)
        trend = self._compute_trend(dark_shares[valid]) if np.any(valid) else 0.0

        # Short ratio
        dark_total = float(np.sum(dark_vols))
        if dark_total > 0:
            avg_short_ratio = float(np.sum(short_vols)) / dark_total
        else:
            avg_short_ratio = 0.0

        is_elevated = avg_dark_share >= self.config.dark_share_warning

        return VolumeSummary(
            symbol=symbol,
            avg_dark_share=round(avg_dark_share, 4),
            dark_share_trend=round(trend, 4),
            total_dark_volume=round(float(np.sum(dark_vols)), 2),
            total_lit_volume=round(float(np.sum(lit_vols)), 2),
            avg_short_ratio=round(avg_short_ratio, 4),
            n_days=n,
            is_elevated=is_elevated,
        )

    def _compute_trend(self, dark_shares: np.ndarray) -> float:
        """Compute dark share trend using linear regression slope."""
        n = len(dark_shares)
        if n < 2:
            return 0.0

        x = np.arange(n, dtype=float)
        x_mean = np.mean(x)
        y_mean = np.mean(dark_shares)

        num = np.sum((x - x_mean) * (dark_shares - y_mean))
        den = np.sum((x - x_mean) ** 2)

        if den == 0:
            return 0.0
        return float(num / den)

    def get_history(self, symbol: str) -> list[DarkPoolVolume]:
        """Get volume history for a symbol."""
        return self._history.get(symbol, [])

    def reset(self) -> None:
        """Clear all history."""
        self._history.clear()

    def _empty_summary(self, symbol: str) -> VolumeSummary:
        return VolumeSummary(
            symbol=symbol,
            avg_dark_share=0.0,
            dark_share_trend=0.0,
            total_dark_volume=0.0,
            total_lit_volume=0.0,
            avg_short_ratio=0.0,
        )
