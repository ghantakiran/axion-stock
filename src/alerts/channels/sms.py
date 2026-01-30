"""SMS notification channel.

Twilio-compatible SMS delivery.
"""

import logging
import re
from typing import Optional

from src.alerts.channels.base import DeliveryChannel
from src.alerts.config import SMSConfig
from src.alerts.models import Notification

logger = logging.getLogger(__name__)

PHONE_REGEX = re.compile(r"^\+?[1-9]\d{6,14}$")


class SMSChannel(DeliveryChannel):
    """SMS delivery channel."""

    def __init__(self, config: Optional[SMSConfig] = None) -> None:
        self.config = config or SMSConfig()
        self._delivery_log: list[dict] = []

    def send(self, notification: Notification) -> bool:
        """Send SMS notification.

        Args:
            notification: Notification with recipient phone number.

        Returns:
            True if sent successfully.
        """
        if not self.validate_recipient(notification.recipient):
            notification.mark_failed("Invalid phone number")
            return False

        # Truncate message for SMS (160 char limit)
        message = notification.message[:155] + "..." if len(notification.message) > 160 else notification.message

        if not self.config.account_sid:
            # No Twilio configured — dry run
            self._delivery_log.append({
                "to": notification.recipient,
                "body": message,
                "status": "dry_run",
            })
            notification.mark_sent()
            logger.info("SMS (dry run) to %s", notification.recipient)
            return True

        try:
            # Twilio integration (requires twilio package)
            from twilio.rest import Client  # type: ignore[import-not-found]
            client = Client(self.config.account_sid, self.config.auth_token)
            client.messages.create(
                to=notification.recipient,
                from_=self.config.from_number,
                body=message,
            )
            notification.mark_sent()
            self._delivery_log.append({
                "to": notification.recipient,
                "body": message,
                "status": "sent",
            })
            return True

        except ImportError:
            notification.mark_failed("twilio package not installed")
            logger.warning("Twilio package not installed")
            return False

        except Exception as e:
            notification.mark_failed(str(e))
            logger.error("SMS delivery failed: %s", e)
            return False

    def validate_recipient(self, recipient: str) -> bool:
        """Validate phone number format (E.164)."""
        return bool(PHONE_REGEX.match(recipient))

    def get_delivery_log(self) -> list[dict]:
        """Get delivery log."""
        return list(self._delivery_log)
