"""Tests for Alert & Notification Network (PRD-142).

8 test classes, ~50 tests covering rules, channels, delivery,
manager, and module imports.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class _MockSignal:
    symbol: str = "AAPL"
    confidence: float = 75.0
    action: type = None
    avg_sentiment: float = 0.8
    direction: str = "bullish"

    def __post_init__(self):
        if self.action is None:
            self.action = type("Action", (), {"value": "buy"})()


@dataclass
class _MockAnomaly:
    symbol: str = "AAPL"
    z_score: float = 3.5
    volume_ratio: float = 5.0


@dataclass
class _MockCorrelation:
    symbol: str = "AAPL"
    is_consensus: bool = True
    consensus_direction: str = "bullish"
    agreement_score: float = 0.9
    platform_count: int = 3


@dataclass
class _MockInfluencer:
    symbol: str = "AAPL"
    confidence: float = 0.8
    tier: str = "mega"
    direction: str = "bullish"


# ═══════════════════════════════════════════════════════════════════════
# Test: Alert Rules
# ═══════════════════════════════════════════════════════════════════════


class TestAlertRules:
    """Tests for alert rule creation and configuration."""

    def test_create_rule(self):
        from src.alert_network import AlertRule, TriggerType
        rule = AlertRule(
            name="Test Rule",
            trigger_type=TriggerType.PRICE_ABOVE,
            symbol="AAPL",
            threshold=200.0,
        )
        assert rule.name == "Test Rule"
        assert rule.trigger_type == TriggerType.PRICE_ABOVE
        assert rule.enabled is True

    def test_rule_to_dict(self):
        from src.alert_network import AlertRule, TriggerType
        rule = AlertRule(
            rule_id="r1", name="Test",
            trigger_type=TriggerType.VOLUME_SPIKE,
            threshold=2.0,
        )
        d = rule.to_dict()
        assert d["rule_id"] == "r1"
        assert d["trigger_type"] == "volume_spike"

    def test_trigger_types(self):
        from src.alert_network import TriggerType
        assert TriggerType.PRICE_ABOVE.value == "price_above"
        assert TriggerType.VOLUME_SPIKE.value == "volume_spike"
        assert TriggerType.SOCIAL_TRENDING.value == "social_trending"
        assert TriggerType.CONSENSUS_FORMED.value == "consensus_formed"

    def test_default_cooldown(self):
        from src.alert_network import AlertRule
        rule = AlertRule()
        assert rule.cooldown_minutes == 30
        assert rule.max_daily_alerts == 10


# ═══════════════════════════════════════════════════════════════════════
# Test: Rule Engine
# ═══════════════════════════════════════════════════════════════════════


class TestRuleEngine:
    """Tests for rule evaluation engine."""

    def test_add_and_get_rules(self):
        from src.alert_network import RuleEngine, AlertRule, TriggerType
        engine = RuleEngine()
        engine.add_rule(AlertRule(
            rule_id="r1", trigger_type=TriggerType.PRICE_ABOVE,
            symbol="AAPL", threshold=200.0,
        ))
        assert len(engine.get_rules()) == 1

    def test_remove_rule(self):
        from src.alert_network import RuleEngine, AlertRule
        engine = RuleEngine()
        engine.add_rule(AlertRule(rule_id="r1"))
        assert engine.remove_rule("r1") is True
        assert engine.remove_rule("r1") is False

    def test_price_above_trigger(self):
        from src.alert_network import RuleEngine, AlertRule, TriggerType
        engine = RuleEngine()
        engine.add_rule(AlertRule(
            rule_id="r1", trigger_type=TriggerType.PRICE_ABOVE,
            symbol="AAPL", threshold=200.0,
        ))
        triggered = engine.evaluate({"prices": {"AAPL": 210.0}})
        assert len(triggered) == 1
        assert triggered[0].symbol == "AAPL"

    def test_price_below_trigger(self):
        from src.alert_network import RuleEngine, AlertRule, TriggerType
        engine = RuleEngine()
        engine.add_rule(AlertRule(
            rule_id="r1", trigger_type=TriggerType.PRICE_BELOW,
            symbol="AAPL", threshold=150.0,
        ))
        triggered = engine.evaluate({"prices": {"AAPL": 140.0}})
        assert len(triggered) == 1

    def test_no_trigger_below_threshold(self):
        from src.alert_network import RuleEngine, AlertRule, TriggerType
        engine = RuleEngine()
        engine.add_rule(AlertRule(
            rule_id="r1", trigger_type=TriggerType.PRICE_ABOVE,
            symbol="AAPL", threshold=200.0,
        ))
        triggered = engine.evaluate({"prices": {"AAPL": 190.0}})
        assert len(triggered) == 0

    def test_volume_spike_trigger(self):
        from src.alert_network import RuleEngine, AlertRule, TriggerType
        engine = RuleEngine()
        engine.add_rule(AlertRule(
            rule_id="r1", trigger_type=TriggerType.VOLUME_SPIKE,
            threshold=2.0,
        ))
        triggered = engine.evaluate({"volume_anomalies": [_MockAnomaly()]})
        assert len(triggered) == 1

    def test_signal_generated_trigger(self):
        from src.alert_network import RuleEngine, AlertRule, TriggerType
        engine = RuleEngine()
        engine.add_rule(AlertRule(
            rule_id="r1", trigger_type=TriggerType.SIGNAL_GENERATED,
            threshold=50.0,
        ))
        triggered = engine.evaluate({"signals": [_MockSignal(confidence=75.0)]})
        assert len(triggered) == 1

    def test_social_trending_trigger(self):
        from src.alert_network import RuleEngine, AlertRule, TriggerType
        engine = RuleEngine()
        engine.add_rule(AlertRule(
            rule_id="r1", trigger_type=TriggerType.SOCIAL_TRENDING,
        ))
        triggered = engine.evaluate({"trending": ["AAPL", "NVDA"]})
        assert len(triggered) == 2

    def test_consensus_trigger(self):
        from src.alert_network import RuleEngine, AlertRule, TriggerType
        engine = RuleEngine()
        engine.add_rule(AlertRule(
            rule_id="r1", trigger_type=TriggerType.CONSENSUS_FORMED,
        ))
        triggered = engine.evaluate({"consensus": [_MockCorrelation()]})
        assert len(triggered) == 1

    def test_disabled_rule_skipped(self):
        from src.alert_network import RuleEngine, AlertRule, TriggerType
        engine = RuleEngine()
        engine.add_rule(AlertRule(
            rule_id="r1", trigger_type=TriggerType.PRICE_ABOVE,
            symbol="AAPL", threshold=200.0, enabled=False,
        ))
        triggered = engine.evaluate({"prices": {"AAPL": 210.0}})
        assert len(triggered) == 0

    def test_symbol_filter(self):
        from src.alert_network import RuleEngine, AlertRule, TriggerType
        engine = RuleEngine()
        engine.add_rule(AlertRule(
            rule_id="r1", trigger_type=TriggerType.VOLUME_SPIKE,
            symbol="MSFT", threshold=2.0,
        ))
        triggered = engine.evaluate({"volume_anomalies": [_MockAnomaly(symbol="AAPL")]})
        assert len(triggered) == 0

    def test_auto_assign_rule_id(self):
        from src.alert_network import RuleEngine, AlertRule
        engine = RuleEngine()
        rule = AlertRule()
        engine.add_rule(rule)
        assert rule.rule_id.startswith("rule_")


# ═══════════════════════════════════════════════════════════════════════
# Test: Channels
# ═══════════════════════════════════════════════════════════════════════


class TestChannels:
    """Tests for notification channels."""

    @pytest.mark.asyncio
    async def test_email_channel_demo(self):
        from src.alert_network import EmailChannel, NotificationPayload
        ch = EmailChannel()
        result = await ch.send(NotificationPayload(title="Test", body="Hello"))
        assert result.success is True
        assert ch.kind.value == "email"

    @pytest.mark.asyncio
    async def test_sms_channel_demo(self):
        from src.alert_network import SMSChannel, NotificationPayload
        ch = SMSChannel()
        result = await ch.send(NotificationPayload(title="Test", body="Hello"))
        assert result.success is True

    @pytest.mark.asyncio
    async def test_push_channel_demo(self):
        from src.alert_network import PushChannel, NotificationPayload
        ch = PushChannel()
        result = await ch.send(NotificationPayload(title="Test", body="Hello"))
        assert result.success is True

    @pytest.mark.asyncio
    async def test_slack_channel_demo(self):
        from src.alert_network import SlackChannel, NotificationPayload
        ch = SlackChannel()
        result = await ch.send(NotificationPayload(title="Test", body="Hello"))
        assert result.success is True

    @pytest.mark.asyncio
    async def test_discord_channel_demo(self):
        from src.alert_network import DiscordChannel, NotificationPayload
        ch = DiscordChannel()
        result = await ch.send(NotificationPayload(title="Test", body="Hello"))
        assert result.success is True

    @pytest.mark.asyncio
    async def test_telegram_channel_demo(self):
        from src.alert_network import TelegramChannel, NotificationPayload
        ch = TelegramChannel()
        result = await ch.send(NotificationPayload(title="Test", body="Hello"))
        assert result.success is True

    def test_channel_kind_enum(self):
        from src.alert_network import ChannelKind
        assert ChannelKind.EMAIL.value == "email"
        assert ChannelKind.SLACK.value == "slack"
        assert ChannelKind.TELEGRAM.value == "telegram"

    def test_channel_result_to_dict(self):
        from src.alert_network import ChannelResult, ChannelKind
        r = ChannelResult(channel=ChannelKind.EMAIL, success=True)
        d = r.to_dict()
        assert d["channel"] == "email"
        assert d["success"] is True


# ═══════════════════════════════════════════════════════════════════════
# Test: Channel Registry
# ═══════════════════════════════════════════════════════════════════════


class TestChannelRegistry:
    """Tests for channel registry."""

    def test_default_channels_registered(self):
        from src.alert_network import ChannelRegistry, ChannelKind
        registry = ChannelRegistry()
        assert ChannelKind.EMAIL in registry.available_channels
        assert ChannelKind.SLACK in registry.available_channels

    @pytest.mark.asyncio
    async def test_send_to_channel(self):
        from src.alert_network import ChannelRegistry, ChannelKind, NotificationPayload
        registry = ChannelRegistry()
        result = await registry.send_to(
            ChannelKind.EMAIL, NotificationPayload(title="Test", body="Hello")
        )
        assert result.success is True

    @pytest.mark.asyncio
    async def test_send_to_all(self):
        from src.alert_network import ChannelRegistry, ChannelKind, NotificationPayload
        registry = ChannelRegistry()
        results = await registry.send_to_all(
            [ChannelKind.EMAIL, ChannelKind.SLACK],
            NotificationPayload(title="Test", body="Hello"),
        )
        assert len(results) == 2
        assert all(r.success for r in results)


# ═══════════════════════════════════════════════════════════════════════
# Test: Delivery Tracker
# ═══════════════════════════════════════════════════════════════════════


class TestDeliveryTracker:
    """Tests for delivery tracking and throttling."""

    def test_can_deliver_default(self):
        from src.alert_network import DeliveryTracker
        tracker = DeliveryTracker()
        assert tracker.can_deliver("user_1") is True

    def test_throttle_over_limit(self):
        from src.alert_network import DeliveryTracker, DeliveryPreferences, DeliveryRecord, DeliveryStatus
        tracker = DeliveryTracker()
        tracker.set_preferences("u1", DeliveryPreferences(max_per_hour=2))
        # First call to can_deliver initializes the reset hour
        assert tracker.can_deliver("u1") is True
        tracker.record(DeliveryRecord(status=DeliveryStatus.SENT), "u1")
        tracker.record(DeliveryRecord(status=DeliveryStatus.SENT), "u1")
        # Now at limit — should block
        assert tracker.can_deliver("u1") is False

    def test_delivery_stats(self):
        from src.alert_network import DeliveryTracker, DeliveryRecord, DeliveryStatus
        tracker = DeliveryTracker()
        tracker.record(DeliveryRecord(status=DeliveryStatus.SENT))
        tracker.record(DeliveryRecord(status=DeliveryStatus.FAILED))
        stats = tracker.get_stats()
        assert stats["total_deliveries"] == 2
        assert stats["sent"] == 1
        assert stats["failed"] == 1

    def test_batch_queue(self):
        from src.alert_network import DeliveryTracker, DeliveryRecord
        tracker = DeliveryTracker()
        tracker.queue_for_batch(DeliveryRecord(symbol="AAPL"))
        tracker.queue_for_batch(DeliveryRecord(symbol="MSFT"))
        batch = tracker.flush_batch()
        assert len(batch) == 2
        assert tracker.flush_batch() == []

    def test_preferences_to_dict(self):
        from src.alert_network import DeliveryPreferences
        prefs = DeliveryPreferences(user_id="u1")
        d = prefs.to_dict()
        assert d["user_id"] == "u1"


# ═══════════════════════════════════════════════════════════════════════
# Test: Notification Manager
# ═══════════════════════════════════════════════════════════════════════


class TestNotificationManager:
    """Tests for the orchestrating notification manager."""

    @pytest.mark.asyncio
    async def test_evaluate_and_notify(self):
        from src.alert_network import (
            NotificationManager, AlertRule, TriggerType, ChannelKind,
        )
        mgr = NotificationManager()
        mgr.add_rule(AlertRule(
            rule_id="r1", name="Price Alert",
            trigger_type=TriggerType.PRICE_ABOVE,
            symbol="AAPL", threshold=200.0,
            channels=[ChannelKind.EMAIL],
        ))
        result = await mgr.evaluate_and_notify({"prices": {"AAPL": 210.0}})
        assert result.alerts_triggered == 1
        assert result.notifications_sent == 1

    @pytest.mark.asyncio
    async def test_no_triggers(self):
        from src.alert_network import NotificationManager
        mgr = NotificationManager()
        result = await mgr.evaluate_and_notify({"prices": {}})
        assert result.alerts_triggered == 0
        assert result.notifications_sent == 0

    @pytest.mark.asyncio
    async def test_multi_channel_delivery(self):
        from src.alert_network import (
            NotificationManager, AlertRule, TriggerType, ChannelKind,
        )
        mgr = NotificationManager()
        mgr.add_rule(AlertRule(
            rule_id="r1", trigger_type=TriggerType.PRICE_ABOVE,
            symbol="AAPL", threshold=200.0,
            channels=[ChannelKind.EMAIL, ChannelKind.SLACK, ChannelKind.PUSH],
        ))
        result = await mgr.evaluate_and_notify({"prices": {"AAPL": 210.0}})
        assert result.notifications_sent == 3

    @pytest.mark.asyncio
    async def test_result_to_dict(self):
        from src.alert_network import (
            NotificationManager, AlertRule, TriggerType, ChannelKind,
        )
        mgr = NotificationManager()
        mgr.add_rule(AlertRule(
            rule_id="r1", trigger_type=TriggerType.SOCIAL_TRENDING,
        ))
        result = await mgr.evaluate_and_notify({"trending": ["AAPL"]})
        d = result.to_dict()
        assert "alerts_triggered" in d
        assert "notifications_sent" in d

    def test_get_delivery_stats(self):
        from src.alert_network import NotificationManager
        mgr = NotificationManager()
        stats = mgr.get_delivery_stats()
        assert "total_deliveries" in stats

    def test_component_accessors(self):
        from src.alert_network import NotificationManager
        mgr = NotificationManager()
        assert mgr.rule_engine is not None
        assert mgr.channel_registry is not None
        assert mgr.delivery_tracker is not None


# ═══════════════════════════════════════════════════════════════════════
# Test: Batch Digest
# ═══════════════════════════════════════════════════════════════════════


class TestBatchDigest:
    """Tests for batch digest functionality."""

    def test_digest_to_payload(self):
        from src.alert_network import BatchDigest, TriggeredAlert, AlertRule
        digest = BatchDigest(
            alerts=[
                TriggeredAlert(rule=AlertRule(name="R1"), symbol="AAPL"),
                TriggeredAlert(rule=AlertRule(name="R2"), symbol="MSFT"),
            ],
            symbol_summary={"AAPL": 1, "MSFT": 1},
        )
        payload = digest.to_payload()
        assert "2 alerts" in payload.title
        assert "AAPL" in payload.body

    def test_digest_to_dict(self):
        from src.alert_network import BatchDigest
        digest = BatchDigest(symbol_summary={"AAPL": 3, "MSFT": 2})
        d = digest.to_dict()
        assert d["symbols"] == ["AAPL", "MSFT"]


# ═══════════════════════════════════════════════════════════════════════
# Test: Module Imports
# ═══════════════════════════════════════════════════════════════════════


class TestModuleImports:
    """Tests for module import integrity."""

    def test_all_exports_importable(self):
        from src.alert_network import __all__
        import src.alert_network as mod
        for name in __all__:
            assert hasattr(mod, name), f"Missing export: {name}"

    def test_trigger_type_values(self):
        from src.alert_network import TriggerType
        assert len(TriggerType) == 11

    def test_channel_kind_values(self):
        from src.alert_network import ChannelKind
        assert len(ChannelKind) == 8

    def test_delivery_status_values(self):
        from src.alert_network import DeliveryStatus
        assert DeliveryStatus.PENDING.value == "pending"
        assert DeliveryStatus.SENT.value == "sent"
