"""Yield Curve Analysis.

Computes term spreads, classifies curve shape, detects
inversions, and fits Nelson-Siegel model parameters.
"""

import logging
import math
from typing import Optional

import numpy as np

from src.macro.config import YieldCurveConfig, CurveShape, DEFAULT_YIELDCURVE_CONFIG
from src.macro.models import YieldCurveSnapshot

logger = logging.getLogger(__name__)

# Tenor to years mapping
TENOR_YEARS = {
    "1M": 1 / 12, "3M": 0.25, "6M": 0.5,
    "1Y": 1, "2Y": 2, "3Y": 3, "5Y": 5,
    "7Y": 7, "10Y": 10, "20Y": 20, "30Y": 30,
}


class YieldCurveAnalyzer:
    """Analyzes yield curve shape and dynamics."""

    def __init__(self, config: Optional[YieldCurveConfig] = None) -> None:
        self.config = config or DEFAULT_YIELDCURVE_CONFIG
        self._history: list[YieldCurveSnapshot] = []

    def analyze(
        self, rates: dict[str, float], date: str = ""
    ) -> YieldCurveSnapshot:
        """Analyze a yield curve.

        Args:
            rates: Dict of tenor -> yield (e.g., {"2Y": 4.25, "10Y": 4.50}).
            date: Date string.

        Returns:
            YieldCurveSnapshot with shape and metrics.
        """
        if not rates:
            return YieldCurveSnapshot(date=date, rates={})

        # Term spread
        short_key = self.config.key_spread_short
        long_key = self.config.key_spread_long
        short_rate = rates.get(short_key, 0)
        long_rate = rates.get(long_key, 0)
        term_spread = long_rate - short_rate

        # Classify shape
        shape = self._classify_shape(rates, term_spread)

        # Inversion detection
        is_inverted, inversion_depth = self._detect_inversion(rates)

        # Nelson-Siegel fit
        level, slope, curvature = self._fit_nelson_siegel(rates)

        snapshot = YieldCurveSnapshot(
            date=date,
            rates=rates,
            shape=shape,
            term_spread=round(term_spread, 4),
            slope=round(slope, 4),
            curvature=round(curvature, 4),
            level=round(level, 4),
            is_inverted=is_inverted,
            inversion_depth=round(inversion_depth, 4),
        )

        self._history.append(snapshot)
        return snapshot

    def _classify_shape(
        self, rates: dict[str, float], term_spread: float
    ) -> CurveShape:
        """Classify yield curve shape."""
        if term_spread < self.config.inversion_threshold:
            return CurveShape.INVERTED
        if abs(term_spread) <= self.config.flat_threshold:
            return CurveShape.FLAT

        # Check for hump: mid-tenor higher than both short and long
        tenors_sorted = sorted(
            [(TENOR_YEARS.get(t, 0), r) for t, r in rates.items()],
            key=lambda x: x[0],
        )
        if len(tenors_sorted) >= 3:
            short_r = tenors_sorted[0][1]
            mid_idx = len(tenors_sorted) // 2
            mid_r = tenors_sorted[mid_idx][1]
            long_r = tenors_sorted[-1][1]

            if mid_r > short_r + 0.1 and mid_r > long_r + 0.1:
                return CurveShape.HUMPED

        return CurveShape.NORMAL

    def _detect_inversion(
        self, rates: dict[str, float]
    ) -> tuple[bool, float]:
        """Detect yield curve inversion.

        Returns (is_inverted, max_inversion_depth).
        """
        tenors_sorted = sorted(
            [(TENOR_YEARS.get(t, 0), r) for t, r in rates.items()],
            key=lambda x: x[0],
        )

        max_inversion = 0.0
        is_inverted = False

        for i in range(len(tenors_sorted) - 1):
            spread = tenors_sorted[i + 1][1] - tenors_sorted[i][1]
            if spread < -abs(self.config.inversion_threshold):
                is_inverted = True
                max_inversion = min(max_inversion, spread)

        return is_inverted, max_inversion

    def _fit_nelson_siegel(
        self, rates: dict[str, float]
    ) -> tuple[float, float, float]:
        """Fit Nelson-Siegel model: y(t) = b0 + b1*(1-e^(-t/tau))/(t/tau) + b2*((1-e^(-t/tau))/(t/tau) - e^(-t/tau))

        Simplified approach using least-squares with fixed tau.

        Returns:
            (level, slope, curvature) parameters.
        """
        if len(rates) < 3:
            vals = list(rates.values())
            if len(vals) >= 2:
                return float(np.mean(vals)), vals[-1] - vals[0], 0.0
            elif len(vals) == 1:
                return vals[0], 0.0, 0.0
            return 0.0, 0.0, 0.0

        # Prepare data
        maturities = []
        yields = []
        for tenor, rate in rates.items():
            t = TENOR_YEARS.get(tenor, 0)
            if t > 0:
                maturities.append(t)
                yields.append(rate)

        if len(maturities) < 3:
            return float(np.mean(yields)), yields[-1] - yields[0], 0.0

        tau = 2.0  # fixed decay parameter
        t_arr = np.array(maturities)
        y_arr = np.array(yields)

        # Nelson-Siegel basis functions
        x1 = np.ones_like(t_arr)  # level
        exp_term = np.exp(-t_arr / tau)
        ratio = (1 - exp_term) / (t_arr / tau)
        x2 = ratio  # slope
        x3 = ratio - exp_term  # curvature

        # Least squares: y = X @ beta
        X = np.column_stack([x1, x2, x3])
        try:
            beta, _, _, _ = np.linalg.lstsq(X, y_arr, rcond=None)
            return float(beta[0]), float(beta[1]), float(beta[2])
        except np.linalg.LinAlgError:
            return float(np.mean(y_arr)), 0.0, 0.0

    def get_history(self) -> list[YieldCurveSnapshot]:
        return self._history

    def reset(self) -> None:
        self._history.clear()
