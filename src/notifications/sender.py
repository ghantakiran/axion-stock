"""Push notification sender."""

from datetime import datetime, timezone
from typing import Optional
import time

from src.notifications.config import (
    NotificationConfig,
    NotificationStatus,
    NotificationPriority,
    Platform,
    TokenType,
    DEFAULT_NOTIFICATION_CONFIG,
    CATEGORY_CONFIGS,
)
from src.notifications.models import (
    Device,
    Notification,
    NotificationResult,
    DeliveryStats,
)
from src.notifications.devices import DeviceManager
from src.notifications.preferences import PreferenceManager


class NotificationSender:
    """Sends push notifications to devices."""

    def __init__(
        self,
        device_manager: DeviceManager,
        preference_manager: PreferenceManager,
        config: Optional[NotificationConfig] = None,
    ):
        self.device_manager = device_manager
        self.preference_manager = preference_manager
        self.config = config or DEFAULT_NOTIFICATION_CONFIG
        self._stats = DeliveryStats()

    def send(self, notification: Notification) -> list[NotificationResult]:
        """Send notification to user's devices."""
        results = []

        # Check preferences
        allowed, reason = self.preference_manager.is_notification_allowed(
            notification.user_id,
            notification.category,
        )

        if not allowed:
            return [
                NotificationResult(
                    notification_id=notification.notification_id,
                    device_id="",
                    success=False,
                    status=NotificationStatus.FAILED,
                    error_code="preference_blocked",
                    error_message=reason,
                )
            ]

        # Get target devices
        if notification.device_id:
            device = self.device_manager.get_device(notification.device_id)
            devices = [device] if device and device.is_active else []
        else:
            devices = self.device_manager.get_user_devices(notification.user_id, active_only=True)

        if not devices:
            return [
                NotificationResult(
                    notification_id=notification.notification_id,
                    device_id="",
                    success=False,
                    status=NotificationStatus.FAILED,
                    error_code="no_devices",
                    error_message="No active devices for user",
                )
            ]

        # Send to each device
        for device in devices:
            result = self._send_to_device(notification, device)
            results.append(result)

            # Update stats
            if result.success:
                self._stats.total_sent += 1
                self._stats.total_delivered += 1
            else:
                self._stats.total_failed += 1

        # Record for rate limiting
        if any(r.success for r in results):
            self.preference_manager.record_notification_sent(
                notification.user_id,
                notification.category,
            )
            notification.mark_sent()

        return results

    def _send_to_device(self, notification: Notification, device: Device) -> NotificationResult:
        """Send notification to a specific device."""
        start_time = time.time()

        try:
            # Build payload
            payload = notification.to_push_payload()

            # Add platform-specific options
            payload = self._add_platform_options(payload, device, notification)

            # Simulate sending (in real implementation, call FCM/APNs)
            message_id = self._simulate_send(device, payload)

            latency_ms = int((time.time() - start_time) * 1000)

            # Mark device as used
            device.mark_used()

            return NotificationResult(
                notification_id=notification.notification_id,
                device_id=device.device_id,
                success=True,
                status=NotificationStatus.SENT,
                message_id=message_id,
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_code = type(e).__name__
            error_message = str(e)

            # Handle invalid token
            if "InvalidToken" in error_code or "NotRegistered" in str(e):
                device.deactivate()

            return NotificationResult(
                notification_id=notification.notification_id,
                device_id=device.device_id,
                success=False,
                status=NotificationStatus.FAILED,
                error_code=error_code,
                error_message=error_message,
                latency_ms=latency_ms,
            )

    def _add_platform_options(
        self,
        payload: dict,
        device: Device,
        notification: Notification,
    ) -> dict:
        """Add platform-specific options to payload."""
        category_config = CATEGORY_CONFIGS.get(notification.category, {})

        if device.platform == Platform.IOS:
            payload["apns"] = {
                "headers": {
                    "apns-priority": "10" if notification.priority == NotificationPriority.URGENT else "5",
                },
                "payload": {
                    "aps": {
                        "alert": payload["notification"],
                        "sound": category_config.get("sound", "default"),
                        "badge": 1,
                    }
                },
            }

        elif device.platform == Platform.ANDROID:
            payload["android"] = {
                "priority": "high" if notification.priority in [NotificationPriority.URGENT, NotificationPriority.HIGH] else "normal",
                "notification": {
                    "icon": category_config.get("icon", "notification_icon"),
                    "color": category_config.get("color", "#2196F3"),
                    "sound": category_config.get("sound", "default"),
                    "channel_id": notification.category.value,
                },
                "ttl": f"{category_config.get('ttl_seconds', 3600)}s",
            }

        elif device.platform == Platform.WEB:
            payload["webpush"] = {
                "headers": {
                    "Urgency": "high" if notification.priority == NotificationPriority.URGENT else "normal",
                    "TTL": str(category_config.get("ttl_seconds", 3600)),
                },
            }

        return payload

    def _simulate_send(self, device: Device, payload: dict) -> str:
        """Simulate sending notification (placeholder for real FCM/APNs calls)."""
        # In production, this would call:
        # - firebase_admin.messaging.send() for FCM
        # - APNs HTTP/2 API for iOS
        # - Web Push API for browsers

        import uuid
        return f"msg_{uuid.uuid4().hex[:12]}"

    def send_to_user(
        self,
        user_id: str,
        title: str,
        body: str,
        category: str,
        data: Optional[dict] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> list[NotificationResult]:
        """Convenience method to send notification to a user."""
        from src.notifications.config import NotificationCategory

        notification = Notification(
            user_id=user_id,
            category=NotificationCategory(category),
            title=title,
            body=body,
            data=data or {},
            priority=priority,
        )
        return self.send(notification)

    def send_test(self, user_id: str, device_id: Optional[str] = None) -> list[NotificationResult]:
        """Send a test notification."""
        from src.notifications.config import NotificationCategory

        notification = Notification(
            user_id=user_id,
            category=NotificationCategory.SYSTEM,
            title="Test Notification",
            body="This is a test notification from Axion.",
            device_id=device_id,
            priority=NotificationPriority.NORMAL,
            data={"type": "test"},
        )
        return self.send(notification)

    def send_bulk(self, notifications: list[Notification]) -> list[NotificationResult]:
        """Send multiple notifications."""
        all_results = []
        for notification in notifications:
            results = self.send(notification)
            all_results.extend(results)
        return all_results

    def get_stats(self) -> DeliveryStats:
        """Get delivery statistics."""
        self._stats.calculate_rates()
        return self._stats

    def reset_stats(self) -> None:
        """Reset delivery statistics."""
        self._stats = DeliveryStats()
