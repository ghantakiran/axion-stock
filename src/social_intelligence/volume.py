"""Social Volume Anomaly Detection (PRD-141).

Detects unusual spikes in social mention volume using Z-score
analysis with rolling windows. Identifies when a ticker's social
activity deviates significantly from its baseline.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VolumeConfig:
    """Configuration for volume anomaly detection."""
    # Rolling window for baseline calculation
    baseline_window: int = 24  # hours
    # Z-score threshold for anomaly
    z_score_threshold: float = 2.0
    # Minimum data points for reliable detection
    min_data_points: int = 6
    # Sustained anomaly window
    sustained_window: int = 3  # consecutive periods
    # Volume multiplier for "extreme" anomaly
    extreme_multiplier: float = 5.0


@dataclass
class MentionTimeseries:
    """Time-series of mention counts for a ticker."""
    symbol: str = ""
    counts: list = field(default_factory=list)
    timestamps: list = field(default_factory=list)

    @property
    def latest(self) -> int:
        return self.counts[-1] if self.counts else 0

    @property
    def mean(self) -> float:
        return float(np.mean(self.counts)) if self.counts else 0.0

    @property
    def std(self) -> float:
        return float(np.std(self.counts)) if len(self.counts) > 1 else 0.0

    def add(self, count: int, timestamp: Optional[datetime] = None) -> None:
        """Add a new data point."""
        self.counts.append(count)
        self.timestamps.append(
            timestamp or datetime.now(timezone.utc)
        )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "data_points": len(self.counts),
            "latest": self.latest,
            "mean": round(self.mean, 2),
            "std": round(self.std, 2),
        }


@dataclass
class VolumeAnomaly:
    """Detected volume anomaly for a ticker."""
    symbol: str = ""
    current_volume: int = 0
    baseline_mean: float = 0.0
    baseline_std: float = 0.0
    z_score: float = 0.0
    volume_ratio: float = 0.0
    is_extreme: bool = False
    is_sustained: bool = False
    consecutive_anomalies: int = 0
    detected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def severity(self) -> str:
        """Anomaly severity label."""
        if self.is_extreme:
            return "extreme"
        elif self.is_sustained:
            return "sustained"
        elif self.z_score >= 3.0:
            return "high"
        return "moderate"

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "current_volume": self.current_volume,
            "baseline_mean": round(self.baseline_mean, 2),
            "z_score": round(self.z_score, 2),
            "volume_ratio": round(self.volume_ratio, 2),
            "severity": self.severity,
            "is_extreme": self.is_extreme,
            "is_sustained": self.is_sustained,
        }


class VolumeAnalyzer:
    """Detects anomalous volume spikes in social mention data.

    Uses Z-score analysis with configurable thresholds. Tracks
    both point anomalies (single spike) and sustained anomalies
    (multiple consecutive periods above threshold).

    Example:
        analyzer = VolumeAnalyzer()
        analyzer.update("AAPL", 5)
        analyzer.update("AAPL", 7)
        analyzer.update("AAPL", 50)  # spike
        anomalies = analyzer.check_all()
    """

    def __init__(self, config: Optional[VolumeConfig] = None):
        self.config = config or VolumeConfig()
        self._timeseries: dict[str, MentionTimeseries] = {}
        self._anomaly_streaks: dict[str, int] = {}

    def update(
        self,
        symbol: str,
        count: int,
        timestamp: Optional[datetime] = None,
    ) -> Optional[VolumeAnomaly]:
        """Add new mention count and check for anomaly.

        Args:
            symbol: Ticker symbol.
            count: Mention count for this period.
            timestamp: When this count was observed.

        Returns:
            VolumeAnomaly if detected, None otherwise.
        """
        if symbol not in self._timeseries:
            self._timeseries[symbol] = MentionTimeseries(symbol=symbol)

        ts = self._timeseries[symbol]
        ts.add(count, timestamp)

        # Trim to window
        window = self.config.baseline_window
        if len(ts.counts) > window:
            ts.counts = ts.counts[-window:]
            ts.timestamps = ts.timestamps[-window:]

        return self._check_anomaly(symbol)

    def update_batch(
        self,
        mention_counts: dict[str, int],
    ) -> list[VolumeAnomaly]:
        """Update multiple tickers and return any anomalies.

        Args:
            mention_counts: Dict of symbol -> current mention count.

        Returns:
            List of detected anomalies.
        """
        anomalies = []
        for symbol, count in mention_counts.items():
            anomaly = self.update(symbol, count)
            if anomaly:
                anomalies.append(anomaly)
        return anomalies

    def check_all(self) -> list[VolumeAnomaly]:
        """Check all tracked tickers for anomalies.

        Returns:
            List of VolumeAnomaly for tickers currently in anomalous state.
        """
        anomalies = []
        for symbol in self._timeseries:
            anomaly = self._check_anomaly(symbol)
            if anomaly:
                anomalies.append(anomaly)
        return anomalies

    def get_timeseries(self, symbol: str) -> Optional[MentionTimeseries]:
        """Get the mention time-series for a ticker."""
        return self._timeseries.get(symbol)

    def detect_anomalies(
        self,
        mention_history: dict[str, list[int]],
    ) -> list[VolumeAnomaly]:
        """Detect anomalies from full mention history.

        Args:
            mention_history: Dict of symbol -> list of hourly mention counts.

        Returns:
            List of VolumeAnomaly for each ticker with anomalous latest value.
        """
        anomalies = []
        for symbol, counts in mention_history.items():
            if len(counts) < self.config.min_data_points:
                continue

            # Use all but last as baseline, last as current
            baseline = counts[:-1]
            current = counts[-1]

            mean = float(np.mean(baseline))
            std = float(np.std(baseline))

            if std == 0:
                std = max(1.0, mean * 0.1)

            z_score = (current - mean) / std

            if z_score >= self.config.z_score_threshold:
                ratio = current / mean if mean > 0 else current
                anomalies.append(VolumeAnomaly(
                    symbol=symbol,
                    current_volume=current,
                    baseline_mean=mean,
                    baseline_std=std,
                    z_score=z_score,
                    volume_ratio=ratio,
                    is_extreme=ratio >= self.config.extreme_multiplier,
                ))

        anomalies.sort(key=lambda a: a.z_score, reverse=True)
        return anomalies

    def _check_anomaly(self, symbol: str) -> Optional[VolumeAnomaly]:
        """Check a single ticker for anomaly."""
        ts = self._timeseries.get(symbol)
        if not ts or len(ts.counts) < self.config.min_data_points:
            return None

        # Baseline: all except latest
        baseline = ts.counts[:-1]
        current = ts.counts[-1]

        mean = float(np.mean(baseline))
        std = float(np.std(baseline))

        if std == 0:
            std = max(1.0, mean * 0.1)

        z_score = (current - mean) / std

        if z_score < self.config.z_score_threshold:
            self._anomaly_streaks[symbol] = 0
            return None

        # Track consecutive anomalies
        streak = self._anomaly_streaks.get(symbol, 0) + 1
        self._anomaly_streaks[symbol] = streak

        ratio = current / mean if mean > 0 else float(current)

        return VolumeAnomaly(
            symbol=symbol,
            current_volume=current,
            baseline_mean=mean,
            baseline_std=std,
            z_score=z_score,
            volume_ratio=ratio,
            is_extreme=ratio >= self.config.extreme_multiplier,
            is_sustained=streak >= self.config.sustained_window,
            consecutive_anomalies=streak,
        )
