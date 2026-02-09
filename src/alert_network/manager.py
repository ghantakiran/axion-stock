"""Alert Network Manager (PRD-142).

Orchestrates the full alert→notification pipeline:
rules evaluation, channel dispatch, delivery tracking, and
batched digest generation.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from src.alert_network.rules import (
    AlertRule, RuleEngine, TriggerType, TriggeredAlert,
)
from src.alert_network.channels import (
    ChannelKind, ChannelRegistry, NotificationPayload, ChannelResult,
)
from src.alert_network.delivery import (
    DeliveryTracker, DeliveryRecord, DeliveryStatus, DeliveryPreferences,
)

logger = logging.getLogger(__name__)


@dataclass
class NotificationResult:
    """Result of processing alerts through the notification pipeline."""
    rules_evaluated: int = 0
    alerts_triggered: int = 0
    notifications_sent: int = 0
    notifications_failed: int = 0
    notifications_throttled: int = 0
    triggered_alerts: list = field(default_factory=list)
    delivery_results: list = field(default_factory=list)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "rules_evaluated": self.rules_evaluated,
            "alerts_triggered": self.alerts_triggered,
            "notifications_sent": self.notifications_sent,
            "notifications_failed": self.notifications_failed,
            "notifications_throttled": self.notifications_throttled,
            "alerts": [a.to_dict() for a in self.triggered_alerts[:10]],
        }


@dataclass
class BatchDigest:
    """A batched digest of alerts for delivery."""
    alerts: list = field(default_factory=list)
    period_start: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    period_end: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    symbol_summary: dict = field(default_factory=dict)

    def to_payload(self) -> NotificationPayload:
        """Convert digest to notification payload."""
        count = len(self.alerts)
        symbols = list(self.symbol_summary.keys())
        body = f"{count} alert(s) for {', '.join(symbols[:5])}"
        if len(symbols) > 5:
            body += f" and {len(symbols) - 5} more"
        return NotificationPayload(
            title=f"Alert Digest: {count} alerts",
            body=body,
            severity="info",
        )

    def to_dict(self) -> dict:
        return {
            "alert_count": len(self.alerts),
            "symbols": list(self.symbol_summary.keys()),
        }


class NotificationManager:
    """Orchestrates the alert→notification pipeline.

    Combines rule evaluation, channel dispatch, and delivery
    tracking into a single manager.

    Example:
        mgr = NotificationManager()
        mgr.add_rule(AlertRule(
            name="AAPL Price Alert",
            trigger_type=TriggerType.PRICE_ABOVE,
            symbol="AAPL",
            threshold=200.0,
            channels=[ChannelKind.PUSH, ChannelKind.EMAIL],
        ))
        result = await mgr.evaluate_and_notify(data)
    """

    def __init__(
        self,
        rule_engine: Optional[RuleEngine] = None,
        channel_registry: Optional[ChannelRegistry] = None,
        delivery_tracker: Optional[DeliveryTracker] = None,
    ):
        self._rules = rule_engine or RuleEngine()
        self._channels = channel_registry or ChannelRegistry()
        self._tracker = delivery_tracker or DeliveryTracker()
        self._digest_queue: list[TriggeredAlert] = []

    def add_rule(self, rule: AlertRule) -> None:
        """Add an alert rule."""
        self._rules.add_rule(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """Remove an alert rule."""
        return self._rules.remove_rule(rule_id)

    def get_rules(self) -> list[AlertRule]:
        """Get all rules."""
        return self._rules.get_rules()

    def set_preferences(
        self, user_id: str, prefs: DeliveryPreferences,
    ) -> None:
        """Set delivery preferences for a user."""
        self._tracker.set_preferences(user_id, prefs)

    async def evaluate_and_notify(
        self,
        data: dict,
        user_id: str = "default",
    ) -> NotificationResult:
        """Evaluate rules and send notifications.

        Args:
            data: Dict with keys: prices, signals, volume_anomalies,
                  trending, influencer_signals, consensus.
            user_id: User to send notifications to.

        Returns:
            NotificationResult with delivery summary.
        """
        result = NotificationResult()
        result.rules_evaluated = len(self._rules.get_rules())

        # Step 1: Evaluate rules
        triggered = self._rules.evaluate(data)
        result.alerts_triggered = len(triggered)
        result.triggered_alerts = triggered

        if not triggered:
            return result

        # Step 2: Check delivery preferences
        prefs = self._tracker.get_preferences(user_id)

        # Step 3: Batch or immediate delivery
        if prefs.batch_enabled:
            self._digest_queue.extend(triggered)
            result.notifications_throttled = len(triggered)
            return result

        # Step 4: Send notifications for each triggered alert
        for alert in triggered:
            if not self._tracker.can_deliver(user_id):
                result.notifications_throttled += 1
                continue

            # Determine channels (rule channels or user defaults)
            channels = alert.rule.channels or prefs.enabled_channels

            payload = NotificationPayload(
                title=alert.rule.name or "Alert",
                body=alert.message,
                symbol=alert.symbol,
                severity=alert.severity,
            )

            for channel_kind in channels:
                if isinstance(channel_kind, str):
                    try:
                        channel_kind = ChannelKind(channel_kind)
                    except ValueError:
                        continue

                ch_result = await self._channels.send_to(channel_kind, payload)

                record = DeliveryRecord(
                    delivery_id=f"del_{id(ch_result)}",
                    channel=channel_kind,
                    status=DeliveryStatus.SENT if ch_result.success else DeliveryStatus.FAILED,
                    rule_id=alert.rule.rule_id,
                    symbol=alert.symbol,
                    message=alert.message,
                    error=ch_result.error,
                    attempts=1,
                )

                self._tracker.record(record, user_id)
                result.delivery_results.append(ch_result)

                if ch_result.success:
                    result.notifications_sent += 1
                else:
                    result.notifications_failed += 1

        return result

    async def send_digest(self, user_id: str = "default") -> Optional[NotificationResult]:
        """Send batched digest notification."""
        if not self._digest_queue:
            return None

        digest = BatchDigest(alerts=list(self._digest_queue))
        for alert in self._digest_queue:
            digest.symbol_summary.setdefault(alert.symbol, 0)
            digest.symbol_summary[alert.symbol] += 1

        self._digest_queue.clear()

        payload = digest.to_payload()
        prefs = self._tracker.get_preferences(user_id)
        channels = prefs.enabled_channels

        result = NotificationResult(
            alerts_triggered=len(digest.alerts),
        )

        for channel_kind in channels:
            ch_result = await self._channels.send_to(channel_kind, payload)
            if ch_result.success:
                result.notifications_sent += 1
            else:
                result.notifications_failed += 1

        return result

    def get_delivery_stats(self) -> dict:
        """Get delivery statistics."""
        return self._tracker.get_stats()

    def get_delivery_history(self, limit: int = 50) -> list[DeliveryRecord]:
        """Get recent delivery history."""
        return self._tracker.get_history(limit)

    @property
    def rule_engine(self) -> RuleEngine:
        return self._rules

    @property
    def channel_registry(self) -> ChannelRegistry:
        return self._channels

    @property
    def delivery_tracker(self) -> DeliveryTracker:
        return self._tracker
