"""PRD-114: Notification & Alerting System - Alert Manager."""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .aggregation import AlertAggregator
from .channels import ChannelDispatcher
from .config import AlertCategory, AlertConfig, AlertSeverity, AlertStatus, ChannelType
from .routing import RoutingEngine

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """Represents a single alert in the system."""

    alert_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    message: str = ""
    severity: AlertSeverity = AlertSeverity.INFO
    category: AlertCategory = AlertCategory.SYSTEM
    status: AlertStatus = AlertStatus.OPEN
    source: str = "system"
    tags: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    dedup_key: Optional[str] = None
    occurrence_count: int = 1


class AlertManager:
    """Central alert management system.

    Handles alert creation, deduplication, lifecycle management,
    routing, and dispatching. Thread-safe via internal locking.
    """

    def __init__(self, config: Optional[AlertConfig] = None) -> None:
        self._config = config or AlertConfig()
        self._alerts: Dict[str, Alert] = {}
        self._lock = threading.Lock()
        self._router = RoutingEngine(default_channels=self._config.default_channels)
        self._aggregator = AlertAggregator(config=self._config)
        self._dispatcher = ChannelDispatcher()
        self._dedup_cache: Dict[str, Alert] = {}

    @property
    def router(self) -> RoutingEngine:
        """Access the routing engine for adding rules."""
        return self._router

    @property
    def aggregator(self) -> AlertAggregator:
        """Access the alert aggregator."""
        return self._aggregator

    @property
    def dispatcher(self) -> ChannelDispatcher:
        """Access the channel dispatcher."""
        return self._dispatcher

    def fire(
        self,
        title: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.INFO,
        category: AlertCategory = AlertCategory.SYSTEM,
        source: str = "system",
        tags: Optional[Dict[str, str]] = None,
        dedup_key: Optional[str] = None,
    ) -> Alert:
        """Fire a new alert.

        Performs deduplication, creates the alert, routes it to channels,
        and dispatches notifications.

        Args:
            title: Alert title.
            message: Alert message body.
            severity: Alert severity level.
            category: Alert category.
            source: Source of the alert.
            tags: Optional key-value tags.
            dedup_key: Optional deduplication key.

        Returns:
            The created or deduplicated Alert.
        """
        with self._lock:
            # Check deduplication
            if dedup_key:
                existing = self._check_dedup(dedup_key)
                if existing is not None:
                    existing.occurrence_count += 1
                    logger.info(
                        "Deduplicated alert %s (key=%s, count=%d)",
                        existing.alert_id,
                        dedup_key,
                        existing.occurrence_count,
                    )
                    return existing

            # Create new alert
            alert = Alert(
                title=title,
                message=message,
                severity=severity,
                category=category,
                source=source,
                tags=tags or {},
                dedup_key=dedup_key,
            )

            self._alerts[alert.alert_id] = alert

            # Register in dedup cache
            if dedup_key:
                self._dedup_cache[dedup_key] = alert

            logger.info(
                "Alert fired: %s [%s/%s] - %s",
                alert.alert_id,
                severity.value,
                category.value,
                title,
            )

            # Route and dispatch
            channels = self._router.resolve_channels(alert)
            if channels:
                self._dispatcher.dispatch_multi(alert, channels)

            return alert

    def acknowledge(self, alert_id: str, by: str = "system") -> bool:
        """Acknowledge an alert.

        Args:
            alert_id: The alert to acknowledge.
            by: Who acknowledged it.

        Returns:
            True if the alert was found and acknowledged.
        """
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert is None:
                return False
            if alert.status != AlertStatus.OPEN:
                return False
            alert.status = AlertStatus.ACKNOWLEDGED
            alert.acknowledged_at = datetime.utcnow()
            alert.acknowledged_by = by
            logger.info("Alert %s acknowledged by %s", alert_id, by)
            return True

    def resolve(self, alert_id: str) -> bool:
        """Resolve an alert.

        Args:
            alert_id: The alert to resolve.

        Returns:
            True if the alert was found and resolved.
        """
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert is None:
                return False
            if alert.status == AlertStatus.RESOLVED:
                return False
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = datetime.utcnow()
            logger.info("Alert %s resolved", alert_id)
            return True

    def suppress(self, alert_id: str) -> bool:
        """Suppress an alert.

        Args:
            alert_id: The alert to suppress.

        Returns:
            True if the alert was found and suppressed.
        """
        with self._lock:
            alert = self._alerts.get(alert_id)
            if alert is None:
                return False
            alert.status = AlertStatus.SUPPRESSED
            logger.info("Alert %s suppressed", alert_id)
            return True

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get a single alert by ID.

        Args:
            alert_id: The alert ID.

        Returns:
            The Alert, or None if not found.
        """
        return self._alerts.get(alert_id)

    def get_active_alerts(self) -> List[Alert]:
        """Get all alerts with OPEN status.

        Returns:
            List of OPEN alerts.
        """
        return [a for a in self._alerts.values() if a.status == AlertStatus.OPEN]

    def get_alerts(
        self,
        status: Optional[AlertStatus] = None,
        severity: Optional[AlertSeverity] = None,
        category: Optional[AlertCategory] = None,
    ) -> List[Alert]:
        """Get alerts with optional filtering.

        Args:
            status: Filter by status.
            severity: Filter by severity.
            category: Filter by category.

        Returns:
            List of matching alerts.
        """
        results = list(self._alerts.values())

        if status is not None:
            results = [a for a in results if a.status == status]
        if severity is not None:
            results = [a for a in results if a.severity == severity]
        if category is not None:
            results = [a for a in results if a.category == category]

        return results

    def get_alert_count_by_severity(self) -> Dict[str, int]:
        """Get count of alerts grouped by severity.

        Returns:
            Dict mapping severity value to count.
        """
        counts: Dict[str, int] = {}
        for alert in self._alerts.values():
            key = alert.severity.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _check_dedup(self, dedup_key: str) -> Optional[Alert]:
        """Check if a dedup key has been seen within the dedup window.

        Args:
            dedup_key: The deduplication key.

        Returns:
            The existing Alert if found within the window, else None.
        """
        existing = self._dedup_cache.get(dedup_key)
        if existing is None:
            return None

        window = timedelta(seconds=self._config.dedup_window_seconds)
        if datetime.utcnow() - existing.created_at > window:
            # Expired, remove from cache
            del self._dedup_cache[dedup_key]
            return None

        return existing
