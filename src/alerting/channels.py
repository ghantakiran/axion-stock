"""PRD-114: Notification & Alerting System - Channel Dispatching."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from .config import ChannelType

logger = logging.getLogger(__name__)


@dataclass
class DeliveryResult:
    """Result of a channel delivery attempt."""

    channel: ChannelType
    success: bool
    error: Optional[str] = None
    delivered_at: datetime = field(default_factory=datetime.utcnow)


class ChannelDispatcher:
    """Dispatches alerts to notification channels.

    Simulates delivery to email, Slack, SMS, webhook, and in-app channels.
    Maintains a delivery log for audit and statistics.
    """

    def __init__(self) -> None:
        self._delivery_log: List[DeliveryResult] = []
        self._alert_channel_map: Dict[str, List[DeliveryResult]] = {}

    def dispatch(self, alert, channel: ChannelType) -> DeliveryResult:
        """Dispatch an alert to a single channel.

        Args:
            alert: The Alert to deliver.
            channel: The target channel.

        Returns:
            DeliveryResult with success status.
        """
        result = DeliveryResult(
            channel=channel,
            success=True,
            delivered_at=datetime.utcnow(),
        )
        self._delivery_log.append(result)

        alert_id = alert.alert_id
        if alert_id not in self._alert_channel_map:
            self._alert_channel_map[alert_id] = []
        self._alert_channel_map[alert_id].append(result)

        logger.info(
            "Dispatched alert %s to %s (success=%s)",
            alert_id,
            channel.value,
            result.success,
        )
        return result

    def dispatch_multi(self, alert, channels: List[ChannelType]) -> List[DeliveryResult]:
        """Dispatch an alert to multiple channels.

        Args:
            alert: The Alert to deliver.
            channels: List of target channels.

        Returns:
            List of DeliveryResult for each channel.
        """
        results = []
        for channel in channels:
            result = self.dispatch(alert, channel)
            results.append(result)
        return results

    def get_delivery_log(self, alert_id: Optional[str] = None) -> List[DeliveryResult]:
        """Get the delivery log, optionally filtered by alert ID.

        Args:
            alert_id: Optional alert ID to filter by.

        Returns:
            List of DeliveryResult entries.
        """
        if alert_id is not None:
            return list(self._alert_channel_map.get(alert_id, []))
        return list(self._delivery_log)

    def get_channel_stats(self) -> Dict[str, int]:
        """Get delivery counts per channel.

        Returns:
            Dict mapping channel name to delivery count.
        """
        stats: Dict[str, int] = {}
        for result in self._delivery_log:
            key = result.channel.value
            stats[key] = stats.get(key, 0) + 1
        return stats

    def clear_log(self) -> None:
        """Clear all delivery logs."""
        self._delivery_log.clear()
        self._alert_channel_map.clear()
        logger.info("Delivery log cleared")
