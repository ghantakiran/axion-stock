"""Core anomaly detection engine with multiple detection methods."""

import math
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .config import (
    AnomalyConfig,
    AnomalySeverity,
    AnomalyType,
    DetectionMethod,
    DetectorConfig,
    DEFAULT_ZSCORE_THRESHOLD,
    DEFAULT_IQR_MULTIPLIER,
    DEFAULT_CONTAMINATION,
    DEFAULT_MA_THRESHOLD,
)


@dataclass
class DataPoint:
    """A single data point for anomaly detection."""

    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    value: float = 0.0
    metric_name: str = ""
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class AnomalyResult:
    """Result of anomaly detection on a data point."""

    anomaly_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    data_point: Optional[DataPoint] = None
    method: DetectionMethod = DetectionMethod.ZSCORE
    score: float = 0.0
    severity: AnomalySeverity = AnomalySeverity.LOW
    is_anomaly: bool = False
    anomaly_type: AnomalyType = AnomalyType.OUTLIER
    context: Dict[str, Any] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def _mean(values: List[float]) -> float:
    """Calculate mean of a list of values."""
    if not values:
        return 0.0
    return sum(values) / len(values)


def _std(values: List[float]) -> float:
    """Calculate standard deviation of a list of values."""
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    variance = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def _median(values: List[float]) -> float:
    """Calculate median of a list of values."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 0:
        return (s[n // 2 - 1] + s[n // 2]) / 2
    return s[n // 2]


def _quartiles(values: List[float]) -> Tuple[float, float]:
    """Calculate Q1 and Q3 for IQR computation."""
    if len(values) < 4:
        return (min(values), max(values))
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 0:
        lower = s[:mid]
        upper = s[mid:]
    else:
        lower = s[:mid]
        upper = s[mid + 1:]
    return (_median(lower), _median(upper))


def _score_to_severity(score: float) -> AnomalySeverity:
    """Map an anomaly score to a severity level."""
    if score >= 5.0:
        return AnomalySeverity.CRITICAL
    elif score >= 4.0:
        return AnomalySeverity.HIGH
    elif score >= 3.0:
        return AnomalySeverity.MEDIUM
    return AnomalySeverity.LOW


class DetectorEngine:
    """Multi-method anomaly detection engine."""

    def __init__(self, config: Optional[AnomalyConfig] = None):
        self.config = config or AnomalyConfig()
        self._history: Dict[str, List[float]] = defaultdict(list)
        self._baselines: Dict[str, Dict[str, float]] = {}

    # ── Public API ────────────────────────────────────────────────────

    def add_data_point(self, point: DataPoint) -> Optional[AnomalyResult]:
        """Ingest a data point and run configured detectors.

        Returns an AnomalyResult if the point is anomalous, else None.
        """
        self._history[point.metric_name].append(point.value)
        values = self._history[point.metric_name]

        # Need enough history before we can detect
        min_samples = max(
            dc.min_samples for dc in self.config.detectors
        )
        if len(values) < min_samples:
            return None

        # Run each configured detector
        best_result: Optional[AnomalyResult] = None
        for dc in self.config.detectors:
            result = self._run_detector(dc, values, point)
            if result and result.is_anomaly:
                if best_result is None or result.score > best_result.score:
                    best_result = result

        return best_result

    def detect_zscore(
        self, values: List[float], threshold: float = DEFAULT_ZSCORE_THRESHOLD
    ) -> List[int]:
        """Return indices of values that exceed the Z-score threshold."""
        if len(values) < 2:
            return []
        m = _mean(values)
        s = _std(values)
        if s == 0:
            return []
        return [i for i, v in enumerate(values) if abs((v - m) / s) > threshold]

    def detect_iqr(
        self, values: List[float], multiplier: float = DEFAULT_IQR_MULTIPLIER
    ) -> List[int]:
        """Return indices of values outside IQR bounds."""
        if len(values) < 4:
            return []
        q1, q3 = _quartiles(values)
        iqr = q3 - q1
        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr
        return [i for i, v in enumerate(values) if v < lower or v > upper]

    def detect_isolation_forest(
        self, values: List[float], contamination: float = DEFAULT_CONTAMINATION
    ) -> List[int]:
        """Simplified isolation-forest-style outlier detection.

        Uses a score based on distance from the mean relative to the range,
        flagging the top *contamination* fraction as anomalous.
        """
        if len(values) < 4:
            return []
        m = _mean(values)
        s = _std(values)
        if s == 0:
            return []

        scores = [abs(v - m) / s for v in values]
        n_anomalies = max(1, int(len(values) * contamination))
        threshold = sorted(scores, reverse=True)[min(n_anomalies - 1, len(scores) - 1)]
        return [i for i, sc in enumerate(scores) if sc >= threshold]

    def detect_moving_average(
        self,
        values: List[float],
        window: int = 10,
        threshold: float = DEFAULT_MA_THRESHOLD,
    ) -> List[int]:
        """Return indices where values deviate from moving average beyond threshold."""
        if len(values) < window + 1:
            return []
        anomalies: List[int] = []
        for i in range(window, len(values)):
            window_vals = values[i - window: i]
            ma = _mean(window_vals)
            s = _std(window_vals)
            if s == 0:
                continue
            z = abs(values[i] - ma) / s
            if z > threshold:
                anomalies.append(i)
        return anomalies

    def batch_detect(self, data_points: List[DataPoint]) -> List[AnomalyResult]:
        """Run detection on a batch of data points, returning all anomalies found."""
        results: List[AnomalyResult] = []
        for point in data_points:
            result = self.add_data_point(point)
            if result is not None:
                results.append(result)
        return results

    def get_baseline(self, metric_name: str) -> Dict[str, float]:
        """Return baseline statistics for a given metric."""
        values = self._history.get(metric_name, [])
        if not values:
            return {"count": 0, "mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
        return {
            "count": len(values),
            "mean": _mean(values),
            "std": _std(values),
            "min": min(values),
            "max": max(values),
            "median": _median(values),
        }

    # ── Internal ──────────────────────────────────────────────────────

    def _run_detector(
        self, dc: DetectorConfig, values: List[float], point: DataPoint
    ) -> Optional[AnomalyResult]:
        """Execute a single detector config against the value history."""
        window = values[-dc.window_size:] if len(values) > dc.window_size else values
        latest_value = point.value

        if dc.method == DetectionMethod.ZSCORE:
            m = _mean(window)
            s = _std(window)
            if s == 0:
                return None
            z = abs(latest_value - m) / s
            is_anomaly = z > dc.threshold
            score = z
        elif dc.method == DetectionMethod.IQR:
            if len(window) < 4:
                return None
            q1, q3 = _quartiles(window)
            iqr = q3 - q1
            if iqr == 0:
                return None
            lower = q1 - dc.threshold * iqr
            upper = q3 + dc.threshold * iqr
            is_anomaly = latest_value < lower or latest_value > upper
            dist = max(lower - latest_value, latest_value - upper, 0)
            score = dist / iqr if iqr > 0 else 0.0
            score = min(score + 3.0, 10.0) if is_anomaly else score
        elif dc.method == DetectionMethod.MOVING_AVERAGE:
            if len(window) < 3:
                return None
            ma = _mean(window[:-1])
            s = _std(window[:-1])
            if s == 0:
                return None
            z = abs(latest_value - ma) / s
            is_anomaly = z > dc.threshold
            score = z
        elif dc.method == DetectionMethod.PERCENTILE:
            sorted_w = sorted(window)
            rank = sum(1 for v in sorted_w if v <= latest_value) / len(sorted_w)
            pct_threshold = 1.0 - dc.sensitivity
            is_anomaly = rank >= pct_threshold or rank <= (1.0 - pct_threshold)
            score = max(abs(rank - 0.5) * 10.0, 0.0)
        elif dc.method == DetectionMethod.ISOLATION_FOREST:
            m = _mean(window)
            s = _std(window)
            if s == 0:
                return None
            score = abs(latest_value - m) / s
            is_anomaly = score > dc.threshold
        else:
            return None

        if not is_anomaly:
            return None

        return AnomalyResult(
            data_point=point,
            method=dc.method,
            score=round(score, 4),
            severity=_score_to_severity(score),
            is_anomaly=True,
            context={
                "window_size": len(window),
                "mean": round(_mean(window), 4),
                "std": round(_std(window), 4),
            },
        )
