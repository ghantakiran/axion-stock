"""Satellite Signal Analyzer.

Processes satellite imagery signals (parking lot counts, oil storage levels,
shipping activity, construction) and normalizes against historical baselines
to detect anomalies and trends.
"""

import logging
from datetime import datetime
from typing import Optional

import numpy as np

from src.altdata.config import SatelliteConfig, SatelliteType, DEFAULT_SATELLITE_CONFIG
from src.altdata.models import SatelliteSignal

logger = logging.getLogger(__name__)


class SatelliteAnalyzer:
    """Analyzes satellite imagery signals."""

    def __init__(self, config: Optional[SatelliteConfig] = None) -> None:
        self.config = config or DEFAULT_SATELLITE_CONFIG
        self._observations: dict[str, dict[SatelliteType, list[tuple[float, datetime]]]] = {}

    def add_observation(
        self,
        symbol: str,
        sat_type: SatelliteType,
        value: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record a satellite observation."""
        ts = timestamp or datetime.now()
        if symbol not in self._observations:
            self._observations[symbol] = {}
        if sat_type not in self._observations[symbol]:
            self._observations[symbol][sat_type] = []
        self._observations[symbol][sat_type].append((value, ts))

    def analyze(
        self, symbol: str, sat_type: SatelliteType
    ) -> SatelliteSignal:
        """Analyze satellite signals for a symbol and type.

        Args:
            symbol: Stock symbol.
            sat_type: Type of satellite signal.

        Returns:
            SatelliteSignal with normalized metrics.
        """
        obs = self._observations.get(symbol, {}).get(sat_type, [])

        if len(obs) < self.config.min_observations:
            return SatelliteSignal(
                symbol=symbol, satellite_type=sat_type, raw_value=0.0,
            )

        values = np.array([v for v, _ in obs], dtype=float)
        current = values[-1]

        # Z-score normalization
        mean_val = float(np.mean(values))
        std_val = float(np.std(values))
        z_score = (current - mean_val) / std_val if std_val > 0 else 0.0

        # Normalized to 0-1 range
        min_val = float(np.min(values))
        max_val = float(np.max(values))
        normalized = (current - min_val) / (max_val - min_val) if max_val > min_val else 0.5

        # Anomaly detection
        is_anomaly = abs(z_score) >= self.config.anomaly_threshold

        # Trend via linear regression
        trend = self._compute_trend(values)

        return SatelliteSignal(
            symbol=symbol,
            satellite_type=sat_type,
            raw_value=float(current),
            normalized_value=round(normalized, 4),
            z_score=round(z_score, 4),
            is_anomaly=is_anomaly,
            trend=round(trend, 4),
            timestamp=obs[-1][1],
        )

    def analyze_all(self, symbol: str) -> list[SatelliteSignal]:
        """Analyze all satellite types for a symbol."""
        results = []
        for sat_type in self._observations.get(symbol, {}):
            results.append(self.analyze(symbol, sat_type))
        return results

    def _compute_trend(self, values: np.ndarray) -> float:
        """Compute trend as linear regression slope normalized by mean."""
        n = len(values)
        if n < self.config.trend_min_points:
            return 0.0

        x = np.arange(n, dtype=float)
        mean_x = np.mean(x)
        mean_y = np.mean(values)

        num = float(np.sum((x - mean_x) * (values - mean_y)))
        den = float(np.sum((x - mean_x) ** 2))

        if den == 0 or mean_y == 0:
            return 0.0

        slope = num / den
        return slope / abs(mean_y)

    def get_observations(
        self, symbol: str, sat_type: SatelliteType
    ) -> list[tuple[float, datetime]]:
        return self._observations.get(symbol, {}).get(sat_type, [])

    def reset(self) -> None:
        self._observations.clear()
