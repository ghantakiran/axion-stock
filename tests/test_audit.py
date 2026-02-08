"""Tests for PRD-109: Audit Trail & Event Sourcing."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from src.audit.config import AuditConfig, EventCategory, EventOutcome, RetentionPolicy
from src.audit.events import Actor, AuditEvent, Resource
from src.audit.recorder import AuditRecorder
from src.audit.query import AuditQuery
from src.audit.export import AuditExporter


class TestAuditConfig:
    """Tests for audit configuration."""

    def test_default_config(self):
        config = AuditConfig()
        assert config.enabled is True
        assert config.buffer_size == 100
        assert config.hash_algorithm == "sha256"
        assert config.genesis_hash == "genesis"

    def test_custom_config(self):
        config = AuditConfig(buffer_size=50, enabled=False)
        assert config.buffer_size == 50
        assert config.enabled is False

    def test_event_category_enum(self):
        assert EventCategory.TRADING.value == "trading"
        assert EventCategory.AUTH.value == "auth"
        assert EventCategory.SYSTEM.value == "system"

    def test_event_outcome_enum(self):
        assert EventOutcome.SUCCESS.value == "success"
        assert EventOutcome.FAILURE.value == "failure"
        assert EventOutcome.DENIED.value == "denied"

    def test_retention_policy(self):
        policy = RetentionPolicy(category=EventCategory.TRADING, retention_days=730)
        assert policy.retention_days == 730
        assert policy.is_expired(800) is True
        assert policy.is_expired(100) is False

    def test_retention_archivable(self):
        policy = RetentionPolicy(category=EventCategory.TRADING, archive_after_days=90)
        assert policy.is_archivable(100) is True
        assert policy.is_archivable(50) is False

    def test_get_retention_policy(self):
        config = AuditConfig()
        policy = config.get_retention_policy(EventCategory.TRADING)
        assert policy.retention_days == 365

    def test_categories_default(self):
        config = AuditConfig()
        assert EventCategory.TRADING in config.categories


class TestActor:
    """Tests for Actor dataclass."""

    def test_actor_creation(self):
        actor = Actor(actor_id="user_42", actor_type="user")
        assert actor.actor_id == "user_42"
        assert actor.actor_type == "user"

    def test_actor_to_dict(self):
        actor = Actor(actor_id="u1", ip_address="10.0.0.1")
        d = actor.to_dict()
        assert d["actor_id"] == "u1"
        assert d["ip_address"] == "10.0.0.1"

    def test_actor_optional_fields(self):
        actor = Actor(actor_id="u1")
        assert actor.ip_address is None
        assert actor.session_id is None


class TestResource:
    """Tests for Resource dataclass."""

    def test_resource_creation(self):
        resource = Resource(resource_type="order", resource_id="ord-123")
        assert resource.resource_type == "order"

    def test_resource_to_dict(self):
        resource = Resource(resource_type="order", resource_id="123", name="Buy AAPL")
        d = resource.to_dict()
        assert d["name"] == "Buy AAPL"


class TestAuditEvent:
    """Tests for AuditEvent dataclass."""

    def test_event_creation(self):
        event = AuditEvent(action="order.create")
        assert event.action == "order.create"
        assert event.event_id != ""
        assert event.timestamp is not None

    def test_compute_hash(self):
        event = AuditEvent(action="test")
        h = event.compute_hash("genesis")
        assert len(h) == 64  # SHA-256 hex

    def test_hash_deterministic(self):
        event = AuditEvent(action="test", event_id="fixed", timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc))
        h1 = event.compute_hash("genesis")
        h2 = event.compute_hash("genesis")
        assert h1 == h2

    def test_hash_changes_with_previous(self):
        event = AuditEvent(action="test")
        h1 = event.compute_hash("genesis")
        h2 = event.compute_hash("other")
        assert h1 != h2

    def test_to_dict(self):
        actor = Actor(actor_id="u1")
        resource = Resource(resource_type="order", resource_id="123")
        event = AuditEvent(action="order.create", actor=actor, resource=resource)
        d = event.to_dict()
        assert d["action"] == "order.create"
        assert d["actor"]["actor_id"] == "u1"
        assert d["resource"]["resource_type"] == "order"

    def test_from_dict(self):
        original = AuditEvent(
            action="test",
            actor=Actor(actor_id="u1"),
            resource=Resource(resource_type="x", resource_id="1"),
            category=EventCategory.TRADING,
        )
        d = original.to_dict()
        restored = AuditEvent.from_dict(d)
        assert restored.action == "test"
        assert restored.actor.actor_id == "u1"
        assert restored.category == EventCategory.TRADING

    def test_event_default_category(self):
        event = AuditEvent(action="test")
        assert event.category == EventCategory.SYSTEM


class TestAuditRecorder:
    """Tests for audit event recorder."""

    def setup_method(self):
        AuditRecorder.reset_instance()

    def test_record_event(self):
        recorder = AuditRecorder()
        event = recorder.record(action="order.create")
        assert event.action == "order.create"
        assert event.event_hash != ""
        assert event.previous_hash == "genesis"

    def test_hash_chain(self):
        recorder = AuditRecorder()
        e1 = recorder.record(action="first")
        e2 = recorder.record(action="second")
        assert e2.previous_hash == e1.event_hash

    def test_event_count(self):
        recorder = AuditRecorder()
        recorder.record(action="a")
        recorder.record(action="b")
        assert recorder.event_count == 2

    def test_flush(self):
        recorder = AuditRecorder(AuditConfig(buffer_size=100))
        recorder.record(action="a")
        recorder.record(action="b")
        count = recorder.flush()
        assert count == 2
        assert len(recorder.events) == 2
        assert len(recorder.buffer) == 0

    def test_auto_flush_on_buffer_full(self):
        recorder = AuditRecorder(AuditConfig(buffer_size=3))
        recorder.record(action="a")
        recorder.record(action="b")
        recorder.record(action="c")
        # Buffer should have been flushed
        assert len(recorder.events) == 3

    def test_verify_integrity_valid(self):
        recorder = AuditRecorder()
        recorder.record(action="a")
        recorder.record(action="b")
        recorder.record(action="c")
        recorder.flush()
        assert recorder.verify_integrity() is True

    def test_verify_integrity_tampering(self):
        recorder = AuditRecorder()
        recorder.record(action="a")
        recorder.record(action="b")
        recorder.flush()
        # Tamper with an event
        recorder._events[0].event_hash = "tampered"
        assert recorder.verify_integrity() is False

    def test_find_tampering(self):
        recorder = AuditRecorder()
        recorder.record(action="a")
        recorder.flush()
        recorder._events[0].event_hash = "tampered"
        issues = recorder.find_tampering()
        assert len(issues) > 0

    def test_singleton(self):
        a = AuditRecorder.get_instance()
        b = AuditRecorder.get_instance()
        assert a is b

    def test_reset_instance(self):
        a = AuditRecorder.get_instance()
        AuditRecorder.reset_instance()
        b = AuditRecorder.get_instance()
        assert a is not b

    def test_record_with_actor(self):
        recorder = AuditRecorder()
        actor = Actor(actor_id="user_42")
        event = recorder.record(action="login", actor=actor, category=EventCategory.AUTH)
        assert event.actor.actor_id == "user_42"
        assert event.category == EventCategory.AUTH

    def test_record_disabled(self):
        recorder = AuditRecorder(AuditConfig(enabled=False))
        event = recorder.record(action="test")
        assert event.event_hash == ""

    def test_clear(self):
        recorder = AuditRecorder()
        recorder.record(action="a")
        recorder.flush()
        recorder.clear()
        assert recorder.event_count == 0

    def test_get_all_events(self):
        recorder = AuditRecorder()
        recorder.record(action="a")
        recorder.flush()
        recorder.record(action="b")
        all_events = recorder.get_all_events()
        assert len(all_events) == 2


class TestAuditQuery:
    """Tests for audit query builder."""

    def _create_recorder_with_events(self):
        recorder = AuditRecorder()
        recorder.record(
            action="order.create",
            actor=Actor(actor_id="user_42", actor_type="user"),
            resource=Resource(resource_type="order", resource_id="1"),
            category=EventCategory.TRADING,
        )
        recorder.record(
            action="order.cancel",
            actor=Actor(actor_id="user_42", actor_type="user"),
            resource=Resource(resource_type="order", resource_id="2"),
            category=EventCategory.TRADING,
        )
        recorder.record(
            action="config.update",
            actor=Actor(actor_id="admin", actor_type="admin"),
            category=EventCategory.CONFIG,
        )
        recorder.record(
            action="user.login",
            actor=Actor(actor_id="user_17", actor_type="user"),
            category=EventCategory.AUTH,
        )
        recorder.flush()
        return recorder

    def setup_method(self):
        AuditRecorder.reset_instance()

    def test_filter_by_actor(self):
        recorder = self._create_recorder_with_events()
        results = AuditQuery(recorder).filter_by_actor("user_42").execute()
        assert len(results) == 2

    def test_filter_by_action(self):
        recorder = self._create_recorder_with_events()
        results = AuditQuery(recorder).filter_by_action("order.create").execute()
        assert len(results) == 1

    def test_filter_by_action_prefix(self):
        recorder = self._create_recorder_with_events()
        results = AuditQuery(recorder).filter_by_action_prefix("order.").execute()
        assert len(results) == 2

    def test_filter_by_category(self):
        recorder = self._create_recorder_with_events()
        results = AuditQuery(recorder).filter_by_category(EventCategory.TRADING).execute()
        assert len(results) == 2

    def test_filter_by_time_range(self):
        recorder = self._create_recorder_with_events()
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)
        results = AuditQuery(recorder).filter_by_time_range(start, end).execute()
        assert len(results) == 4

    def test_chained_filters(self):
        recorder = self._create_recorder_with_events()
        results = (
            AuditQuery(recorder)
            .filter_by_actor("user_42")
            .filter_by_category(EventCategory.TRADING)
            .execute()
        )
        assert len(results) == 2

    def test_paginate(self):
        recorder = self._create_recorder_with_events()
        results = AuditQuery(recorder).paginate(page=1, page_size=2).execute()
        assert len(results) == 2

    def test_paginate_page_2(self):
        recorder = self._create_recorder_with_events()
        results = AuditQuery(recorder).paginate(page=2, page_size=2).execute()
        assert len(results) == 2

    def test_limit(self):
        recorder = self._create_recorder_with_events()
        results = AuditQuery(recorder).limit(1).execute()
        assert len(results) == 1

    def test_count(self):
        recorder = self._create_recorder_with_events()
        count = AuditQuery(recorder).filter_by_actor("user_42").count()
        assert count == 2

    def test_sort_descending(self):
        recorder = self._create_recorder_with_events()
        results = AuditQuery(recorder).sort_descending().execute()
        assert results[0].timestamp >= results[-1].timestamp


class TestAuditExporter:
    """Tests for audit export."""

    def _create_events(self):
        AuditRecorder.reset_instance()
        recorder = AuditRecorder()
        recorder.record(
            action="order.create",
            actor=Actor(actor_id="user_42"),
            resource=Resource(resource_type="order", resource_id="1"),
            category=EventCategory.TRADING,
        )
        recorder.record(
            action="user.login",
            actor=Actor(actor_id="user_17"),
            category=EventCategory.AUTH,
        )
        recorder.flush()
        return recorder.events

    def test_export_json(self):
        events = self._create_events()
        exporter = AuditExporter(events)
        output = exporter.export_json()
        lines = output.strip().split("\n")
        assert len(lines) == 2
        parsed = json.loads(lines[0])
        assert "action" in parsed

    def test_export_csv(self):
        events = self._create_events()
        exporter = AuditExporter(events)
        output = exporter.export_csv()
        lines = output.strip().split("\n")
        assert len(lines) == 3  # header + 2 rows
        assert "event_id" in lines[0]

    def test_export_csv_empty(self):
        exporter = AuditExporter([])
        assert exporter.export_csv() == ""

    def test_compliance_report(self):
        events = self._create_events()
        exporter = AuditExporter(events)
        report = exporter.generate_compliance_report()
        assert report["summary"]["total_events"] == 2
        assert report["summary"]["unique_actors"] == 2

    def test_compliance_report_json(self):
        events = self._create_events()
        exporter = AuditExporter(events)
        json_str = exporter.export_report_json()
        parsed = json.loads(json_str)
        assert "summary" in parsed

    def test_set_events(self):
        exporter = AuditExporter()
        assert len(exporter.events) == 0
        events = self._create_events()
        exporter.events = events
        assert len(exporter.events) == 2
