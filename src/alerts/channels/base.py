"""Abstract base for delivery channels."""

from abc import ABC, abstractmethod

from src.alerts.models import Notification


class DeliveryChannel(ABC):
    """Abstract delivery channel interface."""

    @abstractmethod
    def send(self, notification: Notification) -> bool:
        """Send a notification through this channel.

        Args:
            notification: Notification to deliver.

        Returns:
            True if delivery was successful.
        """

    @abstractmethod
    def validate_recipient(self, recipient: str) -> bool:
        """Validate that the recipient is valid for this channel.

        Args:
            recipient: Channel-specific recipient identifier.

        Returns:
            True if recipient is valid.
        """
