"""PRD-103: Observability & Metrics Export — Metrics Registry."""

import logging
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .config import MetricType

logger = logging.getLogger(__name__)


@dataclass
class MetricMeta:
    """Metadata for a registered metric."""

    name: str
    description: str
    metric_type: MetricType
    label_names: Tuple[str, ...] = ()


class Counter:
    """Monotonically increasing counter metric."""

    def __init__(self, name: str, description: str = "", label_names: Tuple[str, ...] = ()):
        self.name = name
        self.description = description
        self.label_names = label_names
        self._lock = threading.Lock()
        self._values: Dict[Tuple[str, ...], float] = {}

    def increment(self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment the counter by the given amount."""
        if amount < 0:
            raise ValueError("Counter increment amount must be non-negative")
        key = self._label_key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    @property
    def value(self) -> float:
        """Return the counter value for the default (no-label) series."""
        with self._lock:
            return self._values.get((), 0.0)

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """Return the counter value for specific labels."""
        key = self._label_key(labels)
        with self._lock:
            return self._values.get(key, 0.0)

    def get_all(self) -> Dict[Tuple[str, ...], float]:
        """Return all label-set values."""
        with self._lock:
            return dict(self._values)

    def reset(self) -> None:
        """Reset the counter (for testing)."""
        with self._lock:
            self._values.clear()

    def _label_key(self, labels: Optional[Dict[str, str]]) -> Tuple[str, ...]:
        if not labels:
            return ()
        return tuple(labels.get(k, "") for k in self.label_names)


class Gauge:
    """Metric that can go up and down."""

    def __init__(self, name: str, description: str = "", label_names: Tuple[str, ...] = ()):
        self.name = name
        self.description = description
        self.label_names = label_names
        self._lock = threading.Lock()
        self._values: Dict[Tuple[str, ...], float] = {}

    def set(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set the gauge to a specific value."""
        key = self._label_key(labels)
        with self._lock:
            self._values[key] = value

    def increment(self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment the gauge."""
        key = self._label_key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def decrement(self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Decrement the gauge."""
        key = self._label_key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) - amount

    @property
    def value(self) -> float:
        """Return the gauge value for the default (no-label) series."""
        with self._lock:
            return self._values.get((), 0.0)

    def get(self, labels: Optional[Dict[str, str]] = None) -> float:
        """Return the gauge value for specific labels."""
        key = self._label_key(labels)
        with self._lock:
            return self._values.get(key, 0.0)

    def get_all(self) -> Dict[Tuple[str, ...], float]:
        """Return all label-set values."""
        with self._lock:
            return dict(self._values)

    def reset(self) -> None:
        """Reset the gauge (for testing)."""
        with self._lock:
            self._values.clear()

    def _label_key(self, labels: Optional[Dict[str, str]]) -> Tuple[str, ...]:
        if not labels:
            return ()
        return tuple(labels.get(k, "") for k in self.label_names)


class Histogram:
    """Distribution metric with configurable buckets."""

    def __init__(
        self,
        name: str,
        description: str = "",
        label_names: Tuple[str, ...] = (),
        buckets: Optional[List[float]] = None,
    ):
        self.name = name
        self.description = description
        self.label_names = label_names
        self.bucket_bounds = sorted(buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0])
        self._lock = threading.Lock()
        # Per label-set: {key: {"buckets": [counts], "count": int, "sum": float}}
        self._data: Dict[Tuple[str, ...], Dict[str, Any]] = {}

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record an observation."""
        key = self._label_key(labels)
        with self._lock:
            if key not in self._data:
                self._data[key] = {
                    "buckets": [0] * (len(self.bucket_bounds) + 1),  # +1 for +Inf
                    "count": 0,
                    "sum": 0.0,
                    "values": [],
                }
            data = self._data[key]
            data["count"] += 1
            data["sum"] += value
            data["values"].append(value)
            # Update cumulative bucket counts
            for i, bound in enumerate(self.bucket_bounds):
                if value <= bound:
                    data["buckets"][i] += 1
            # +Inf bucket always gets incremented
            data["buckets"][-1] += 1

    @property
    def count(self) -> int:
        """Return observation count for the default series."""
        with self._lock:
            data = self._data.get((), {})
            return data.get("count", 0)

    @property
    def sum(self) -> float:
        """Return sum of observations for the default series."""
        with self._lock:
            data = self._data.get((), {})
            return data.get("sum", 0.0)

    def get_count(self, labels: Optional[Dict[str, str]] = None) -> int:
        """Return observation count for specific labels."""
        key = self._label_key(labels)
        with self._lock:
            data = self._data.get(key, {})
            return data.get("count", 0)

    def get_sum(self, labels: Optional[Dict[str, str]] = None) -> float:
        """Return sum of observations for specific labels."""
        key = self._label_key(labels)
        with self._lock:
            data = self._data.get(key, {})
            return data.get("sum", 0.0)

    def get_buckets(self, labels: Optional[Dict[str, str]] = None) -> List[Tuple[float, int]]:
        """Return bucket boundaries and cumulative counts."""
        key = self._label_key(labels)
        with self._lock:
            data = self._data.get(key, {})
            bucket_counts = data.get("buckets", [0] * (len(self.bucket_bounds) + 1))
            result = []
            for i, bound in enumerate(self.bucket_bounds):
                result.append((bound, bucket_counts[i]))
            result.append((float("inf"), bucket_counts[-1]))
            return result

    def quantile(self, q: float, labels: Optional[Dict[str, str]] = None) -> float:
        """Calculate approximate quantile from stored values."""
        key = self._label_key(labels)
        with self._lock:
            data = self._data.get(key, {})
            values = sorted(data.get("values", []))
            if not values:
                return 0.0
            idx = int(math.ceil(q * len(values))) - 1
            idx = max(0, min(idx, len(values) - 1))
            return values[idx]

    def get_all(self) -> Dict[Tuple[str, ...], Dict[str, Any]]:
        """Return all label-set data."""
        with self._lock:
            return {k: dict(v) for k, v in self._data.items()}

    def reset(self) -> None:
        """Reset the histogram (for testing)."""
        with self._lock:
            self._data.clear()

    def _label_key(self, labels: Optional[Dict[str, str]]) -> Tuple[str, ...]:
        if not labels:
            return ()
        return tuple(labels.get(k, "") for k in self.label_names)


class MetricsRegistry:
    """Central registry for all application metrics. Singleton pattern."""

    _instance: Optional["MetricsRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "MetricsRegistry":
        with cls._lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._initialized = False
                cls._instance = instance
            return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._metrics: Dict[str, Any] = {}
        self._meta: Dict[str, MetricMeta] = {}
        self._registry_lock = threading.Lock()
        logger.info("MetricsRegistry initialized")

    def counter(
        self,
        name: str,
        description: str = "",
        label_names: Tuple[str, ...] = (),
    ) -> Counter:
        """Register and return a Counter metric."""
        with self._registry_lock:
            if name in self._metrics:
                existing = self._metrics[name]
                if not isinstance(existing, Counter):
                    raise TypeError(f"Metric '{name}' already registered as {type(existing).__name__}")
                return existing
            c = Counter(name=name, description=description, label_names=label_names)
            self._metrics[name] = c
            self._meta[name] = MetricMeta(
                name=name,
                description=description,
                metric_type=MetricType.COUNTER,
                label_names=label_names,
            )
            return c

    def gauge(
        self,
        name: str,
        description: str = "",
        label_names: Tuple[str, ...] = (),
    ) -> Gauge:
        """Register and return a Gauge metric."""
        with self._registry_lock:
            if name in self._metrics:
                existing = self._metrics[name]
                if not isinstance(existing, Gauge):
                    raise TypeError(f"Metric '{name}' already registered as {type(existing).__name__}")
                return existing
            g = Gauge(name=name, description=description, label_names=label_names)
            self._metrics[name] = g
            self._meta[name] = MetricMeta(
                name=name,
                description=description,
                metric_type=MetricType.GAUGE,
                label_names=label_names,
            )
            return g

    def histogram(
        self,
        name: str,
        description: str = "",
        label_names: Tuple[str, ...] = (),
        buckets: Optional[List[float]] = None,
    ) -> Histogram:
        """Register and return a Histogram metric."""
        with self._registry_lock:
            if name in self._metrics:
                existing = self._metrics[name]
                if not isinstance(existing, Histogram):
                    raise TypeError(f"Metric '{name}' already registered as {type(existing).__name__}")
                return existing
            h = Histogram(
                name=name,
                description=description,
                label_names=label_names,
                buckets=buckets,
            )
            self._metrics[name] = h
            self._meta[name] = MetricMeta(
                name=name,
                description=description,
                metric_type=MetricType.HISTOGRAM,
                label_names=label_names,
            )
            return h

    def get_metric(self, name: str) -> Optional[Any]:
        """Look up a metric by name."""
        with self._registry_lock:
            return self._metrics.get(name)

    def get_meta(self, name: str) -> Optional[MetricMeta]:
        """Look up metric metadata by name."""
        with self._registry_lock:
            return self._meta.get(name)

    def get_all_metrics(self) -> Dict[str, Any]:
        """Return dict of all registered metrics."""
        with self._registry_lock:
            return dict(self._metrics)

    def get_all_meta(self) -> Dict[str, MetricMeta]:
        """Return dict of all metric metadata."""
        with self._registry_lock:
            return dict(self._meta)

    def reset(self) -> None:
        """Reset all metrics and registrations (for testing)."""
        with self._registry_lock:
            self._metrics.clear()
            self._meta.clear()
        logger.debug("MetricsRegistry reset")

    @classmethod
    def destroy(cls) -> None:
        """Destroy the singleton instance (for testing)."""
        with cls._lock:
            cls._instance = None
