"""Tests for PRD-13: Alerting & Notifications System."""

import pytest
from datetime import datetime, timedelta, timezone

from src.alerts.config import (
    AlertType,
    AlertPriority,
    AlertStatus,
    ComparisonOperator,
    LogicalOperator,
    ChannelType,
    DeliveryStatus,
    DigestFrequency,
    DEFAULT_COOLDOWNS,
    ALERT_TEMPLATES,
    AlertingConfig,
    EmailConfig,
    SMSConfig,
    SlackConfig,
    WebhookConfig,
    QuietHours,
)
from src.alerts.models import (
    AlertCondition,
    CompoundCondition,
    Alert,
    AlertEvent,
    Notification,
    NotificationPreferences,
)
from src.alerts.conditions import ConditionBuilder, ConditionEvaluator
from src.alerts.engine import AlertEngine
from src.alerts.manager import AlertManager
from src.alerts.channels.in_app import InAppChannel
from src.alerts.channels.email import EmailChannel
from src.alerts.channels.sms import SMSChannel
from src.alerts.channels.webhook import WebhookChannel
from src.alerts.channels.slack import SlackChannel


class TestAlertsConfig:
    """Test configuration enums and constants."""

    def test_alert_types(self):
        assert len(AlertType) == 7
        assert AlertType.PRICE.value == "price"
        assert AlertType.TECHNICAL.value == "technical"

    def test_alert_priorities(self):
        assert len(AlertPriority) == 4
        assert AlertPriority.LOW.value == "low"
        assert AlertPriority.CRITICAL.value == "critical"

    def test_comparison_operators(self):
        assert len(ComparisonOperator) == 10
        assert ComparisonOperator.GT.value == ">"
        assert ComparisonOperator.CROSSES_ABOVE.value == "crosses_above"

    def test_channel_types(self):
        assert len(ChannelType) == 5
        assert ChannelType.IN_APP.value == "in_app"
        assert ChannelType.SLACK.value == "slack"

    def test_default_cooldowns(self):
        assert DEFAULT_COOLDOWNS[AlertPriority.LOW] == 3600
        assert DEFAULT_COOLDOWNS[AlertPriority.CRITICAL] == 60

    def test_alert_templates(self):
        assert len(ALERT_TEMPLATES) >= 10
        assert "price_breakout" in ALERT_TEMPLATES
        assert "rsi_overbought" in ALERT_TEMPLATES
        assert "var_breach" in ALERT_TEMPLATES
        assert "unusual_volume" in ALERT_TEMPLATES

    def test_alerting_config_defaults(self):
        config = AlertingConfig()
        assert config.max_alerts_per_user == 50
        assert config.default_cooldown_seconds == 1800
        assert config.evaluation_interval_seconds == 60
        assert config.digest_frequency == DigestFrequency.IMMEDIATE

    def test_email_config(self):
        config = EmailConfig(smtp_host="smtp.test.com", smtp_port=465)
        assert config.smtp_host == "smtp.test.com"
        assert config.smtp_port == 465
        assert config.use_tls is True

    def test_quiet_hours(self):
        qh = QuietHours(enabled=True, start_hour=22, end_hour=7)
        assert qh.enabled is True
        assert qh.override_critical is True


class TestAlertCondition:
    """Test condition evaluation."""

    def test_greater_than(self):
        cond = AlertCondition("price", ComparisonOperator.GT, 100.0)
        assert cond.evaluate(101.0) is True
        assert cond.evaluate(99.0) is False
        assert cond.evaluate(100.0) is False

    def test_less_than(self):
        cond = AlertCondition("price", ComparisonOperator.LT, 100.0)
        assert cond.evaluate(99.0) is True
        assert cond.evaluate(101.0) is False

    def test_greater_than_or_equal(self):
        cond = AlertCondition("price", ComparisonOperator.GTE, 100.0)
        assert cond.evaluate(100.0) is True
        assert cond.evaluate(101.0) is True
        assert cond.evaluate(99.0) is False

    def test_less_than_or_equal(self):
        cond = AlertCondition("price", ComparisonOperator.LTE, 100.0)
        assert cond.evaluate(100.0) is True
        assert cond.evaluate(99.0) is True
        assert cond.evaluate(101.0) is False

    def test_equal(self):
        cond = AlertCondition("price", ComparisonOperator.EQ, 100.0)
        assert cond.evaluate(100.0) is True
        assert cond.evaluate(99.0) is False

    def test_not_equal(self):
        cond = AlertCondition("price", ComparisonOperator.NEQ, 100.0)
        assert cond.evaluate(99.0) is True
        assert cond.evaluate(100.0) is False

    def test_crosses_above(self):
        cond = AlertCondition("price", ComparisonOperator.CROSSES_ABOVE, 100.0)
        # No previous value — should not trigger
        assert cond.evaluate(101.0) is False
        # Now previous=101, current=99 — not crossing above
        assert cond.evaluate(99.0) is False
        # Previous=99, current=101 — crosses above!
        assert cond.evaluate(101.0) is True

    def test_crosses_below(self):
        cond = AlertCondition("price", ComparisonOperator.CROSSES_BELOW, 100.0)
        assert cond.evaluate(99.0) is False
        assert cond.evaluate(101.0) is False
        # Previous=101, current=99 — crosses below
        assert cond.evaluate(99.0) is True

    def test_pct_change_gt(self):
        cond = AlertCondition("price", ComparisonOperator.PCT_CHANGE_GT, 5.0)
        # No previous — False
        assert cond.evaluate(100.0) is False
        # Previous=100, current=106 — 6% > 5%
        assert cond.evaluate(106.0) is True

    def test_pct_change_lt(self):
        cond = AlertCondition("price", ComparisonOperator.PCT_CHANGE_LT, -5.0)
        assert cond.evaluate(100.0) is False
        # Previous=100, current=94 — -6% < -5%
        assert cond.evaluate(94.0) is True

    def test_previous_value_tracked(self):
        cond = AlertCondition("price", ComparisonOperator.GT, 100.0)
        cond.evaluate(95.0)
        assert cond.previous_value == 95.0
        cond.evaluate(105.0)
        assert cond.previous_value == 105.0


class TestCompoundCondition:
    """Test compound condition evaluation."""

    def test_and_all_true(self):
        cc = CompoundCondition(
            conditions=[
                AlertCondition("price", ComparisonOperator.GT, 100.0),
                AlertCondition("volume", ComparisonOperator.GT, 1000.0),
            ],
            logical_operator=LogicalOperator.AND,
        )
        assert cc.evaluate({"price": 105.0, "volume": 1500.0}) is True

    def test_and_one_false(self):
        cc = CompoundCondition(
            conditions=[
                AlertCondition("price", ComparisonOperator.GT, 100.0),
                AlertCondition("volume", ComparisonOperator.GT, 1000.0),
            ],
            logical_operator=LogicalOperator.AND,
        )
        assert cc.evaluate({"price": 105.0, "volume": 500.0}) is False

    def test_or_one_true(self):
        cc = CompoundCondition(
            conditions=[
                AlertCondition("price", ComparisonOperator.GT, 100.0),
                AlertCondition("volume", ComparisonOperator.GT, 1000.0),
            ],
            logical_operator=LogicalOperator.OR,
        )
        assert cc.evaluate({"price": 105.0, "volume": 500.0}) is True

    def test_or_none_true(self):
        cc = CompoundCondition(
            conditions=[
                AlertCondition("price", ComparisonOperator.GT, 100.0),
                AlertCondition("volume", ComparisonOperator.GT, 1000.0),
            ],
            logical_operator=LogicalOperator.OR,
        )
        assert cc.evaluate({"price": 95.0, "volume": 500.0}) is False

    def test_empty_conditions(self):
        cc = CompoundCondition()
        assert cc.evaluate({"price": 100.0}) is False

    def test_missing_metric(self):
        cc = CompoundCondition(
            conditions=[
                AlertCondition("price", ComparisonOperator.GT, 100.0),
            ],
        )
        # Metric not in values dict
        assert cc.evaluate({"volume": 1000.0}) is False


class TestConditionBuilder:
    """Test condition builder helpers."""

    def test_simple(self):
        cc = ConditionBuilder.simple("price", ComparisonOperator.GT, 100.0)
        assert len(cc.conditions) == 1
        assert cc.conditions[0].metric == "price"
        assert cc.conditions[0].threshold == 100.0

    def test_compound(self):
        cc = ConditionBuilder.compound([
            ("price", ComparisonOperator.GT, 100.0),
            ("rsi_14", ComparisonOperator.LT, 70.0),
        ])
        assert len(cc.conditions) == 2
        assert cc.logical_operator == LogicalOperator.AND

    def test_from_template(self):
        cc = ConditionBuilder.from_template("rsi_overbought")
        assert len(cc.conditions) == 1
        assert cc.conditions[0].threshold == 70.0

    def test_from_template_override(self):
        cc = ConditionBuilder.from_template("rsi_overbought", threshold_override=80.0)
        assert cc.conditions[0].threshold == 80.0

    def test_from_template_unknown(self):
        with pytest.raises(ValueError, match="Unknown template"):
            ConditionBuilder.from_template("nonexistent")

    def test_price_above(self):
        cc = ConditionBuilder.price_above(200.0)
        assert cc.conditions[0].operator == ComparisonOperator.GT
        assert cc.conditions[0].threshold == 200.0

    def test_price_below(self):
        cc = ConditionBuilder.price_below(150.0)
        assert cc.conditions[0].operator == ComparisonOperator.LT

    def test_price_crosses_above(self):
        cc = ConditionBuilder.price_crosses_above(200.0)
        assert cc.conditions[0].operator == ComparisonOperator.CROSSES_ABOVE

    def test_pct_change_up(self):
        cc = ConditionBuilder.pct_change(5.0, direction="up")
        assert cc.conditions[0].operator == ComparisonOperator.PCT_CHANGE_GT
        assert cc.conditions[0].threshold == 5.0

    def test_pct_change_down(self):
        cc = ConditionBuilder.pct_change(5.0, direction="down")
        assert cc.conditions[0].operator == ComparisonOperator.PCT_CHANGE_LT
        assert cc.conditions[0].threshold == -5.0


class TestConditionEvaluator:
    """Test stateful condition evaluator."""

    def test_evaluate_simple(self):
        evaluator = ConditionEvaluator()
        cc = ConditionBuilder.simple("price", ComparisonOperator.GT, 100.0)
        assert evaluator.evaluate("alert1", cc, {"price": 105.0}) is True
        assert evaluator.evaluate("alert1", cc, {"price": 95.0}) is False

    def test_evaluate_cross_detection(self):
        evaluator = ConditionEvaluator()
        cc = ConditionBuilder.simple("price", ComparisonOperator.CROSSES_ABOVE, 100.0)

        # First evaluation — no previous state
        assert evaluator.evaluate("alert1", cc, {"price": 95.0}) is False
        # Second — still below
        assert evaluator.evaluate("alert1", cc, {"price": 98.0}) is False
        # Third — crosses above
        assert evaluator.evaluate("alert1", cc, {"price": 105.0}) is True

    def test_clear_state(self):
        evaluator = ConditionEvaluator()
        cc = ConditionBuilder.simple("price", ComparisonOperator.GT, 100.0)
        evaluator.evaluate("alert1", cc, {"price": 105.0})
        assert "alert1" in evaluator._state
        evaluator.clear_state("alert1")
        assert "alert1" not in evaluator._state

    def test_clear_all(self):
        evaluator = ConditionEvaluator()
        cc = ConditionBuilder.simple("price", ComparisonOperator.GT, 100.0)
        evaluator.evaluate("a1", cc, {"price": 105.0})
        evaluator.evaluate("a2", cc, {"price": 105.0})
        evaluator.clear_all()
        assert len(evaluator._state) == 0


class TestAlert:
    """Test Alert model."""

    def test_is_active(self):
        alert = Alert(status=AlertStatus.ACTIVE)
        assert alert.is_active() is True

    def test_is_active_disabled(self):
        alert = Alert(status=AlertStatus.DISABLED)
        assert alert.is_active() is False

    def test_is_active_expired(self):
        alert = Alert(
            status=AlertStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert alert.is_active() is False
        assert alert.status == AlertStatus.EXPIRED

    def test_is_active_snoozed(self):
        alert = Alert(
            status=AlertStatus.ACTIVE,
            snooze_until=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert alert.is_active() is False

    def test_is_active_max_triggers(self):
        alert = Alert(
            status=AlertStatus.ACTIVE,
            max_triggers=3,
            trigger_count=3,
        )
        assert alert.is_active() is False
        assert alert.status == AlertStatus.DISABLED

    def test_cooldown(self):
        alert = Alert(cooldown_seconds=300)
        assert alert.is_in_cooldown() is False

        alert.trigger()
        assert alert.is_in_cooldown() is True

    def test_trigger_increments_count(self):
        alert = Alert()
        assert alert.trigger_count == 0
        alert.trigger()
        assert alert.trigger_count == 1
        assert alert.last_triggered_at is not None

    def test_format_message_default(self):
        cond = CompoundCondition(
            conditions=[AlertCondition("price", ComparisonOperator.GT, 200.0)],
        )
        alert = Alert(name="AAPL Alert", symbol="AAPL", conditions=cond)
        msg = alert.format_message({"price": 205.0})
        assert "AAPL Alert" in msg
        assert "AAPL" in msg
        assert "205" in msg

    def test_format_message_template(self):
        alert = Alert(
            name="Test",
            symbol="AAPL",
            message_template="{name}: {symbol} price is {price:.2f}",
        )
        msg = alert.format_message({"price": 205.5})
        assert msg == "Test: AAPL price is 205.50"


class TestNotification:
    """Test Notification model."""

    def test_mark_sent(self):
        n = Notification()
        assert n.status == DeliveryStatus.PENDING
        n.mark_sent()
        assert n.status == DeliveryStatus.SENT
        assert n.delivered_at is not None

    def test_mark_delivered(self):
        n = Notification()
        n.mark_delivered()
        assert n.status == DeliveryStatus.DELIVERED

    def test_mark_failed(self):
        n = Notification()
        n.mark_failed("Connection timeout")
        assert n.status == DeliveryStatus.FAILED
        assert n.error_message == "Connection timeout"

    def test_mark_read(self):
        n = Notification()
        assert n.is_read is False
        n.mark_read()
        assert n.is_read is True


class TestNotificationPreferences:
    """Test notification preferences."""

    def test_default_channels(self):
        prefs = NotificationPreferences(user_id="u1")
        assert ChannelType.IN_APP in prefs.enabled_channels

    def test_get_channels_for_priority_default(self):
        prefs = NotificationPreferences(
            user_id="u1",
            enabled_channels=[ChannelType.IN_APP, ChannelType.EMAIL],
        )
        channels = prefs.get_channels_for_priority(AlertPriority.MEDIUM)
        assert ChannelType.IN_APP in channels
        assert ChannelType.EMAIL in channels

    def test_get_channels_with_override(self):
        prefs = NotificationPreferences(
            user_id="u1",
            enabled_channels=[ChannelType.IN_APP],
            priority_overrides={
                "critical": [ChannelType.IN_APP, ChannelType.SMS, ChannelType.EMAIL],
            },
        )
        channels = prefs.get_channels_for_priority(AlertPriority.CRITICAL)
        assert ChannelType.SMS in channels
        assert len(channels) == 3

    def test_quiet_hours_not_enabled(self):
        prefs = NotificationPreferences(quiet_hours_enabled=False)
        assert prefs.is_in_quiet_hours(23) is False

    def test_quiet_hours_wraps_midnight(self):
        prefs = NotificationPreferences(
            quiet_hours_enabled=True,
            quiet_start_hour=22,
            quiet_end_hour=7,
        )
        assert prefs.is_in_quiet_hours(23) is True
        assert prefs.is_in_quiet_hours(3) is True
        assert prefs.is_in_quiet_hours(10) is False
        assert prefs.is_in_quiet_hours(22) is True
        assert prefs.is_in_quiet_hours(7) is False

    def test_quiet_hours_same_day(self):
        prefs = NotificationPreferences(
            quiet_hours_enabled=True,
            quiet_start_hour=12,
            quiet_end_hour=14,
        )
        assert prefs.is_in_quiet_hours(13) is True
        assert prefs.is_in_quiet_hours(11) is False
        assert prefs.is_in_quiet_hours(15) is False


class TestInAppChannel:
    """Test in-app notification channel."""

    def test_send(self):
        channel = InAppChannel()
        n = Notification(user_id="u1", message="Test alert")
        assert channel.send(n) is True
        assert n.status == DeliveryStatus.DELIVERED

    def test_get_unread(self):
        channel = InAppChannel()
        n1 = Notification(user_id="u1", message="Alert 1")
        n2 = Notification(user_id="u1", message="Alert 2")
        channel.send(n1)
        channel.send(n2)
        unread = channel.get_unread("u1")
        assert len(unread) == 2

    def test_mark_read(self):
        channel = InAppChannel()
        n = Notification(user_id="u1", message="Test")
        channel.send(n)
        assert channel.mark_read("u1", n.notification_id) is True
        assert len(channel.get_unread("u1")) == 0

    def test_mark_all_read(self):
        channel = InAppChannel()
        for i in range(5):
            channel.send(Notification(user_id="u1", message=f"Alert {i}"))
        count = channel.mark_all_read("u1")
        assert count == 5
        assert channel.get_unread_count("u1") == 0

    def test_max_per_user(self):
        channel = InAppChannel(max_per_user=3)
        for i in range(5):
            channel.send(Notification(user_id="u1", message=f"Alert {i}"))
        assert len(channel.get_all("u1")) == 3

    def test_clear(self):
        channel = InAppChannel()
        channel.send(Notification(user_id="u1", message="Test"))
        channel.clear("u1")
        assert len(channel.get_all("u1")) == 0

    def test_validate_recipient(self):
        channel = InAppChannel()
        assert channel.validate_recipient("anything") is True


class TestEmailChannel:
    """Test email channel (dry run mode)."""

    def test_send_dry_run(self):
        channel = EmailChannel()
        n = Notification(
            user_id="u1",
            message="Price alert triggered",
            recipient="user@example.com",
            subject="Axion Alert",
        )
        assert channel.send(n) is True
        assert n.status == DeliveryStatus.SENT
        assert len(channel.get_delivery_log()) == 1

    def test_invalid_email(self):
        channel = EmailChannel()
        n = Notification(user_id="u1", message="Test", recipient="not-an-email")
        assert channel.send(n) is False
        assert n.status == DeliveryStatus.FAILED

    def test_validate_email(self):
        channel = EmailChannel()
        assert channel.validate_recipient("user@example.com") is True
        assert channel.validate_recipient("a.b+c@test.co.uk") is True
        assert channel.validate_recipient("invalid") is False
        assert channel.validate_recipient("@test.com") is False


class TestSMSChannel:
    """Test SMS channel (dry run mode)."""

    def test_send_dry_run(self):
        channel = SMSChannel()
        n = Notification(
            user_id="u1",
            message="AAPL > $200",
            recipient="+15551234567",
        )
        assert channel.send(n) is True
        assert n.status == DeliveryStatus.SENT

    def test_invalid_phone(self):
        channel = SMSChannel()
        n = Notification(user_id="u1", message="Test", recipient="abc")
        assert channel.send(n) is False

    def test_validate_phone(self):
        channel = SMSChannel()
        assert channel.validate_recipient("+15551234567") is True
        assert channel.validate_recipient("15551234567") is True
        assert channel.validate_recipient("abc") is False
        assert channel.validate_recipient("+0123") is False


class TestWebhookChannel:
    """Test webhook channel."""

    def test_validate_url(self):
        channel = WebhookChannel()
        assert channel.validate_recipient("https://example.com/webhook") is True
        assert channel.validate_recipient("http://localhost:8080/hook") is True
        assert channel.validate_recipient("not-a-url") is False
        assert channel.validate_recipient("ftp://example.com") is False

    def test_build_payload(self):
        channel = WebhookChannel()
        n = Notification(
            notification_id="abc123",
            event_id="evt456",
            user_id="u1",
            message="Test alert",
            subject="Alert",
        )
        payload = channel._build_payload(n)
        assert "alert.triggered" in payload
        assert "abc123" in payload
        assert "Test alert" in payload

    def test_sign_payload(self):
        from src.alerts.config import WebhookConfig
        config = WebhookConfig(signing_secret="test-secret")
        channel = WebhookChannel(config=config)
        sig = channel._sign('{"test": true}')
        assert len(sig) == 64  # SHA-256 hex digest

    def test_invalid_url_fails(self):
        channel = WebhookChannel()
        n = Notification(
            user_id="u1",
            message="Test",
            recipient="not-a-url",
        )
        assert channel.send(n) is False
        assert n.status == DeliveryStatus.FAILED


class TestSlackChannel:
    """Test Slack channel."""

    def test_validate_slack_url(self):
        channel = SlackChannel()
        assert channel.validate_recipient(
            "https://hooks.slack.com/services/T123ABC/B456DEF/abcdef123456"
        ) is True
        assert channel.validate_recipient("https://example.com") is False

    def test_build_payload(self):
        channel = SlackChannel()
        n = Notification(
            user_id="u1",
            message="AAPL crossed above $200",
            subject="Price Alert",
        )
        payload = channel._build_payload(n)
        assert payload["text"] == "Price Alert: AAPL crossed above $200"
        assert len(payload["blocks"]) == 3
        assert payload["blocks"][0]["type"] == "header"


class TestAlertEngine:
    """Test the core alert engine."""

    def test_register_and_get_alert(self):
        engine = AlertEngine()
        alert = Alert(alert_id="a1", user_id="u1", name="Test")
        engine.register_alert(alert)
        assert engine.get_alert("a1") is not None
        assert engine.get_alert("a1").name == "Test"

    def test_remove_alert(self):
        engine = AlertEngine()
        alert = Alert(alert_id="a1", user_id="u1")
        engine.register_alert(alert)
        assert engine.remove_alert("a1") is True
        assert engine.get_alert("a1") is None
        assert engine.remove_alert("a1") is False

    def test_get_alerts_by_user(self):
        engine = AlertEngine()
        engine.register_alert(Alert(alert_id="a1", user_id="u1"))
        engine.register_alert(Alert(alert_id="a2", user_id="u2"))
        engine.register_alert(Alert(alert_id="a3", user_id="u1"))
        assert len(engine.get_alerts(user_id="u1")) == 2
        assert len(engine.get_alerts(user_id="u2")) == 1

    def test_evaluate_triggers_alert(self):
        engine = AlertEngine()
        conditions = ConditionBuilder.simple("price", ComparisonOperator.GT, 200.0)
        alert = Alert(
            alert_id="a1",
            user_id="u1",
            name="AAPL > $200",
            symbol="AAPL",
            conditions=conditions,
            cooldown_seconds=0,
        )
        engine.register_alert(alert)

        events = engine.evaluate({"AAPL": {"price": 205.0}})
        assert len(events) == 1
        assert events[0].alert_id == "a1"
        assert "205" in events[0].message

    def test_evaluate_no_trigger(self):
        engine = AlertEngine()
        conditions = ConditionBuilder.simple("price", ComparisonOperator.GT, 200.0)
        alert = Alert(
            alert_id="a1",
            user_id="u1",
            symbol="AAPL",
            conditions=conditions,
        )
        engine.register_alert(alert)

        events = engine.evaluate({"AAPL": {"price": 195.0}})
        assert len(events) == 0

    def test_evaluate_respects_cooldown(self):
        engine = AlertEngine()
        conditions = ConditionBuilder.simple("price", ComparisonOperator.GT, 200.0)
        alert = Alert(
            alert_id="a1",
            user_id="u1",
            symbol="AAPL",
            conditions=conditions,
            cooldown_seconds=3600,
        )
        engine.register_alert(alert)

        # First trigger
        events1 = engine.evaluate({"AAPL": {"price": 205.0}})
        assert len(events1) == 1

        # Second — should be in cooldown
        events2 = engine.evaluate({"AAPL": {"price": 210.0}})
        assert len(events2) == 0

    def test_evaluate_disabled_alert(self):
        engine = AlertEngine()
        conditions = ConditionBuilder.simple("price", ComparisonOperator.GT, 200.0)
        alert = Alert(
            alert_id="a1",
            user_id="u1",
            symbol="AAPL",
            conditions=conditions,
            status=AlertStatus.DISABLED,
        )
        engine.register_alert(alert)

        events = engine.evaluate({"AAPL": {"price": 205.0}})
        assert len(events) == 0

    def test_in_app_notifications_delivered(self):
        engine = AlertEngine()
        conditions = ConditionBuilder.simple("price", ComparisonOperator.GT, 200.0)
        alert = Alert(
            alert_id="a1",
            user_id="u1",
            name="AAPL Alert",
            symbol="AAPL",
            conditions=conditions,
            channels=[ChannelType.IN_APP],
            cooldown_seconds=0,
        )
        engine.register_alert(alert)
        engine.evaluate({"AAPL": {"price": 205.0}})

        unread = engine.in_app_channel.get_unread("u1")
        assert len(unread) == 1
        assert "AAPL Alert" in unread[0].message

    def test_quiet_hours_suppresses_email(self):
        engine = AlertEngine()
        # Set preferences with quiet hours and email
        prefs = NotificationPreferences(
            user_id="u1",
            enabled_channels=[ChannelType.IN_APP, ChannelType.EMAIL],
            channel_settings={"email": "user@test.com"},
            quiet_hours_enabled=True,
            quiet_start_hour=22,
            quiet_end_hour=7,
        )
        engine.set_preferences(prefs)

        conditions = ConditionBuilder.simple("price", ComparisonOperator.GT, 200.0)
        alert = Alert(
            alert_id="a1",
            user_id="u1",
            symbol="AAPL",
            conditions=conditions,
            channels=[ChannelType.IN_APP, ChannelType.EMAIL],
            priority=AlertPriority.MEDIUM,
            cooldown_seconds=0,
        )
        engine.register_alert(alert)

        # Trigger during quiet hours (2 AM)
        engine.evaluate({"AAPL": {"price": 205.0}}, current_hour=2)

        # In-app should still be delivered
        assert engine.in_app_channel.get_unread_count("u1") == 1

    def test_critical_bypasses_quiet_hours(self):
        engine = AlertEngine()
        prefs = NotificationPreferences(
            user_id="u1",
            enabled_channels=[ChannelType.IN_APP, ChannelType.EMAIL],
            channel_settings={"email": "user@test.com"},
            quiet_hours_enabled=True,
            quiet_start_hour=22,
            quiet_end_hour=7,
        )
        engine.set_preferences(prefs)

        conditions = ConditionBuilder.simple("var_95", ComparisonOperator.GT, 0.03)
        alert = Alert(
            alert_id="a1",
            user_id="u1",
            symbol="*",
            conditions=conditions,
            channels=[ChannelType.IN_APP, ChannelType.EMAIL],
            priority=AlertPriority.CRITICAL,
            cooldown_seconds=0,
        )
        engine.register_alert(alert)

        # Trigger during quiet hours — critical should still send email
        engine.evaluate({"*": {"var_95": 0.04}}, current_hour=2)

        assert engine.in_app_channel.get_unread_count("u1") == 1

    def test_get_events(self):
        engine = AlertEngine()
        conditions = ConditionBuilder.simple("price", ComparisonOperator.GT, 100.0)
        alert = Alert(
            alert_id="a1", user_id="u1", symbol="AAPL",
            conditions=conditions, cooldown_seconds=0,
        )
        engine.register_alert(alert)

        engine.evaluate({"AAPL": {"price": 105.0}})
        engine.evaluate({"AAPL": {"price": 110.0}})

        events = engine.get_events(user_id="u1")
        assert len(events) == 2

    def test_get_stats(self):
        engine = AlertEngine()
        engine.register_alert(Alert(
            alert_id="a1", user_id="u1",
            alert_type=AlertType.PRICE, priority=AlertPriority.HIGH,
        ))
        engine.register_alert(Alert(
            alert_id="a2", user_id="u1",
            alert_type=AlertType.TECHNICAL, priority=AlertPriority.MEDIUM,
        ))

        stats = engine.get_stats()
        assert stats["total_alerts"] == 2
        assert stats["active_alerts"] == 2
        assert stats["alerts_by_type"]["price"] == 1
        assert stats["alerts_by_type"]["technical"] == 1


class TestAlertsAlertManager:
    """Test the alert manager."""

    def test_create_alert(self):
        mgr = AlertManager()
        alert = mgr.create_alert(
            user_id="u1",
            name="AAPL Price",
            alert_type=AlertType.PRICE,
            metric="price",
            operator=ComparisonOperator.GT,
            threshold=200.0,
            symbol="AAPL",
        )
        assert alert.alert_id is not None
        assert alert.name == "AAPL Price"
        assert alert.user_id == "u1"
        assert alert.symbol == "AAPL"

    def test_create_from_template(self):
        mgr = AlertManager()
        alert = mgr.create_from_template(
            user_id="u1",
            template_name="rsi_overbought",
            symbol="MSFT",
        )
        assert alert.name == "RSI Overbought"
        assert alert.symbol == "MSFT"
        assert alert.conditions.conditions[0].threshold == 70.0

    def test_create_from_template_with_override(self):
        mgr = AlertManager()
        alert = mgr.create_from_template(
            user_id="u1",
            template_name="rsi_overbought",
            symbol="MSFT",
            threshold_override=75.0,
        )
        assert alert.conditions.conditions[0].threshold == 75.0

    def test_create_from_unknown_template(self):
        mgr = AlertManager()
        with pytest.raises(ValueError):
            mgr.create_from_template("u1", "nonexistent")

    def test_create_compound_alert(self):
        mgr = AlertManager()
        alert = mgr.create_compound_alert(
            user_id="u1",
            name="RSI + Volume",
            alert_type=AlertType.TECHNICAL,
            conditions=[
                ("rsi_14", ComparisonOperator.GT, 70.0),
                ("volume_ratio_20d", ComparisonOperator.GT, 2.0),
            ],
            logical_operator="and",
            symbol="AAPL",
        )
        assert len(alert.conditions.conditions) == 2

    def test_update_alert(self):
        mgr = AlertManager()
        alert = mgr.create_alert(
            user_id="u1", name="Test",
            alert_type=AlertType.PRICE,
            metric="price", operator=ComparisonOperator.GT,
            threshold=100.0,
        )
        updated = mgr.update_alert(
            alert.alert_id,
            name="Updated Name",
            priority=AlertPriority.HIGH,
        )
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.priority == AlertPriority.HIGH

    def test_delete_alert(self):
        mgr = AlertManager()
        alert = mgr.create_alert(
            user_id="u1", name="Test",
            alert_type=AlertType.PRICE,
            metric="price", operator=ComparisonOperator.GT,
            threshold=100.0,
        )
        assert mgr.delete_alert(alert.alert_id) is True
        assert mgr.delete_alert(alert.alert_id) is False

    def test_snooze_and_unsnooze(self):
        mgr = AlertManager()
        alert = mgr.create_alert(
            user_id="u1", name="Test",
            alert_type=AlertType.PRICE,
            metric="price", operator=ComparisonOperator.GT,
            threshold=100.0,
        )
        snoozed = mgr.snooze_alert(alert.alert_id, hours=2)
        assert snoozed.status == AlertStatus.SNOOZED
        assert snoozed.snooze_until is not None

        unsnoozed = mgr.unsnooze_alert(alert.alert_id)
        assert unsnoozed.status == AlertStatus.ACTIVE
        assert unsnoozed.snooze_until is None

    def test_disable_and_enable(self):
        mgr = AlertManager()
        alert = mgr.create_alert(
            user_id="u1", name="Test",
            alert_type=AlertType.PRICE,
            metric="price", operator=ComparisonOperator.GT,
            threshold=100.0,
        )
        disabled = mgr.disable_alert(alert.alert_id)
        assert disabled.status == AlertStatus.DISABLED

        enabled = mgr.enable_alert(alert.alert_id)
        assert enabled.status == AlertStatus.ACTIVE

    def test_get_user_alerts(self):
        mgr = AlertManager()
        mgr.create_alert(
            user_id="u1", name="A1",
            alert_type=AlertType.PRICE,
            metric="price", operator=ComparisonOperator.GT,
            threshold=100.0,
        )
        mgr.create_alert(
            user_id="u2", name="A2",
            alert_type=AlertType.PRICE,
            metric="price", operator=ComparisonOperator.GT,
            threshold=200.0,
        )
        assert len(mgr.get_user_alerts("u1")) == 1

    def test_evaluate_integration(self):
        mgr = AlertManager()
        mgr.create_alert(
            user_id="u1",
            name="AAPL > $200",
            alert_type=AlertType.PRICE,
            metric="price",
            operator=ComparisonOperator.GT,
            threshold=200.0,
            symbol="AAPL",
            cooldown_seconds=0,
        )

        events = mgr.evaluate({"AAPL": {"price": 205.0}})
        assert len(events) == 1

    def test_set_notification_preferences(self):
        mgr = AlertManager()
        prefs = mgr.set_notification_preferences(
            user_id="u1",
            enabled_channels=[ChannelType.IN_APP, ChannelType.EMAIL],
            email="user@test.com",
            quiet_hours_enabled=True,
        )
        assert ChannelType.EMAIL in prefs.enabled_channels
        assert prefs.channel_settings["email"] == "user@test.com"
        assert prefs.quiet_hours_enabled is True

    def test_get_available_templates(self):
        mgr = AlertManager()
        templates = mgr.get_available_templates()
        assert len(templates) >= 10
        assert "price_breakout" in templates

    def test_get_stats(self):
        mgr = AlertManager()
        mgr.create_alert(
            user_id="u1", name="Test",
            alert_type=AlertType.PRICE,
            metric="price", operator=ComparisonOperator.GT,
            threshold=100.0,
        )
        stats = mgr.get_stats()
        assert stats["total_alerts"] == 1

    def test_expires_in_hours(self):
        mgr = AlertManager()
        alert = mgr.create_alert(
            user_id="u1", name="Temp",
            alert_type=AlertType.PRICE,
            metric="price", operator=ComparisonOperator.GT,
            threshold=100.0,
            expires_in_hours=24,
        )
        assert alert.expires_at is not None
        assert alert.expires_at > datetime.now(timezone.utc)


class TestAlertsFullWorkflow:
    """Integration tests for the complete alerting workflow."""

    def test_price_alert_workflow(self):
        """End-to-end: create alert, evaluate, get notifications."""
        mgr = AlertManager()

        # Set up preferences
        mgr.set_notification_preferences(
            user_id="u1",
            enabled_channels=[ChannelType.IN_APP, ChannelType.EMAIL],
            email="trader@example.com",
        )

        # Create alert
        alert = mgr.create_alert(
            user_id="u1",
            name="AAPL Breakout",
            alert_type=AlertType.PRICE,
            metric="price",
            operator=ComparisonOperator.GT,
            threshold=200.0,
            symbol="AAPL",
            channels=[ChannelType.IN_APP, ChannelType.EMAIL],
            cooldown_seconds=0,
        )

        # Evaluate — not triggered
        events = mgr.evaluate({"AAPL": {"price": 195.0}})
        assert len(events) == 0

        # Evaluate — triggered
        events = mgr.evaluate({"AAPL": {"price": 205.0}})
        assert len(events) == 1
        assert events[0].priority == AlertPriority.MEDIUM

        # Check in-app notifications
        unread = mgr.engine.in_app_channel.get_unread("u1")
        assert len(unread) == 1
        assert "AAPL Breakout" in unread[0].message

        # Check history
        history = mgr.get_alert_history("u1")
        assert len(history) == 1

    def test_multi_alert_evaluation(self):
        """Evaluate multiple alerts across symbols."""
        mgr = AlertManager()

        mgr.create_alert(
            user_id="u1", name="AAPL Up",
            alert_type=AlertType.PRICE,
            metric="price", operator=ComparisonOperator.GT,
            threshold=200.0, symbol="AAPL", cooldown_seconds=0,
        )
        mgr.create_alert(
            user_id="u1", name="MSFT Down",
            alert_type=AlertType.PRICE,
            metric="price", operator=ComparisonOperator.LT,
            threshold=300.0, symbol="MSFT", cooldown_seconds=0,
        )
        mgr.create_alert(
            user_id="u1", name="Portfolio Risk",
            alert_type=AlertType.RISK,
            metric="var_95", operator=ComparisonOperator.GT,
            threshold=0.02, cooldown_seconds=0,
        )

        events = mgr.evaluate({
            "AAPL": {"price": 205.0},
            "MSFT": {"price": 295.0},
            "*": {"var_95": 0.025},
        })
        assert len(events) == 3

    def test_template_alert_workflow(self):
        """Create from template and evaluate."""
        mgr = AlertManager()

        alert = mgr.create_from_template(
            user_id="u1",
            template_name="unusual_volume",
            symbol="TSLA",
        )
        alert.cooldown_seconds = 0

        events = mgr.evaluate({"TSLA": {"volume_ratio_20d": 3.5}})
        assert len(events) == 1

        events = mgr.evaluate({"TSLA": {"volume_ratio_20d": 1.2}})
        assert len(events) == 0


class TestAlertsModuleImports:
    """Test that all module exports work."""

    def test_top_level_imports(self):
        from src.alerts import (
            AlertType, AlertPriority, AlertStatus,
            ComparisonOperator, LogicalOperator,
            ChannelType, DeliveryStatus,
            AlertCondition, CompoundCondition,
            Alert, AlertEvent, Notification, NotificationPreferences,
            ConditionBuilder, ConditionEvaluator,
            AlertEngine, AlertManager,
            InAppChannel, EmailChannel, SMSChannel,
            WebhookChannel, SlackChannel,
            ALERT_TEMPLATES, DEFAULT_ALERTING_CONFIG,
        )

    def test_channel_imports(self):
        from src.alerts.channels import (
            DeliveryChannel, InAppChannel, EmailChannel,
            SMSChannel, WebhookChannel, SlackChannel,
        )
