"""Webhook notification channel.

HTTP POST delivery with HMAC signing.
"""

import hashlib
import hmac
import json
import logging
import re
from typing import Optional

from src.alerts.channels.base import DeliveryChannel
from src.alerts.config import WebhookConfig
from src.alerts.models import Notification

logger = logging.getLogger(__name__)

URL_REGEX = re.compile(
    r"^https?://[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?"
    r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*"
    r"(:\d+)?(/.*)?$"
)


class WebhookChannel(DeliveryChannel):
    """Webhook delivery channel with HMAC signing."""

    def __init__(self, config: Optional[WebhookConfig] = None) -> None:
        self.config = config or WebhookConfig()
        self._delivery_log: list[dict] = []

    def send(self, notification: Notification) -> bool:
        """Send webhook notification via HTTP POST.

        Args:
            notification: Notification with recipient webhook URL.

        Returns:
            True if sent successfully.
        """
        if not self.validate_recipient(notification.recipient):
            notification.mark_failed("Invalid webhook URL")
            return False

        payload = self._build_payload(notification)
        headers = {"Content-Type": "application/json"}

        if self.config.signing_secret:
            signature = self._sign(payload)
            headers["X-Axion-Signature"] = signature

        try:
            import urllib.request

            req = urllib.request.Request(
                notification.recipient,
                data=payload.encode("utf-8"),
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(
                req, timeout=self.config.timeout_seconds,
            ) as response:
                status = response.status

            if 200 <= status < 300:
                notification.mark_sent()
                self._delivery_log.append({
                    "url": notification.recipient,
                    "status_code": status,
                    "status": "sent",
                })
                return True
            else:
                notification.mark_failed(f"HTTP {status}")
                return False

        except Exception as e:
            notification.mark_failed(str(e))
            self._delivery_log.append({
                "url": notification.recipient,
                "error": str(e),
                "status": "failed",
            })
            logger.error("Webhook delivery failed: %s", e)
            return False

    def validate_recipient(self, recipient: str) -> bool:
        """Validate webhook URL format."""
        return bool(URL_REGEX.match(recipient))

    def get_delivery_log(self) -> list[dict]:
        """Get delivery log."""
        return list(self._delivery_log)

    def _build_payload(self, notification: Notification) -> str:
        """Build JSON payload for webhook."""
        return json.dumps({
            "event": "alert.triggered",
            "notification_id": notification.notification_id,
            "event_id": notification.event_id,
            "user_id": notification.user_id,
            "message": notification.message,
            "subject": notification.subject,
            "timestamp": notification.created_at.isoformat(),
        })

    def _sign(self, payload: str) -> str:
        """HMAC-SHA256 sign the payload.

        Args:
            payload: JSON payload string.

        Returns:
            Hex-encoded signature.
        """
        return hmac.new(
            self.config.signing_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
