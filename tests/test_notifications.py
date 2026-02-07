"""Tests for PRD-60: Mobile Push Notifications."""

import pytest
from datetime import datetime, timezone, timedelta

from src.notifications.config import (
    NotificationCategory,
    NotificationPriority,
    NotificationStatus,
    Platform,
    TokenType,
    NotificationConfig,
    DEFAULT_NOTIFICATION_CONFIG,
    CATEGORY_CONFIGS,
)
from src.notifications.models import (
    Device,
    NotificationPreference,
    Notification,
    NotificationResult,
    DeliveryStats,
    PriceAlertPayload,
    TradeExecutionPayload,
    PortfolioUpdatePayload,
    RiskAlertPayload,
)
from src.notifications.devices import DeviceManager
from src.notifications.preferences import PreferenceManager
from src.notifications.sender import NotificationSender
from src.notifications.queue import NotificationQueue


class TestNotificationConfig:
    """Tests for notification configuration."""

    def test_notification_categories(self):
        """Test notification category enum."""
        assert NotificationCategory.PRICE_ALERTS.value == "price_alerts"
        assert NotificationCategory.TRADE_EXECUTIONS.value == "trade_executions"
        assert NotificationCategory.PORTFOLIO.value == "portfolio"
        assert NotificationCategory.RISK_ALERTS.value == "risk_alerts"

    def test_notification_priority(self):
        """Test priority levels."""
        assert NotificationPriority.URGENT.value == "urgent"
        assert NotificationPriority.HIGH.value == "high"
        assert NotificationPriority.NORMAL.value == "normal"
        assert NotificationPriority.LOW.value == "low"

    def test_platforms(self):
        """Test platform enum."""
        assert Platform.IOS.value == "ios"
        assert Platform.ANDROID.value == "android"
        assert Platform.WEB.value == "web"

    def test_token_types(self):
        """Test token type enum."""
        assert TokenType.FCM.value == "fcm"
        assert TokenType.APNS.value == "apns"
        assert TokenType.WEB_PUSH.value == "web_push"

    def test_default_config(self):
        """Test default configuration."""
        config = DEFAULT_NOTIFICATION_CONFIG
        assert config.max_retries > 0
        assert config.batch_size > 0
        assert config.max_per_user_per_hour > 0

    def test_category_configs(self):
        """Test category-specific configurations."""
        price_config = CATEGORY_CONFIGS.get(NotificationCategory.PRICE_ALERTS)
        assert price_config is not None
        assert "default_priority" in price_config
        assert "ttl_seconds" in price_config


class TestDevice:
    """Tests for device model."""

    def test_device_creation(self):
        """Test device creation."""
        device = Device(
            user_id="user123",
            device_token="token_abc123",
            platform=Platform.IOS,
            token_type=TokenType.APNS,
        )
        assert device.user_id == "user123"
        assert device.platform == Platform.IOS
        assert device.is_active

    def test_refresh_token(self):
        """Test token refresh."""
        device = Device(
            user_id="user123",
            device_token="old_token",
            platform=Platform.ANDROID,
            token_type=TokenType.FCM,
        )
        device.refresh_token("new_token")
        assert device.device_token == "new_token"
        assert device.token_refreshed_at is not None

    def test_mark_used(self):
        """Test marking device as used."""
        device = Device(
            user_id="user123",
            device_token="token",
            platform=Platform.IOS,
            token_type=TokenType.APNS,
        )
        device.mark_used()
        assert device.last_used_at is not None

    def test_deactivate(self):
        """Test device deactivation."""
        device = Device(
            user_id="user123",
            device_token="token",
            platform=Platform.IOS,
            token_type=TokenType.APNS,
        )
        device.deactivate()
        assert not device.is_active

    def test_device_to_dict(self):
        """Test device serialization."""
        device = Device(
            user_id="user123",
            device_token="token",
            platform=Platform.IOS,
            token_type=TokenType.APNS,
        )
        data = device.to_dict()
        assert data["user_id"] == "user123"
        assert data["platform"] == "ios"


class TestNotificationPreference:
    """Tests for notification preference model."""

    def test_preference_creation(self):
        """Test preference creation."""
        pref = NotificationPreference(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
        )
        assert pref.enabled
        assert pref.priority == NotificationPriority.NORMAL

    def test_quiet_hours_overnight(self):
        """Test overnight quiet hours detection."""
        pref = NotificationPreference(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            quiet_hours_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="08:00",
        )

        # 23:00 should be in quiet hours
        late_night = datetime(2025, 1, 15, 23, 0, tzinfo=timezone.utc)
        assert pref.is_in_quiet_hours(late_night)

        # 10:00 should not be in quiet hours
        morning = datetime(2025, 1, 15, 10, 0, tzinfo=timezone.utc)
        assert not pref.is_in_quiet_hours(morning)

    def test_quiet_hours_daytime(self):
        """Test daytime quiet hours detection."""
        pref = NotificationPreference(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            quiet_hours_enabled=True,
            quiet_hours_start="09:00",
            quiet_hours_end="17:00",
        )

        # 12:00 should be in quiet hours
        noon = datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)
        assert pref.is_in_quiet_hours(noon)

        # 20:00 should not be in quiet hours
        evening = datetime(2025, 1, 15, 20, 0, tzinfo=timezone.utc)
        assert not pref.is_in_quiet_hours(evening)

    def test_quiet_hours_disabled(self):
        """Test quiet hours when disabled."""
        pref = NotificationPreference(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            quiet_hours_enabled=False,
            quiet_hours_start="22:00",
            quiet_hours_end="08:00",
        )

        late_night = datetime(2025, 1, 15, 23, 0, tzinfo=timezone.utc)
        assert not pref.is_in_quiet_hours(late_night)


class TestNotification:
    """Tests for notification model."""

    def test_notification_creation(self):
        """Test notification creation."""
        notification = Notification(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            title="AAPL Alert",
            body="AAPL reached $190.00",
        )
        assert notification.status == NotificationStatus.PENDING
        assert notification.priority == NotificationPriority.NORMAL

    def test_notification_expiration(self):
        """Test notification expiration check."""
        notification = Notification(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            title="Test",
            body="Test",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert notification.is_expired()

    def test_notification_not_expired(self):
        """Test non-expired notification."""
        notification = Notification(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            title="Test",
            body="Test",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert not notification.is_expired()

    def test_mark_sent(self):
        """Test marking notification as sent."""
        notification = Notification(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            title="Test",
            body="Test",
        )
        notification.mark_sent()
        assert notification.status == NotificationStatus.SENT
        assert notification.sent_at is not None

    def test_to_push_payload(self):
        """Test push payload generation."""
        notification = Notification(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            title="AAPL Alert",
            body="Price reached $190",
            data={"symbol": "AAPL"},
        )
        payload = notification.to_push_payload()
        assert payload["notification"]["title"] == "AAPL Alert"
        assert payload["data"]["category"] == "price_alerts"
        assert payload["data"]["symbol"] == "AAPL"


class TestNotificationPayloads:
    """Tests for notification payload helpers."""

    def test_price_alert_payload(self):
        """Test price alert payload."""
        payload = PriceAlertPayload(
            symbol="AAPL",
            current_price=190.50,
            target_price=189.50,
            direction="above",
            alert_id="alert123",
        )
        notification = payload.to_notification("user123")
        assert notification.category == NotificationCategory.PRICE_ALERTS
        assert "AAPL" in notification.title
        assert notification.data["symbol"] == "AAPL"

    def test_trade_execution_payload(self):
        """Test trade execution payload."""
        payload = TradeExecutionPayload(
            order_id="ord123",
            symbol="MSFT",
            side="buy",
            quantity=100,
            status="filled",
            fill_price=420.50,
        )
        notification = payload.to_notification("user123")
        assert notification.category == NotificationCategory.TRADE_EXECUTIONS
        assert notification.priority == NotificationPriority.URGENT

    def test_portfolio_update_payload(self):
        """Test portfolio update payload."""
        payload = PortfolioUpdatePayload(
            total_value=100000.0,
            day_pnl=1234.50,
            day_return_pct=1.25,
        )
        notification = payload.to_notification("user123")
        assert notification.category == NotificationCategory.PORTFOLIO
        assert "+$1,234.50" in notification.body

    def test_risk_alert_payload(self):
        """Test risk alert payload."""
        payload = RiskAlertPayload(
            alert_type="stop_loss",
            symbol="NVDA",
            message="Stop-loss triggered at $845",
        )
        notification = payload.to_notification("user123")
        assert notification.category == NotificationCategory.RISK_ALERTS
        assert notification.priority == NotificationPriority.URGENT


class TestDeviceManager:
    """Tests for device manager."""

    def test_register_device(self):
        """Test device registration."""
        manager = DeviceManager()
        device = manager.register_device(
            user_id="user123",
            device_token="token_abc",
            platform=Platform.IOS,
        )
        assert device.user_id == "user123"
        assert device.platform == Platform.IOS
        assert device.token_type == TokenType.APNS

    def test_register_android_device(self):
        """Test Android device auto-detects FCM."""
        manager = DeviceManager()
        device = manager.register_device(
            user_id="user123",
            device_token="token_xyz",
            platform=Platform.ANDROID,
        )
        assert device.token_type == TokenType.FCM

    def test_get_device(self):
        """Test getting device by ID."""
        manager = DeviceManager()
        device = manager.register_device(
            user_id="user123",
            device_token="token_abc",
            platform=Platform.IOS,
        )
        retrieved = manager.get_device(device.device_id)
        assert retrieved == device

    def test_get_user_devices(self):
        """Test getting all devices for a user."""
        manager = DeviceManager()
        manager.register_device("user123", "token1", Platform.IOS)
        manager.register_device("user123", "token2", Platform.ANDROID)
        manager.register_device("user456", "token3", Platform.IOS)

        devices = manager.get_user_devices("user123")
        assert len(devices) == 2

    def test_unregister_device(self):
        """Test device unregistration."""
        manager = DeviceManager()
        device = manager.register_device(
            user_id="user123",
            device_token="token_abc",
            platform=Platform.IOS,
        )
        result = manager.unregister_device(device.device_id)
        assert result
        assert manager.get_device(device.device_id) is None

    def test_refresh_token(self):
        """Test token refresh."""
        manager = DeviceManager()
        device = manager.register_device(
            user_id="user123",
            device_token="old_token",
            platform=Platform.IOS,
        )
        result = manager.refresh_token(device.device_id, "new_token")
        assert result
        assert device.device_token == "new_token"

    def test_mark_token_invalid(self):
        """Test marking invalid token."""
        manager = DeviceManager()
        device = manager.register_device(
            user_id="user123",
            device_token="bad_token",
            platform=Platform.IOS,
        )
        result = manager.mark_token_invalid("bad_token")
        assert result
        assert not device.is_active

    def test_get_stats(self):
        """Test device statistics."""
        manager = DeviceManager()
        manager.register_device("user1", "token1", Platform.IOS)
        manager.register_device("user2", "token2", Platform.ANDROID)

        stats = manager.get_stats()
        assert stats["total_devices"] == 2
        assert stats["active_devices"] == 2
        assert stats["unique_users"] == 2


class TestPreferenceManager:
    """Tests for preference manager."""

    def test_get_default_preference(self):
        """Test getting default preference."""
        manager = PreferenceManager()
        pref = manager.get_preference("user123", NotificationCategory.PRICE_ALERTS)
        assert pref.enabled
        assert pref.category == NotificationCategory.PRICE_ALERTS

    def test_update_preference(self):
        """Test updating preference."""
        manager = PreferenceManager()
        pref = manager.update_preference(
            user_id="user123",
            category=NotificationCategory.NEWS,
            enabled=False,
            priority=NotificationPriority.LOW,
        )
        assert not pref.enabled
        assert pref.priority == NotificationPriority.LOW

    def test_set_quiet_hours(self):
        """Test setting quiet hours."""
        manager = PreferenceManager()
        count = manager.set_quiet_hours(
            user_id="user123",
            start="22:00",
            end="08:00",
        )
        assert count > 0

        pref = manager.get_preference("user123", NotificationCategory.PRICE_ALERTS)
        assert pref.quiet_hours_enabled
        assert pref.quiet_hours_start == "22:00"

    def test_disable_quiet_hours(self):
        """Test disabling quiet hours."""
        manager = PreferenceManager()
        manager.set_quiet_hours("user123", "22:00", "08:00")
        count = manager.disable_quiet_hours("user123")
        assert count > 0

        pref = manager.get_preference("user123", NotificationCategory.PRICE_ALERTS)
        assert not pref.quiet_hours_enabled

    def test_enable_disable_category(self):
        """Test enabling/disabling categories."""
        manager = PreferenceManager()
        manager.disable_category("user123", NotificationCategory.NEWS)
        pref = manager.get_preference("user123", NotificationCategory.NEWS)
        assert not pref.enabled

        manager.enable_category("user123", NotificationCategory.NEWS)
        pref = manager.get_preference("user123", NotificationCategory.NEWS)
        assert pref.enabled

    def test_is_notification_allowed(self):
        """Test notification allowed check."""
        manager = PreferenceManager()
        allowed, reason = manager.is_notification_allowed(
            "user123",
            NotificationCategory.PRICE_ALERTS,
        )
        assert allowed
        assert reason == "allowed"

    def test_notification_blocked_by_preference(self):
        """Test notification blocked when disabled."""
        manager = PreferenceManager()
        manager.disable_category("user123", NotificationCategory.NEWS)

        allowed, reason = manager.is_notification_allowed(
            "user123",
            NotificationCategory.NEWS,
        )
        assert not allowed
        assert reason == "category_disabled"

    def test_get_enabled_categories(self):
        """Test getting enabled categories."""
        manager = PreferenceManager()
        manager.disable_category("user123", NotificationCategory.NEWS)
        manager.disable_category("user123", NotificationCategory.DIVIDENDS)

        enabled = manager.get_enabled_categories("user123")
        assert NotificationCategory.PRICE_ALERTS in enabled
        assert NotificationCategory.NEWS not in enabled


class TestNotificationQueue:
    """Tests for notification queue."""

    def test_enqueue(self):
        """Test enqueuing notification."""
        queue = NotificationQueue()
        notification = Notification(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            title="Test",
            body="Test",
        )
        result = queue.enqueue(notification)
        assert result
        assert notification.status == NotificationStatus.QUEUED

    def test_dequeue(self):
        """Test dequeuing notification."""
        queue = NotificationQueue()
        notification = Notification(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            title="Test",
            body="Test",
        )
        queue.enqueue(notification)

        dequeued = queue.dequeue()
        assert dequeued == notification
        assert dequeued.status == NotificationStatus.SENDING

    def test_priority_ordering(self):
        """Test priority-based ordering."""
        queue = NotificationQueue()

        low = Notification(
            user_id="user123",
            category=NotificationCategory.SYSTEM,
            title="Low",
            body="Low priority",
            priority=NotificationPriority.LOW,
        )
        urgent = Notification(
            user_id="user123",
            category=NotificationCategory.RISK_ALERTS,
            title="Urgent",
            body="Urgent priority",
            priority=NotificationPriority.URGENT,
        )

        queue.enqueue(low)
        queue.enqueue(urgent)

        first = queue.dequeue()
        assert first.priority == NotificationPriority.URGENT

    def test_mark_success(self):
        """Test marking notification as successful."""
        queue = NotificationQueue()
        notification = Notification(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            title="Test",
            body="Test",
        )
        queue.enqueue(notification)
        queue.dequeue()

        result = queue.mark_success(notification.notification_id)
        assert result
        assert queue.get_pending_count() == 0

    def test_mark_failed_with_retry(self):
        """Test failed notification scheduled for retry."""
        config = NotificationConfig(max_retries=3, retry_delay_seconds=1)
        queue = NotificationQueue(config=config)

        notification = Notification(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            title="Test",
            body="Test",
        )
        queue.enqueue(notification)
        queue.dequeue()

        result = queue.mark_failed(notification.notification_id, "Network error")
        assert result  # Scheduled for retry
        assert queue.get_pending_count() == 1

    def test_mark_failed_max_retries(self):
        """Test failed notification moved to dead letter after max retries."""
        config = NotificationConfig(max_retries=1, retry_delay_seconds=0)
        queue = NotificationQueue(config=config)

        notification = Notification(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            title="Test",
            body="Test",
        )
        queue.enqueue(notification)
        queue.dequeue()
        queue.mark_failed(notification.notification_id, "Error 1")

        # Dequeue retry
        import time
        time.sleep(0.01)
        queue.dequeue()
        result = queue.mark_failed(notification.notification_id, "Error 2")

        assert not result  # Moved to dead letter
        assert queue.get_dead_letter_count() == 1

    def test_cancel_notification(self):
        """Test cancelling notification."""
        queue = NotificationQueue()
        notification = Notification(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            title="Test",
            body="Test",
        )
        queue.enqueue(notification)

        result = queue.cancel(notification.notification_id)
        assert result
        assert queue.get_pending_count() == 0

    def test_get_user_pending(self):
        """Test getting pending notifications for user."""
        queue = NotificationQueue()

        n1 = Notification(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            title="Test 1",
            body="Test",
        )
        n2 = Notification(
            user_id="user456",
            category=NotificationCategory.PRICE_ALERTS,
            title="Test 2",
            body="Test",
        )

        queue.enqueue(n1)
        queue.enqueue(n2)

        pending = queue.get_user_pending("user123")
        assert len(pending) == 1
        assert pending[0] == n1

    def test_get_stats(self):
        """Test queue statistics."""
        queue = NotificationQueue()

        for i in range(5):
            notification = Notification(
                user_id="user123",
                category=NotificationCategory.PRICE_ALERTS,
                title=f"Test {i}",
                body="Test",
            )
            queue.enqueue(notification)

        stats = queue.get_stats()
        assert stats["pending_count"] == 5
        assert stats["queue_size"] == 5


class TestNotificationSender:
    """Tests for notification sender."""

    def test_send_notification(self):
        """Test sending notification."""
        device_manager = DeviceManager()
        pref_manager = PreferenceManager()
        sender = NotificationSender(device_manager, pref_manager)

        device_manager.register_device("user123", "token_abc", Platform.IOS)

        notification = Notification(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            title="Test",
            body="Test notification",
        )

        results = sender.send(notification)
        assert len(results) == 1
        assert results[0].success

    def test_send_to_multiple_devices(self):
        """Test sending to multiple devices."""
        device_manager = DeviceManager()
        pref_manager = PreferenceManager()
        sender = NotificationSender(device_manager, pref_manager)

        device_manager.register_device("user123", "token1", Platform.IOS)
        device_manager.register_device("user123", "token2", Platform.ANDROID)

        notification = Notification(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            title="Test",
            body="Test",
        )

        results = sender.send(notification)
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_send_blocked_by_preference(self):
        """Test send blocked by user preference."""
        device_manager = DeviceManager()
        pref_manager = PreferenceManager()
        sender = NotificationSender(device_manager, pref_manager)

        device_manager.register_device("user123", "token_abc", Platform.IOS)
        pref_manager.disable_category("user123", NotificationCategory.NEWS)

        notification = Notification(
            user_id="user123",
            category=NotificationCategory.NEWS,
            title="Test",
            body="Test",
        )

        results = sender.send(notification)
        assert len(results) == 1
        assert not results[0].success
        assert results[0].error_code == "preference_blocked"

    def test_send_no_devices(self):
        """Test send when user has no devices."""
        device_manager = DeviceManager()
        pref_manager = PreferenceManager()
        sender = NotificationSender(device_manager, pref_manager)

        notification = Notification(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            title="Test",
            body="Test",
        )

        results = sender.send(notification)
        assert len(results) == 1
        assert not results[0].success
        assert results[0].error_code == "no_devices"

    def test_send_test_notification(self):
        """Test sending test notification."""
        device_manager = DeviceManager()
        pref_manager = PreferenceManager()
        sender = NotificationSender(device_manager, pref_manager)

        device_manager.register_device("user123", "token_abc", Platform.IOS)

        results = sender.send_test("user123")
        assert len(results) == 1
        assert results[0].success

    def test_get_stats(self):
        """Test delivery statistics."""
        device_manager = DeviceManager()
        pref_manager = PreferenceManager()
        sender = NotificationSender(device_manager, pref_manager)

        device_manager.register_device("user123", "token_abc", Platform.IOS)

        notification = Notification(
            user_id="user123",
            category=NotificationCategory.PRICE_ALERTS,
            title="Test",
            body="Test",
        )
        sender.send(notification)

        stats = sender.get_stats()
        assert stats.total_sent == 1
        assert stats.total_delivered == 1


class TestDeliveryStats:
    """Tests for delivery statistics."""

    def test_calculate_rates(self):
        """Test rate calculations."""
        stats = DeliveryStats(
            total_sent=100,
            total_delivered=95,
            total_opened=50,
        )
        stats.calculate_rates()

        assert stats.delivery_rate == 0.95
        assert pytest.approx(stats.open_rate, abs=0.01) == 0.526

    def test_to_dict(self):
        """Test stats serialization."""
        stats = DeliveryStats(
            total_sent=100,
            total_delivered=95,
            total_opened=50,
        )
        stats.calculate_rates()

        data = stats.to_dict()
        assert data["total_sent"] == 100
        assert data["delivery_rate"] == 95.0
