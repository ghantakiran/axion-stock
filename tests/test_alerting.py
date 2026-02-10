"""Tests for PRD-114: Notification & Alerting System."""

from datetime import datetime, timedelta

import pytest

from src.alerting.config import (
    AlertSeverity,
    AlertStatus,
    AlertCategory,
    ChannelType,
    AlertConfig,
)
from src.alerting.manager import Alert, AlertManager
from src.alerting.routing import RoutingRule, RoutingEngine
from src.alerting.escalation import (
    EscalationLevel,
    EscalationPolicy,
    EscalationManager,
)
from src.alerting.aggregation import AlertDigest, AlertAggregator
from src.alerting.channels import DeliveryResult, ChannelDispatcher


# ── Config Tests ─────────────────────────────────────────────────────


class TestAlertConfig:
    def test_alert_severity_enum(self):
        assert len(AlertSeverity) == 4
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.ERROR.value == "error"
        assert AlertSeverity.CRITICAL.value == "critical"

    def test_alert_status_enum(self):
        assert len(AlertStatus) == 4
        assert AlertStatus.OPEN.value == "open"
        assert AlertStatus.ACKNOWLEDGED.value == "acknowledged"
        assert AlertStatus.RESOLVED.value == "resolved"
        assert AlertStatus.SUPPRESSED.value == "suppressed"

    def test_alert_category_enum(self):
        assert len(AlertCategory) == 5
        assert AlertCategory.SYSTEM.value == "system"
        assert AlertCategory.TRADING.value == "trading"
        assert AlertCategory.DATA.value == "data"
        assert AlertCategory.SECURITY.value == "security"
        assert AlertCategory.COMPLIANCE.value == "compliance"

    def test_channel_type_enum(self):
        assert len(ChannelType) == 5
        assert ChannelType.EMAIL.value == "email"
        assert ChannelType.SLACK.value == "slack"
        assert ChannelType.SMS.value == "sms"
        assert ChannelType.WEBHOOK.value == "webhook"
        assert ChannelType.IN_APP.value == "in_app"

    def test_default_config(self):
        cfg = AlertConfig()
        assert cfg.default_channels == [ChannelType.IN_APP]
        assert cfg.aggregation_window_seconds == 60
        assert cfg.max_alerts_per_window == 100
        assert cfg.enable_escalation is True
        assert cfg.enable_aggregation is True
        assert cfg.dedup_window_seconds == 300

    def test_custom_config(self):
        cfg = AlertConfig(
            default_channels=[ChannelType.EMAIL, ChannelType.SLACK],
            aggregation_window_seconds=120,
            max_alerts_per_window=50,
            enable_escalation=False,
            enable_aggregation=False,
            dedup_window_seconds=600,
        )
        assert len(cfg.default_channels) == 2
        assert cfg.aggregation_window_seconds == 120
        assert cfg.max_alerts_per_window == 50
        assert cfg.enable_escalation is False


# ── Alert Manager Tests ──────────────────────────────────────────────


class TestAlertingAlertManager:
    def setup_method(self):
        self.manager = AlertManager()

    def test_fire_basic_alert(self):
        alert = self.manager.fire(
            title="Test Alert",
            message="Something happened",
            severity=AlertSeverity.WARNING,
            category=AlertCategory.SYSTEM,
        )
        assert alert.title == "Test Alert"
        assert alert.message == "Something happened"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.category == AlertCategory.SYSTEM
        assert alert.status == AlertStatus.OPEN
        assert alert.occurrence_count == 1

    def test_fire_alert_with_tags(self):
        alert = self.manager.fire(
            title="Tagged Alert",
            message="Has tags",
            tags={"host": "server-1", "env": "prod"},
        )
        assert alert.tags["host"] == "server-1"
        assert alert.tags["env"] == "prod"

    def test_fire_alert_with_source(self):
        alert = self.manager.fire(
            title="Source Alert",
            message="From specific source",
            source="data_pipeline",
        )
        assert alert.source == "data_pipeline"

    def test_deduplication_same_key(self):
        a1 = self.manager.fire(
            title="Dup Alert",
            message="First",
            dedup_key="dup-001",
        )
        a2 = self.manager.fire(
            title="Dup Alert",
            message="Second",
            dedup_key="dup-001",
        )
        assert a1.alert_id == a2.alert_id
        assert a2.occurrence_count == 2

    def test_deduplication_different_keys(self):
        a1 = self.manager.fire(title="A1", message="M1", dedup_key="key-1")
        a2 = self.manager.fire(title="A2", message="M2", dedup_key="key-2")
        assert a1.alert_id != a2.alert_id

    def test_deduplication_no_key(self):
        a1 = self.manager.fire(title="No Key 1", message="M1")
        a2 = self.manager.fire(title="No Key 2", message="M2")
        assert a1.alert_id != a2.alert_id

    def test_acknowledge_alert(self):
        alert = self.manager.fire(title="Ack Test", message="M")
        result = self.manager.acknowledge(alert.alert_id, by="operator")
        assert result is True
        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.acknowledged_by == "operator"
        assert alert.acknowledged_at is not None

    def test_acknowledge_non_open_alert_fails(self):
        alert = self.manager.fire(title="Ack Fail", message="M")
        self.manager.acknowledge(alert.alert_id, by="op1")
        result = self.manager.acknowledge(alert.alert_id, by="op2")
        assert result is False

    def test_acknowledge_nonexistent_alert(self):
        result = self.manager.acknowledge("nonexistent-id")
        assert result is False

    def test_resolve_alert(self):
        alert = self.manager.fire(title="Resolve Test", message="M")
        result = self.manager.resolve(alert.alert_id)
        assert result is True
        assert alert.status == AlertStatus.RESOLVED
        assert alert.resolved_at is not None

    def test_resolve_already_resolved(self):
        alert = self.manager.fire(title="Resolve Twice", message="M")
        self.manager.resolve(alert.alert_id)
        result = self.manager.resolve(alert.alert_id)
        assert result is False

    def test_resolve_nonexistent(self):
        result = self.manager.resolve("no-such-id")
        assert result is False

    def test_suppress_alert(self):
        alert = self.manager.fire(title="Suppress Test", message="M")
        result = self.manager.suppress(alert.alert_id)
        assert result is True
        assert alert.status == AlertStatus.SUPPRESSED

    def test_suppress_nonexistent(self):
        result = self.manager.suppress("no-such-id")
        assert result is False

    def test_get_alert(self):
        alert = self.manager.fire(title="Get Test", message="M")
        fetched = self.manager.get_alert(alert.alert_id)
        assert fetched is not None
        assert fetched.title == "Get Test"

    def test_get_alert_nonexistent(self):
        assert self.manager.get_alert("missing") is None

    def test_get_active_alerts(self):
        self.manager.fire(title="A1", message="M1")
        a2 = self.manager.fire(title="A2", message="M2")
        self.manager.fire(title="A3", message="M3")
        self.manager.resolve(a2.alert_id)
        active = self.manager.get_active_alerts()
        assert len(active) == 2
        assert all(a.status == AlertStatus.OPEN for a in active)

    def test_get_alerts_filter_by_status(self):
        a1 = self.manager.fire(title="A1", message="M1")
        self.manager.fire(title="A2", message="M2")
        self.manager.resolve(a1.alert_id)
        resolved = self.manager.get_alerts(status=AlertStatus.RESOLVED)
        assert len(resolved) == 1
        assert resolved[0].alert_id == a1.alert_id

    def test_get_alerts_filter_by_severity(self):
        self.manager.fire(title="Info", message="M", severity=AlertSeverity.INFO)
        self.manager.fire(title="Error", message="M", severity=AlertSeverity.ERROR)
        self.manager.fire(title="Error2", message="M", severity=AlertSeverity.ERROR)
        errors = self.manager.get_alerts(severity=AlertSeverity.ERROR)
        assert len(errors) == 2

    def test_get_alerts_filter_by_category(self):
        self.manager.fire(title="Sys", message="M", category=AlertCategory.SYSTEM)
        self.manager.fire(title="Trade", message="M", category=AlertCategory.TRADING)
        trading = self.manager.get_alerts(category=AlertCategory.TRADING)
        assert len(trading) == 1
        assert trading[0].category == AlertCategory.TRADING

    def test_get_alerts_combined_filters(self):
        self.manager.fire(
            title="A1",
            message="M",
            severity=AlertSeverity.ERROR,
            category=AlertCategory.SYSTEM,
        )
        self.manager.fire(
            title="A2",
            message="M",
            severity=AlertSeverity.ERROR,
            category=AlertCategory.TRADING,
        )
        self.manager.fire(
            title="A3",
            message="M",
            severity=AlertSeverity.INFO,
            category=AlertCategory.SYSTEM,
        )
        result = self.manager.get_alerts(
            severity=AlertSeverity.ERROR,
            category=AlertCategory.SYSTEM,
        )
        assert len(result) == 1
        assert result[0].title == "A1"

    def test_alert_count_by_severity(self):
        self.manager.fire(title="I1", message="M", severity=AlertSeverity.INFO)
        self.manager.fire(title="I2", message="M", severity=AlertSeverity.INFO)
        self.manager.fire(title="W1", message="M", severity=AlertSeverity.WARNING)
        self.manager.fire(title="E1", message="M", severity=AlertSeverity.ERROR)
        counts = self.manager.get_alert_count_by_severity()
        assert counts["info"] == 2
        assert counts["warning"] == 1
        assert counts["error"] == 1

    def test_alert_dispatched_to_channels(self):
        alert = self.manager.fire(title="Dispatch Test", message="M")
        log = self.manager.dispatcher.get_delivery_log(alert.alert_id)
        assert len(log) >= 1  # At least default IN_APP channel


# ── Routing Engine Tests ─────────────────────────────────────────────


class TestRoutingEngine:
    def setup_method(self):
        self.engine = RoutingEngine()

    def test_default_channels_when_no_rules(self):
        alert = Alert(title="Test", message="M", severity=AlertSeverity.INFO)
        channels = self.engine.resolve_channels(alert)
        assert channels == [ChannelType.IN_APP]

    def test_add_and_get_rules(self):
        rule = RoutingRule(
            rule_id="R1",
            name="Critical to SMS",
            severity_min=AlertSeverity.CRITICAL,
            channels=[ChannelType.SMS],
        )
        self.engine.add_rule(rule)
        assert len(self.engine.get_rules()) == 1

    def test_remove_rule(self):
        rule = RoutingRule(
            rule_id="R1",
            name="Test",
            severity_min=AlertSeverity.INFO,
            channels=[ChannelType.EMAIL],
        )
        self.engine.add_rule(rule)
        assert self.engine.remove_rule("R1") is True
        assert len(self.engine.get_rules()) == 0

    def test_remove_nonexistent_rule(self):
        assert self.engine.remove_rule("no-such") is False

    def test_resolve_channels_by_severity(self):
        rule = RoutingRule(
            rule_id="R1",
            name="Error+ to Email",
            severity_min=AlertSeverity.ERROR,
            channels=[ChannelType.EMAIL, ChannelType.SLACK],
        )
        self.engine.add_rule(rule)

        # ERROR matches
        error_alert = Alert(
            title="Error", message="M", severity=AlertSeverity.ERROR
        )
        channels = self.engine.resolve_channels(error_alert)
        assert ChannelType.EMAIL in channels
        assert ChannelType.SLACK in channels

        # INFO does not match, falls to default
        info_alert = Alert(
            title="Info", message="M", severity=AlertSeverity.INFO
        )
        channels = self.engine.resolve_channels(info_alert)
        assert channels == [ChannelType.IN_APP]

    def test_resolve_channels_by_category(self):
        rule = RoutingRule(
            rule_id="R1",
            name="Security to SMS",
            severity_min=AlertSeverity.INFO,
            categories=[AlertCategory.SECURITY],
            channels=[ChannelType.SMS],
        )
        self.engine.add_rule(rule)

        sec_alert = Alert(
            title="Sec",
            message="M",
            severity=AlertSeverity.WARNING,
            category=AlertCategory.SECURITY,
        )
        assert self.engine.resolve_channels(sec_alert) == [ChannelType.SMS]

        sys_alert = Alert(
            title="Sys",
            message="M",
            severity=AlertSeverity.WARNING,
            category=AlertCategory.SYSTEM,
        )
        # Does not match category, falls to default
        assert self.engine.resolve_channels(sys_alert) == [ChannelType.IN_APP]

    def test_priority_ordering(self):
        low_rule = RoutingRule(
            rule_id="R-low",
            name="Low Priority",
            severity_min=AlertSeverity.INFO,
            channels=[ChannelType.IN_APP],
            priority=1,
        )
        high_rule = RoutingRule(
            rule_id="R-high",
            name="High Priority",
            severity_min=AlertSeverity.INFO,
            channels=[ChannelType.EMAIL, ChannelType.SMS],
            priority=10,
        )
        self.engine.add_rule(low_rule)
        self.engine.add_rule(high_rule)

        alert = Alert(title="Test", message="M", severity=AlertSeverity.WARNING)
        channels = self.engine.resolve_channels(alert)
        assert ChannelType.EMAIL in channels
        assert ChannelType.SMS in channels

    def test_disabled_rule_skipped(self):
        rule = RoutingRule(
            rule_id="R1",
            name="Disabled",
            severity_min=AlertSeverity.INFO,
            channels=[ChannelType.EMAIL],
            enabled=False,
        )
        self.engine.add_rule(rule)

        alert = Alert(title="Test", message="M", severity=AlertSeverity.ERROR)
        channels = self.engine.resolve_channels(alert)
        assert channels == [ChannelType.IN_APP]  # Falls to default

    def test_clear_rules(self):
        self.engine.add_rule(
            RoutingRule(
                rule_id="R1",
                name="Test",
                severity_min=AlertSeverity.INFO,
                channels=[ChannelType.EMAIL],
            )
        )
        self.engine.clear_rules()
        assert len(self.engine.get_rules()) == 0


# ── Escalation Manager Tests ────────────────────────────────────────


class TestEscalationManager:
    def setup_method(self):
        self.manager = EscalationManager()
        self.policy = EscalationPolicy(
            policy_id="P1",
            name="Standard Escalation",
            levels=[
                EscalationLevel(
                    level=0,
                    timeout_seconds=300,
                    channels=[ChannelType.IN_APP],
                    notify_targets=["team-a"],
                ),
                EscalationLevel(
                    level=1,
                    timeout_seconds=600,
                    channels=[ChannelType.EMAIL, ChannelType.SLACK],
                    notify_targets=["team-lead"],
                ),
                EscalationLevel(
                    level=2,
                    timeout_seconds=900,
                    channels=[ChannelType.SMS],
                    notify_targets=["director"],
                ),
            ],
        )
        self.manager.add_policy(self.policy)

    def test_add_and_get_policies(self):
        policies = self.manager.get_policies()
        assert len(policies) == 1
        assert policies[0].policy_id == "P1"

    def test_remove_policy(self):
        assert self.manager.remove_policy("P1") is True
        assert len(self.manager.get_policies()) == 0

    def test_remove_nonexistent_policy(self):
        assert self.manager.remove_policy("nonexistent") is False

    def test_start_escalation(self):
        result = self.manager.start_escalation("alert-1", "P1")
        assert result is True
        state = self.manager.get_escalation_state("alert-1")
        assert state is not None
        assert state["current_level"] == 0
        assert state["policy_id"] == "P1"

    def test_start_escalation_nonexistent_policy(self):
        result = self.manager.start_escalation("alert-1", "no-policy")
        assert result is False

    def test_start_escalation_disabled_policy(self):
        disabled = EscalationPolicy(
            policy_id="P-disabled",
            name="Disabled",
            levels=[
                EscalationLevel(level=0, timeout_seconds=60, channels=[ChannelType.IN_APP]),
            ],
            enabled=False,
        )
        self.manager.add_policy(disabled)
        result = self.manager.start_escalation("alert-1", "P-disabled")
        assert result is False

    def test_check_escalations_timeout(self):
        self.manager.start_escalation("alert-1", "P1")

        # Simulate time passing beyond first level timeout
        future = datetime.utcnow() + timedelta(seconds=301)
        escalations = self.manager.check_escalations(now=future)
        assert len(escalations) == 1
        alert_id, level = escalations[0]
        assert alert_id == "alert-1"
        assert level.level == 1  # Escalated to level 1

    def test_check_escalations_no_timeout(self):
        self.manager.start_escalation("alert-1", "P1")
        # Check immediately (no timeout yet)
        escalations = self.manager.check_escalations(now=datetime.utcnow())
        assert len(escalations) == 0

    def test_cancel_escalation(self):
        self.manager.start_escalation("alert-1", "P1")
        assert self.manager.cancel_escalation("alert-1") is True
        assert self.manager.get_escalation_state("alert-1") is None

    def test_cancel_nonexistent_escalation(self):
        assert self.manager.cancel_escalation("no-alert") is False

    def test_get_escalation_state_nonexistent(self):
        assert self.manager.get_escalation_state("no-alert") is None

    def test_escalation_state_has_time_remaining(self):
        self.manager.start_escalation("alert-1", "P1")
        state = self.manager.get_escalation_state("alert-1")
        assert state is not None
        assert state["time_remaining_seconds"] > 0
        assert state["time_remaining_seconds"] <= 300


# ── Alert Aggregator Tests ───────────────────────────────────────────


class TestAlertAggregator:
    def setup_method(self):
        self.config = AlertConfig(
            aggregation_window_seconds=60,
            max_alerts_per_window=5,
            enable_aggregation=True,
        )
        self.aggregator = AlertAggregator(config=self.config)

    def _make_alert(self, severity=AlertSeverity.INFO, category=AlertCategory.SYSTEM):
        return Alert(
            title="Test",
            message="Test message",
            severity=severity,
            category=category,
        )

    def test_add_alert_to_window(self):
        alert = self._make_alert()
        result = self.aggregator.add_alert(alert)
        assert result is True  # Window not full yet
        assert self.aggregator.get_pending_count() == 1

    def test_add_alerts_fills_window(self):
        for i in range(5):
            result = self.aggregator.add_alert(self._make_alert())
        # On the 5th alert, window is full
        assert result is False
        assert self.aggregator.get_pending_count() == 5

    def test_should_aggregate_enabled(self):
        alert = self._make_alert()
        assert self.aggregator.should_aggregate(alert) is True

    def test_should_aggregate_disabled(self):
        config = AlertConfig(enable_aggregation=False)
        agg = AlertAggregator(config=config)
        alert = self._make_alert()
        assert agg.should_aggregate(alert) is False

    def test_flush_window(self):
        for _ in range(3):
            self.aggregator.add_alert(self._make_alert())
        digest = self.aggregator.flush_window("system")
        assert digest is not None
        assert digest.count == 3
        assert "3 alerts" in digest.summary
        # After flush, window is empty
        assert self.aggregator.get_pending_count() == 0

    def test_flush_empty_window(self):
        digest = self.aggregator.flush_window("system")
        assert digest is None

    def test_digest_severity_counts(self):
        self.aggregator.add_alert(self._make_alert(severity=AlertSeverity.INFO))
        self.aggregator.add_alert(self._make_alert(severity=AlertSeverity.INFO))
        self.aggregator.add_alert(self._make_alert(severity=AlertSeverity.ERROR))
        digest = self.aggregator.flush_window("system")
        assert digest is not None
        assert digest.severity_counts["info"] == 2
        assert digest.severity_counts["error"] == 1

    def test_reset(self):
        self.aggregator.add_alert(self._make_alert())
        self.aggregator.reset()
        assert self.aggregator.get_pending_count() == 0


# ── Channel Dispatcher Tests ────────────────────────────────────────


class TestChannelDispatcher:
    def setup_method(self):
        self.dispatcher = ChannelDispatcher()

    def _make_alert(self):
        return Alert(title="Test", message="M")

    def test_dispatch_single(self):
        alert = self._make_alert()
        result = self.dispatcher.dispatch(alert, ChannelType.EMAIL)
        assert result.success is True
        assert result.channel == ChannelType.EMAIL
        assert result.error is None
        assert result.delivered_at is not None

    def test_dispatch_multi(self):
        alert = self._make_alert()
        channels = [ChannelType.EMAIL, ChannelType.SLACK, ChannelType.SMS]
        results = self.dispatcher.dispatch_multi(alert, channels)
        assert len(results) == 3
        assert all(r.success for r in results)
        assert results[0].channel == ChannelType.EMAIL
        assert results[1].channel == ChannelType.SLACK
        assert results[2].channel == ChannelType.SMS

    def test_delivery_log(self):
        alert = self._make_alert()
        self.dispatcher.dispatch(alert, ChannelType.EMAIL)
        self.dispatcher.dispatch(alert, ChannelType.SLACK)
        log = self.dispatcher.get_delivery_log()
        assert len(log) == 2

    def test_delivery_log_by_alert_id(self):
        a1 = Alert(title="A1", message="M1")
        a2 = Alert(title="A2", message="M2")
        self.dispatcher.dispatch(a1, ChannelType.EMAIL)
        self.dispatcher.dispatch(a2, ChannelType.SLACK)
        self.dispatcher.dispatch(a1, ChannelType.SMS)
        log_a1 = self.dispatcher.get_delivery_log(a1.alert_id)
        assert len(log_a1) == 2
        log_a2 = self.dispatcher.get_delivery_log(a2.alert_id)
        assert len(log_a2) == 1

    def test_channel_stats(self):
        alert = self._make_alert()
        self.dispatcher.dispatch(alert, ChannelType.EMAIL)
        self.dispatcher.dispatch(alert, ChannelType.EMAIL)
        self.dispatcher.dispatch(alert, ChannelType.SLACK)
        stats = self.dispatcher.get_channel_stats()
        assert stats["email"] == 2
        assert stats["slack"] == 1

    def test_clear_log(self):
        alert = self._make_alert()
        self.dispatcher.dispatch(alert, ChannelType.EMAIL)
        self.dispatcher.clear_log()
        assert len(self.dispatcher.get_delivery_log()) == 0
        assert self.dispatcher.get_channel_stats() == {}
