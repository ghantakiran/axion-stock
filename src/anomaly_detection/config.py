"""Configuration for real-time anomaly detection engine."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class AnomalyType(str, Enum):
    PRICE_SPIKE = "price_spike"
    VOLUME_SURGE = "volume_surge"
    LATENCY_SPIKE = "latency_spike"
    ERROR_BURST = "error_burst"
    PATTERN_BREAK = "pattern_break"
    DATA_DRIFT = "data_drift"
    OUTLIER = "outlier"


class DetectionMethod(str, Enum):
    ZSCORE = "zscore"
    IQR = "iqr"
    ISOLATION_FOREST = "isolation_forest"
    MOVING_AVERAGE = "moving_average"
    PERCENTILE = "percentile"
    CUSTOM = "custom"


class AnomalySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AnomalyStatus(str, Enum):
    DETECTED = "detected"
    CONFIRMED = "confirmed"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


# Default thresholds
DEFAULT_ZSCORE_THRESHOLD = 3.0
DEFAULT_IQR_MULTIPLIER = 1.5
DEFAULT_WINDOW_SIZE = 50
DEFAULT_MIN_SAMPLES = 10
DEFAULT_SENSITIVITY = 0.5
DEFAULT_COOLDOWN_SECONDS = 60
DEFAULT_MAX_ANOMALIES_PER_HOUR = 100
DEFAULT_CONTAMINATION = 0.1
DEFAULT_MA_THRESHOLD = 2.0
DEFAULT_BUFFER_SIZE = 1000
DEFAULT_EMIT_INTERVAL = 1.0


@dataclass
class DetectorConfig:
    """Configuration for a single detection method."""

    method: DetectionMethod = DetectionMethod.ZSCORE
    threshold: float = DEFAULT_ZSCORE_THRESHOLD
    window_size: int = DEFAULT_WINDOW_SIZE
    min_samples: int = DEFAULT_MIN_SAMPLES
    sensitivity: float = DEFAULT_SENSITIVITY


@dataclass
class AnomalyConfig:
    """Top-level anomaly detection configuration."""

    detectors: List[DetectorConfig] = field(
        default_factory=lambda: [DetectorConfig()]
    )
    alert_on_severity: AnomalySeverity = AnomalySeverity.MEDIUM
    cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS
    max_anomalies_per_hour: int = DEFAULT_MAX_ANOMALIES_PER_HOUR
