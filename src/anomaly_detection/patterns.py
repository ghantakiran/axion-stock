"""Trading pattern anomaly detection."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .detector import _mean, _std


@dataclass
class TradingPattern:
    """A recognised trading pattern for a symbol."""

    pattern_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    pattern_type: str = ""
    symbols: List[str] = field(default_factory=list)
    time_range: Tuple[Optional[datetime], Optional[datetime]] = (None, None)
    description: str = ""
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class PatternAnomaly:
    """An anomalous deviation from expected trading patterns."""

    anomaly_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    pattern: Optional[TradingPattern] = None
    deviation_score: float = 0.0
    expected: float = 0.0
    actual: float = 0.0
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class PatternAnalyzer:
    """Analyzes trading data for pattern-based anomalies."""

    def __init__(self, zscore_threshold: float = 2.0):
        self._zscore_threshold = zscore_threshold
        self._pattern_history: Dict[str, List[TradingPattern]] = {}

    # ── Public API ────────────────────────────────────────────────────

    def analyze_volume_pattern(
        self, symbol: str, volumes: List[float]
    ) -> List[PatternAnomaly]:
        """Detect anomalous volume values for a symbol."""
        if len(volumes) < 3:
            return []
        m = _mean(volumes)
        s = _std(volumes)
        if s == 0:
            return []

        anomalies: List[PatternAnomaly] = []
        for i, v in enumerate(volumes):
            z = abs(v - m) / s
            if z > self._zscore_threshold:
                pattern = TradingPattern(
                    pattern_type="volume_anomaly",
                    symbols=[symbol],
                    description=f"Volume anomaly at index {i}: {v:.2f} (mean={m:.2f}, std={s:.2f})",
                )
                self._record_pattern(symbol, pattern)
                anomalies.append(
                    PatternAnomaly(
                        pattern=pattern,
                        deviation_score=round(z, 4),
                        expected=round(m, 4),
                        actual=round(v, 4),
                    )
                )
        return anomalies

    def analyze_price_pattern(
        self, symbol: str, prices: List[float]
    ) -> List[PatternAnomaly]:
        """Detect anomalous price movements for a symbol (using returns)."""
        if len(prices) < 4:
            return []
        # Compute returns
        returns = [
            (prices[i] - prices[i - 1]) / prices[i - 1]
            for i in range(1, len(prices))
            if prices[i - 1] != 0
        ]
        if len(returns) < 3:
            return []

        m = _mean(returns)
        s = _std(returns)
        if s == 0:
            return []

        anomalies: List[PatternAnomaly] = []
        for i, r in enumerate(returns):
            z = abs(r - m) / s
            if z > self._zscore_threshold:
                pattern = TradingPattern(
                    pattern_type="price_anomaly",
                    symbols=[symbol],
                    description=f"Price return anomaly at index {i + 1}: return={r:.4f}",
                )
                self._record_pattern(symbol, pattern)
                anomalies.append(
                    PatternAnomaly(
                        pattern=pattern,
                        deviation_score=round(z, 4),
                        expected=round(m, 4),
                        actual=round(r, 4),
                    )
                )
        return anomalies

    def detect_regime_change(
        self, series: List[float], window: int = 10
    ) -> List[int]:
        """Detect regime change points based on rolling mean shift.

        Uses pooled standard deviation of the two windows for a more
        robust regime-change signal.

        Returns list of indices where a regime change is detected.
        """
        if len(series) < window * 2:
            return []
        change_points: List[int] = []
        for i in range(window, len(series) - window):
            left = series[i - window: i]
            right = series[i: i + window]
            left_mean = _mean(left)
            right_mean = _mean(right)
            left_std = _std(left)
            right_std = _std(right)
            # Pooled standard deviation
            pooled_std = ((left_std ** 2 + right_std ** 2) / 2) ** 0.5
            if pooled_std == 0:
                # If both halves are constant but different, that is a change
                if left_mean != right_mean:
                    if not change_points or i - change_points[-1] >= window:
                        change_points.append(i)
                continue
            shift = abs(right_mean - left_mean) / pooled_std
            if shift > self._zscore_threshold:
                # Avoid duplicate adjacent points
                if not change_points or i - change_points[-1] >= window:
                    change_points.append(i)
        return change_points

    def compare_to_baseline(
        self, current: float, baseline: float
    ) -> float:
        """Compute deviation score of current value from baseline.

        Returns a ratio indicating the degree of deviation.
        """
        if baseline == 0:
            return 0.0 if current == 0 else float("inf")
        return round(abs(current - baseline) / abs(baseline), 4)

    def get_pattern_history(self, symbol: str) -> List[TradingPattern]:
        """Return all detected patterns for a symbol."""
        return list(self._pattern_history.get(symbol, []))

    # ── Internal ──────────────────────────────────────────────────────

    def _record_pattern(self, symbol: str, pattern: TradingPattern) -> None:
        """Store pattern in history."""
        if symbol not in self._pattern_history:
            self._pattern_history[symbol] = []
        self._pattern_history[symbol].append(pattern)
