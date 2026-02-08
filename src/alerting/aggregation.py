"""PRD-114: Notification & Alerting System - Alert Aggregation."""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .config import AlertConfig, AlertSeverity

logger = logging.getLogger(__name__)


@dataclass
class AlertDigest:
    """A digest summarizing multiple aggregated alerts."""

    digest_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    alerts: List = field(default_factory=list)
    window_start: datetime = field(default_factory=datetime.utcnow)
    window_end: datetime = field(default_factory=datetime.utcnow)
    summary: str = ""

    @property
    def count(self) -> int:
        """Number of alerts in this digest."""
        return len(self.alerts)

    @property
    def severity_counts(self) -> Dict[str, int]:
        """Count of alerts by severity level."""
        counts: Dict[str, int] = {}
        for alert in self.alerts:
            key = alert.severity.value
            counts[key] = counts.get(key, 0) + 1
        return counts


class AlertAggregator:
    """Aggregates alerts within time windows to reduce noise.

    Collects alerts by category during a configurable time window,
    then flushes them as a digest for batched delivery.
    """

    def __init__(self, config: Optional[AlertConfig] = None) -> None:
        self._config = config or AlertConfig()
        self._windows: Dict[str, List] = {}
        self._window_start: Dict[str, datetime] = {}

    def add_alert(self, alert) -> bool:
        """Add an alert to the current aggregation window.

        Args:
            alert: The Alert to aggregate.

        Returns:
            True if the window is still open (not yet full).
        """
        category_key = alert.category.value
        now = datetime.utcnow()

        # Initialize window if needed
        if category_key not in self._window_start:
            self._window_start[category_key] = now
            self._windows[category_key] = []

        # Check if window has expired
        window_start = self._window_start[category_key]
        window_duration = timedelta(seconds=self._config.aggregation_window_seconds)
        if now - window_start > window_duration:
            # Window expired, start new one
            self._window_start[category_key] = now
            self._windows[category_key] = []

        self._windows[category_key].append(alert)
        count = len(self._windows[category_key])

        logger.debug(
            "Added alert to %s window (%d/%d)",
            category_key,
            count,
            self._config.max_alerts_per_window,
        )

        return count < self._config.max_alerts_per_window

    def flush_window(self, category: str) -> Optional[AlertDigest]:
        """Flush the aggregation window for a category, creating a digest.

        Args:
            category: The category key (AlertCategory.value) to flush.

        Returns:
            AlertDigest if there were alerts, None otherwise.
        """
        alerts = self._windows.get(category, [])
        if not alerts:
            return None

        window_start = self._window_start.get(category, datetime.utcnow())
        now = datetime.utcnow()

        # Build summary
        severity_parts = []
        severity_counts: Dict[str, int] = {}
        for a in alerts:
            key = a.severity.value
            severity_counts[key] = severity_counts.get(key, 0) + 1
        for sev, cnt in severity_counts.items():
            severity_parts.append(f"{cnt} {sev}")
        summary = f"{len(alerts)} alerts in {category}: {', '.join(severity_parts)}"

        digest = AlertDigest(
            alerts=list(alerts),
            window_start=window_start,
            window_end=now,
            summary=summary,
        )

        # Clear the window
        self._windows[category] = []
        self._window_start[category] = now

        logger.info("Flushed %s window: %d alerts", category, len(alerts))
        return digest

    def should_aggregate(self, alert) -> bool:
        """Determine if an alert should be aggregated.

        Args:
            alert: The Alert to check.

        Returns:
            True if aggregation is enabled and the window is active.
        """
        if not self._config.enable_aggregation:
            return False

        category_key = alert.category.value
        now = datetime.utcnow()

        # Check if there's an active window
        if category_key in self._window_start:
            window_start = self._window_start[category_key]
            window_duration = timedelta(seconds=self._config.aggregation_window_seconds)
            if now - window_start <= window_duration:
                return True

        # No active window, but aggregation is enabled so new window will be created
        return True

    def get_pending_count(self) -> int:
        """Get the total number of alerts pending in all windows.

        Returns:
            Total count of pending alerts across all categories.
        """
        total = 0
        for alerts in self._windows.values():
            total += len(alerts)
        return total

    def reset(self) -> None:
        """Clear all aggregation windows."""
        self._windows.clear()
        self._window_start.clear()
        logger.info("Alert aggregator reset")
