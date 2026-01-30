"""Slack notification channel.

Delivers notifications via Slack incoming webhooks.
"""

import json
import logging
import re
from typing import Optional

from src.alerts.channels.base import DeliveryChannel
from src.alerts.config import SlackConfig
from src.alerts.models import Notification

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_REGEX = re.compile(
    r"^https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[a-zA-Z0-9]+$"
)


class SlackChannel(DeliveryChannel):
    """Slack notification delivery via incoming webhooks."""

    # Priority to emoji mapping
    PRIORITY_EMOJI = {
        "low": ":information_source:",
        "medium": ":warning:",
        "high": ":rotating_light:",
        "critical": ":fire:",
    }

    def __init__(self, config: Optional[SlackConfig] = None) -> None:
        self.config = config or SlackConfig()
        self._delivery_log: list[dict] = []

    def send(self, notification: Notification) -> bool:
        """Send notification to Slack.

        Args:
            notification: Notification with Slack webhook URL as recipient.

        Returns:
            True if sent successfully.
        """
        webhook_url = notification.recipient or self.config.default_webhook_url
        if not webhook_url:
            notification.mark_failed("No Slack webhook URL configured")
            return False

        if not self.validate_recipient(webhook_url):
            # For non-Slack URLs, still attempt delivery (custom integrations)
            pass

        payload = self._build_payload(notification)

        try:
            import urllib.request

            req = urllib.request.Request(
                webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                status = response.status

            if 200 <= status < 300:
                notification.mark_sent()
                self._delivery_log.append({
                    "url": webhook_url,
                    "status": "sent",
                })
                return True
            else:
                notification.mark_failed(f"Slack HTTP {status}")
                return False

        except Exception as e:
            notification.mark_failed(str(e))
            self._delivery_log.append({
                "url": webhook_url,
                "error": str(e),
                "status": "failed",
            })
            logger.error("Slack delivery failed: %s", e)
            return False

    def validate_recipient(self, recipient: str) -> bool:
        """Validate Slack webhook URL format."""
        return bool(SLACK_WEBHOOK_REGEX.match(recipient))

    def get_delivery_log(self) -> list[dict]:
        """Get delivery log."""
        return list(self._delivery_log)

    def _build_payload(self, notification: Notification) -> dict:
        """Build Slack message payload with blocks."""
        subject = notification.subject or "Axion Alert"

        return {
            "text": f"{subject}: {notification.message}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": subject,
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": notification.message,
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"_Axion Alert System | {notification.created_at.strftime('%Y-%m-%d %H:%M UTC')}_",
                        },
                    ],
                },
            ],
        }
