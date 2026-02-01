"""Chart Pattern Detection.

Detects common chart patterns: double top/bottom, head and shoulders,
triangles, flags, and wedges from OHLC price data.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.charting.config import (
    PatternConfig,
    PatternType,
    DEFAULT_PATTERN_CONFIG,
)
from src.charting.models import ChartPattern

logger = logging.getLogger(__name__)


class PatternDetector:
    """Detects chart patterns in price data."""

    def __init__(self, config: Optional[PatternConfig] = None) -> None:
        self.config = config or DEFAULT_PATTERN_CONFIG

    def detect_all(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        symbol: str = "",
    ) -> list[ChartPattern]:
        """Run all pattern detectors.

        Args:
            high: High prices.
            low: Low prices.
            close: Close prices.
            symbol: Asset symbol.

        Returns:
            List of detected patterns sorted by confidence.
        """
        patterns: list[ChartPattern] = []
        patterns.extend(self.detect_double_top(high, close, symbol=symbol))
        patterns.extend(self.detect_double_bottom(low, close, symbol=symbol))
        patterns.extend(self.detect_head_and_shoulders(high, low, close, symbol=symbol))
        patterns.extend(self.detect_triangle(high, low, close, symbol=symbol))
        patterns.sort(key=lambda p: p.confidence, reverse=True)
        return patterns

    def detect_double_top(
        self,
        high: pd.Series,
        close: pd.Series,
        symbol: str = "",
    ) -> list[ChartPattern]:
        """Detect double top patterns.

        Two peaks at roughly the same level with a trough between them.
        """
        patterns: list[ChartPattern] = []
        n = len(high)
        if n < self.config.min_pattern_bars:
            return patterns

        highs = high.values
        closes = close.values
        peaks = self._find_peaks(highs, order=5)

        for i in range(len(peaks) - 1):
            p1_idx = peaks[i]
            p2_idx = peaks[i + 1]

            span = p2_idx - p1_idx
            if span < self.config.min_pattern_bars // 2:
                continue
            if span > self.config.max_pattern_bars:
                continue

            p1_val = highs[p1_idx]
            p2_val = highs[p2_idx]

            # Peaks should be within tolerance
            if abs(p2_val - p1_val) / p1_val > self.config.price_tolerance:
                continue

            # Find trough between peaks
            trough_slice = closes[p1_idx:p2_idx + 1]
            trough_val = float(np.min(trough_slice))
            neckline = trough_val

            # Pattern height -> target
            height = ((p1_val + p2_val) / 2) - neckline
            target = neckline - height

            # Confidence based on symmetry
            symmetry = 1.0 - abs(p2_val - p1_val) / p1_val / self.config.price_tolerance
            confidence = round(max(0.0, min(1.0, symmetry * 0.8)), 3)

            if confidence < self.config.min_confidence:
                continue

            # Confirmed if price breaks below neckline
            confirmed = False
            if p2_idx + self.config.confirmation_bars < n:
                post = closes[p2_idx:p2_idx + self.config.confirmation_bars + 1]
                if any(v < neckline for v in post):
                    confirmed = True

            patterns.append(ChartPattern(
                pattern_type=PatternType.DOUBLE_TOP,
                start_idx=p1_idx,
                end_idx=p2_idx,
                neckline=round(neckline, 4),
                target_price=round(target, 4),
                confidence=confidence,
                confirmed=confirmed,
                symbol=symbol,
            ))

        return patterns

    def detect_double_bottom(
        self,
        low: pd.Series,
        close: pd.Series,
        symbol: str = "",
    ) -> list[ChartPattern]:
        """Detect double bottom patterns.

        Two troughs at roughly the same level with a peak between them.
        """
        patterns: list[ChartPattern] = []
        n = len(low)
        if n < self.config.min_pattern_bars:
            return patterns

        lows = low.values
        closes = close.values
        troughs = self._find_troughs(lows, order=5)

        for i in range(len(troughs) - 1):
            t1_idx = troughs[i]
            t2_idx = troughs[i + 1]

            span = t2_idx - t1_idx
            if span < self.config.min_pattern_bars // 2:
                continue
            if span > self.config.max_pattern_bars:
                continue

            t1_val = lows[t1_idx]
            t2_val = lows[t2_idx]

            if abs(t2_val - t1_val) / t1_val > self.config.price_tolerance:
                continue

            # Find peak between troughs
            peak_slice = closes[t1_idx:t2_idx + 1]
            peak_val = float(np.max(peak_slice))
            neckline = peak_val

            height = neckline - ((t1_val + t2_val) / 2)
            target = neckline + height

            symmetry = 1.0 - abs(t2_val - t1_val) / t1_val / self.config.price_tolerance
            confidence = round(max(0.0, min(1.0, symmetry * 0.8)), 3)

            if confidence < self.config.min_confidence:
                continue

            confirmed = False
            if t2_idx + self.config.confirmation_bars < n:
                post = closes[t2_idx:t2_idx + self.config.confirmation_bars + 1]
                if any(v > neckline for v in post):
                    confirmed = True

            patterns.append(ChartPattern(
                pattern_type=PatternType.DOUBLE_BOTTOM,
                start_idx=t1_idx,
                end_idx=t2_idx,
                neckline=round(neckline, 4),
                target_price=round(target, 4),
                confidence=confidence,
                confirmed=confirmed,
                symbol=symbol,
            ))

        return patterns

    def detect_head_and_shoulders(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        symbol: str = "",
    ) -> list[ChartPattern]:
        """Detect head and shoulders and inverse patterns."""
        patterns: list[ChartPattern] = []
        n = len(high)
        if n < self.config.min_pattern_bars:
            return patterns

        highs = high.values
        lows = low.values

        # Regular H&S (bearish) — three peaks, middle is highest
        peaks = self._find_peaks(highs, order=5)
        for i in range(len(peaks) - 2):
            l_idx, h_idx, r_idx = peaks[i], peaks[i + 1], peaks[i + 2]

            span = r_idx - l_idx
            if span < self.config.min_pattern_bars:
                continue
            if span > self.config.max_pattern_bars:
                continue

            l_val, h_val, r_val = highs[l_idx], highs[h_idx], highs[r_idx]

            # Head must be highest
            if h_val <= l_val or h_val <= r_val:
                continue

            # Shoulders roughly symmetric
            shoulder_diff = abs(r_val - l_val) / l_val
            if shoulder_diff > self.config.price_tolerance * 2:
                continue

            # Neckline from troughs between peaks
            t1 = float(np.min(lows[l_idx:h_idx + 1]))
            t2 = float(np.min(lows[h_idx:r_idx + 1]))
            neckline = (t1 + t2) / 2

            height = h_val - neckline
            target = neckline - height

            symmetry = 1.0 - shoulder_diff / (self.config.price_tolerance * 2)
            confidence = round(max(0.0, min(1.0, symmetry * 0.75)), 3)

            if confidence < self.config.min_confidence:
                continue

            patterns.append(ChartPattern(
                pattern_type=PatternType.HEAD_AND_SHOULDERS,
                start_idx=l_idx,
                end_idx=r_idx,
                neckline=round(neckline, 4),
                target_price=round(target, 4),
                confidence=confidence,
                symbol=symbol,
            ))

        # Inverse H&S (bullish) — three troughs, middle is lowest
        troughs = self._find_troughs(lows, order=5)
        for i in range(len(troughs) - 2):
            l_idx, h_idx, r_idx = troughs[i], troughs[i + 1], troughs[i + 2]

            span = r_idx - l_idx
            if span < self.config.min_pattern_bars:
                continue
            if span > self.config.max_pattern_bars:
                continue

            l_val, h_val, r_val = lows[l_idx], lows[h_idx], lows[r_idx]

            if h_val >= l_val or h_val >= r_val:
                continue

            shoulder_diff = abs(r_val - l_val) / l_val
            if shoulder_diff > self.config.price_tolerance * 2:
                continue

            t1 = float(np.max(highs[l_idx:h_idx + 1]))
            t2 = float(np.max(highs[h_idx:r_idx + 1]))
            neckline = (t1 + t2) / 2

            height = neckline - h_val
            target = neckline + height

            symmetry = 1.0 - shoulder_diff / (self.config.price_tolerance * 2)
            confidence = round(max(0.0, min(1.0, symmetry * 0.75)), 3)

            if confidence < self.config.min_confidence:
                continue

            patterns.append(ChartPattern(
                pattern_type=PatternType.INVERSE_HEAD_AND_SHOULDERS,
                start_idx=l_idx,
                end_idx=r_idx,
                neckline=round(neckline, 4),
                target_price=round(target, 4),
                confidence=confidence,
                symbol=symbol,
            ))

        return patterns

    def detect_triangle(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        symbol: str = "",
    ) -> list[ChartPattern]:
        """Detect ascending and descending triangle patterns."""
        patterns: list[ChartPattern] = []
        n = len(high)
        window = min(self.config.max_pattern_bars, n)
        if window < self.config.min_pattern_bars:
            return patterns

        highs = high.values[-window:]
        lows = low.values[-window:]
        offset = n - window

        peaks = self._find_peaks(highs, order=3)
        troughs = self._find_troughs(lows, order=3)

        if len(peaks) < 2 or len(troughs) < 2:
            return patterns

        # Ascending triangle: flat resistance, rising support
        resistance_vals = [highs[p] for p in peaks[-3:]]
        support_vals = [lows[t] for t in troughs[-3:]]

        if len(resistance_vals) >= 2 and len(support_vals) >= 2:
            r_range = (max(resistance_vals) - min(resistance_vals)) / max(resistance_vals)
            s_slope = (support_vals[-1] - support_vals[0]) / max(1, troughs[-1] - troughs[0])

            # Flat top, rising bottom
            if r_range < self.config.price_tolerance and s_slope > 0:
                neckline = float(np.mean(resistance_vals))
                height = neckline - min(support_vals)
                confidence = round(min(1.0, (1.0 - r_range / self.config.price_tolerance) * 0.7), 3)

                if confidence >= self.config.min_confidence:
                    patterns.append(ChartPattern(
                        pattern_type=PatternType.ASCENDING_TRIANGLE,
                        start_idx=offset + min(peaks[0], troughs[0]),
                        end_idx=offset + max(peaks[-1], troughs[-1]),
                        neckline=round(neckline, 4),
                        target_price=round(neckline + height, 4),
                        confidence=confidence,
                        symbol=symbol,
                    ))

            # Descending triangle: flat support, falling resistance
            s_range = (max(support_vals) - min(support_vals)) / max(support_vals)
            r_slope = (resistance_vals[-1] - resistance_vals[0]) / max(1, peaks[-1] - peaks[0])

            if s_range < self.config.price_tolerance and r_slope < 0:
                neckline = float(np.mean(support_vals))
                height = max(resistance_vals) - neckline
                confidence = round(min(1.0, (1.0 - s_range / self.config.price_tolerance) * 0.7), 3)

                if confidence >= self.config.min_confidence:
                    patterns.append(ChartPattern(
                        pattern_type=PatternType.DESCENDING_TRIANGLE,
                        start_idx=offset + min(peaks[0], troughs[0]),
                        end_idx=offset + max(peaks[-1], troughs[-1]),
                        neckline=round(neckline, 4),
                        target_price=round(neckline - height, 4),
                        confidence=confidence,
                        symbol=symbol,
                    ))

        return patterns

    def _find_peaks(self, data: np.ndarray, order: int = 5) -> list[int]:
        """Find local maxima indices."""
        peaks = []
        for i in range(order, len(data) - order):
            if all(data[i] >= data[i - j] for j in range(1, order + 1)) and \
               all(data[i] >= data[i + j] for j in range(1, order + 1)):
                peaks.append(i)
        return peaks

    def _find_troughs(self, data: np.ndarray, order: int = 5) -> list[int]:
        """Find local minima indices."""
        troughs = []
        for i in range(order, len(data) - order):
            if all(data[i] <= data[i - j] for j in range(1, order + 1)) and \
               all(data[i] <= data[i + j] for j in range(1, order + 1)):
                troughs.append(i)
        return troughs
