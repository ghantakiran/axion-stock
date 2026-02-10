"""Tests for PRD-121: Event-Driven Architecture & Message Bus."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from src.event_bus import (
    EventPriority,
    DeliveryStatus,
    SubscriberState,
    EventCategory,
    EventBusConfig,
    EventEnvelope,
    SchemaDefinition,
    SchemaRegistry,
    order_executed_event,
    alert_triggered_event,
    model_updated_event,
    compliance_violation_event,
    Subscriber,
    DeliveryRecord,
    EventBus,
    EventRecord,
    Snapshot,
    EventStore,
    ConsumerCheckpoint,
    ConsumerGroup,
    AsyncConsumer,
)


class TestEventBusConfig:
    """Tests for event bus configuration."""

    def setup_method(self):
        self.config = EventBusConfig()

    def test_default_config(self):
        assert self.config.max_subscribers_per_topic == 100
        assert self.config.max_retry_attempts == 3
        assert self.config.dead_letter_enabled is True

    def test_custom_config(self):
        config = EventBusConfig(max_retry_attempts=5, dead_letter_enabled=False)
        assert config.max_retry_attempts == 5
        assert config.dead_letter_enabled is False

    def test_enums(self):
        assert EventPriority.CRITICAL.value == "critical"
        assert DeliveryStatus.DEAD_LETTER.value == "dead_letter"
        assert SubscriberState.PAUSED.value == "paused"
        assert EventCategory.TRADE.value == "trade"


class TestSchemaRegistry:
    """Tests for event schema registry."""

    def setup_method(self):
        self.registry = SchemaRegistry()

    def test_register_schema(self):
        schema = SchemaDefinition(
            event_type="OrderExecuted",
            version=1,
            required_fields=["order_id", "symbol"],
        )
        result = self.registry.register(schema)
        assert result.event_type == "OrderExecuted"

    def test_get_schema_latest(self):
        self.registry.register(SchemaDefinition(
            event_type="OrderExecuted", version=1,
            required_fields=["order_id"],
        ))
        self.registry.register(SchemaDefinition(
            event_type="OrderExecuted", version=2,
            required_fields=["order_id", "symbol"],
        ))
        schema = self.registry.get_schema("OrderExecuted")
        assert schema is not None
        assert schema.version == 2

    def test_get_schema_specific_version(self):
        self.registry.register(SchemaDefinition(
            event_type="OrderExecuted", version=1,
            required_fields=["order_id"],
        ))
        self.registry.register(SchemaDefinition(
            event_type="OrderExecuted", version=2,
            required_fields=["order_id", "symbol"],
        ))
        schema = self.registry.get_schema("OrderExecuted", version=1)
        assert schema is not None
        assert schema.version == 1

    def test_get_schema_not_found(self):
        assert self.registry.get_schema("Unknown") is None

    def test_validate_event_valid(self):
        self.registry.register(SchemaDefinition(
            event_type="OrderExecuted", version=1,
            required_fields=["order_id", "symbol"],
        ))
        event = EventEnvelope(
            event_type="OrderExecuted",
            data={"order_id": "123", "symbol": "AAPL"},
        )
        result = self.registry.validate_event(event)
        assert result["valid"] is True

    def test_validate_event_missing_field(self):
        self.registry.register(SchemaDefinition(
            event_type="OrderExecuted", version=1,
            required_fields=["order_id", "symbol"],
        ))
        event = EventEnvelope(
            event_type="OrderExecuted",
            data={"order_id": "123"},
        )
        result = self.registry.validate_event(event)
        assert result["valid"] is False
        assert len(result["errors"]) == 1

    def test_validate_event_no_schema(self):
        event = EventEnvelope(event_type="Unknown", data={})
        result = self.registry.validate_event(event)
        assert result["valid"] is True  # no schema = passes

    def test_list_schemas(self):
        self.registry.register(SchemaDefinition(event_type="A", version=1))
        self.registry.register(SchemaDefinition(event_type="B", version=1))
        schemas = self.registry.list_schemas()
        assert len(schemas) == 2

    def test_get_versions(self):
        self.registry.register(SchemaDefinition(event_type="A", version=1))
        self.registry.register(SchemaDefinition(event_type="A", version=2))
        versions = self.registry.get_versions("A")
        assert versions == [1, 2]

    def test_is_compatible_backward(self):
        self.registry.register(SchemaDefinition(
            event_type="A", version=1,
            required_fields=["x"],
        ))
        self.registry.register(SchemaDefinition(
            event_type="A", version=2,
            required_fields=["x", "y"],
        ))
        assert self.registry.is_compatible("A", 1, 2) is True

    def test_is_compatible_breaking(self):
        self.registry.register(SchemaDefinition(
            event_type="A", version=1,
            required_fields=["x", "y"],
        ))
        self.registry.register(SchemaDefinition(
            event_type="A", version=2,
            required_fields=["z"],
        ))
        assert self.registry.is_compatible("A", 1, 2) is False

    def test_is_compatible_missing_schema(self):
        assert self.registry.is_compatible("X", 1, 2) is False


class TestEventFactories:
    """Tests for built-in event factory functions."""

    def test_order_executed_event(self):
        event = order_executed_event("o1", "AAPL", "buy", 100.0, 150.5)
        assert event.event_type == "OrderExecuted"
        assert event.category == EventCategory.ORDER
        assert event.priority == EventPriority.HIGH
        assert event.data["symbol"] == "AAPL"
        assert event.data["quantity"] == 100.0

    def test_alert_triggered_event(self):
        event = alert_triggered_event("a1", "critical", "Price alert")
        assert event.event_type == "AlertTriggered"
        assert event.priority == EventPriority.HIGH

    def test_alert_triggered_non_critical(self):
        event = alert_triggered_event("a1", "warning", "Low volume")
        assert event.priority == EventPriority.NORMAL

    def test_model_updated_event(self):
        event = model_updated_event("m1", "ranking_model", "v2.0")
        assert event.event_type == "ModelUpdated"
        assert event.category == EventCategory.MODEL

    def test_compliance_violation_event(self):
        event = compliance_violation_event("v1", "position_limit", "Exceeded 5%")
        assert event.event_type == "ComplianceViolation"
        assert event.priority == EventPriority.CRITICAL

    def test_factory_extra_data(self):
        event = order_executed_event("o1", "TSLA", "sell", 50.0, 200.0, broker="alpaca")
        assert event.data["broker"] == "alpaca"


class TestEventBus:
    """Tests for the event bus."""

    def setup_method(self):
        self.bus = EventBus()
        self.received_events: list[EventEnvelope] = []

    def _handler(self, event: EventEnvelope) -> None:
        self.received_events.append(event)

    def test_subscribe(self):
        sub = self.bus.subscribe("test_sub", "orders.*", self._handler)
        assert sub.name == "test_sub"
        assert sub.state == SubscriberState.ACTIVE

    def test_unsubscribe(self):
        sub = self.bus.subscribe("test_sub", "*", self._handler)
        assert self.bus.unsubscribe(sub.subscriber_id) is True
        assert self.bus.unsubscribe("nonexistent") is False

    def test_publish_and_deliver(self):
        self.bus.subscribe("sub1", "*", self._handler)
        event = order_executed_event("o1", "AAPL", "buy", 100.0, 150.0)
        records = self.bus.publish("orders.executed", event)
        assert len(records) == 1
        assert records[0].status == DeliveryStatus.DELIVERED
        assert len(self.received_events) == 1

    def test_publish_multiple_subscribers(self):
        received1: list[EventEnvelope] = []
        received2: list[EventEnvelope] = []
        self.bus.subscribe("sub1", "*", lambda e: received1.append(e))
        self.bus.subscribe("sub2", "*", lambda e: received2.append(e))
        event = order_executed_event("o1", "AAPL", "buy", 100.0, 150.0)
        self.bus.publish("orders", event)
        assert len(received1) == 1
        assert len(received2) == 1

    def test_publish_no_matching_subscribers(self):
        self.bus.subscribe("sub1", "orders", self._handler)
        event = order_executed_event("o1", "AAPL", "buy", 100.0, 150.0)
        records = self.bus.publish("alerts", event)
        assert len(records) == 0

    def test_subscriber_filter(self):
        self.bus.subscribe(
            "sub1", "*", self._handler,
            filter_fn=lambda e: e.data.get("symbol") == "AAPL",
        )
        e1 = order_executed_event("o1", "AAPL", "buy", 100.0, 150.0)
        e2 = order_executed_event("o2", "TSLA", "sell", 50.0, 200.0)
        self.bus.publish("orders", e1)
        self.bus.publish("orders", e2)
        assert len(self.received_events) == 1
        assert self.received_events[0].data["symbol"] == "AAPL"

    def test_handler_failure_dead_letter(self):
        def bad_handler(e: EventEnvelope) -> None:
            raise ValueError("Processing error")

        self.bus.subscribe("sub1", "*", bad_handler)
        event = order_executed_event("o1", "AAPL", "buy", 100.0, 150.0)
        records = self.bus.publish("orders", event)
        assert records[0].status == DeliveryStatus.DEAD_LETTER
        assert len(self.bus.get_dead_letters()) == 1

    def test_handler_failure_no_dead_letter(self):
        config = EventBusConfig(dead_letter_enabled=False, max_retry_attempts=1)
        bus = EventBus(config)

        def bad_handler(e: EventEnvelope) -> None:
            raise ValueError("fail")

        bus.subscribe("sub1", "*", bad_handler)
        event = order_executed_event("o1", "AAPL", "buy", 100.0, 150.0)
        records = bus.publish("orders", event)
        assert records[0].status == DeliveryStatus.FAILED

    def test_pause_resume_subscriber(self):
        sub = self.bus.subscribe("sub1", "*", self._handler)
        assert self.bus.pause_subscriber(sub.subscriber_id) is True
        event = order_executed_event("o1", "AAPL", "buy", 100.0, 150.0)
        self.bus.publish("orders", event)
        assert len(self.received_events) == 0  # paused

        self.bus.resume_subscriber(sub.subscriber_id)
        self.bus.publish("orders", event)
        assert len(self.received_events) == 1

    def test_pause_nonexistent(self):
        assert self.bus.pause_subscriber("fake") is False
        assert self.bus.resume_subscriber("fake") is False

    def test_clear_dead_letters(self):
        def bad_handler(e: EventEnvelope) -> None:
            raise ValueError("fail")

        self.bus.subscribe("sub1", "*", bad_handler)
        self.bus.publish("t", order_executed_event("o1", "A", "b", 1.0, 1.0))
        assert self.bus.clear_dead_letters() == 1
        assert len(self.bus.get_dead_letters()) == 0

    def test_delivery_log(self):
        self.bus.subscribe("sub1", "*", self._handler)
        event = order_executed_event("o1", "AAPL", "buy", 100.0, 150.0)
        self.bus.publish("orders", event)
        log = self.bus.get_delivery_log(event_id=event.event_id)
        assert len(log) == 1
        assert log[0].status == DeliveryStatus.DELIVERED

    def test_statistics(self):
        self.bus.subscribe("sub1", "*", self._handler)
        self.bus.publish("t", order_executed_event("o1", "A", "b", 1.0, 1.0))
        stats = self.bus.get_statistics()
        assert stats["total_subscribers"] == 1
        assert stats["total_published"] == 1
        assert stats["total_delivered"] == 1

    def test_no_handler_delivery(self):
        self.bus.subscribe("sub1", "*")  # no handler
        event = order_executed_event("o1", "AAPL", "buy", 100.0, 150.0)
        records = self.bus.publish("orders", event)
        assert records[0].status == DeliveryStatus.DELIVERED


class TestEventStore:
    """Tests for the event store."""

    def setup_method(self):
        self.store = EventStore()

    def test_append_event(self):
        event = order_executed_event("o1", "AAPL", "buy", 100.0, 150.0)
        record = self.store.append(event)
        assert record.sequence_number == 1
        assert record.event is event

    def test_append_with_aggregate(self):
        event = order_executed_event("o1", "AAPL", "buy", 100.0, 150.0)
        record = self.store.append(event, aggregate_id="order-o1", aggregate_type="Order")
        assert record.aggregate_id == "order-o1"

    def test_get_event(self):
        event = order_executed_event("o1", "AAPL", "buy", 100.0, 150.0)
        self.store.append(event)
        retrieved = self.store.get_event(1)
        assert retrieved is not None
        assert retrieved.event.event_id == event.event_id

    def test_get_event_not_found(self):
        assert self.store.get_event(0) is None
        assert self.store.get_event(999) is None

    def test_replay_all(self):
        for i in range(5):
            self.store.append(order_executed_event(f"o{i}", "AAPL", "buy", 1.0, 1.0))
        events = self.store.replay()
        assert len(events) == 5

    def test_replay_range(self):
        for i in range(5):
            self.store.append(order_executed_event(f"o{i}", "AAPL", "buy", 1.0, 1.0))
        events = self.store.replay(from_sequence=2, to_sequence=4)
        assert len(events) == 3

    def test_replay_by_type(self):
        self.store.append(order_executed_event("o1", "AAPL", "buy", 1.0, 1.0))
        self.store.append(alert_triggered_event("a1", "critical", "Alert"))
        self.store.append(order_executed_event("o2", "TSLA", "sell", 1.0, 1.0))
        events = self.store.replay(event_type="OrderExecuted")
        assert len(events) == 2

    def test_get_aggregate_events(self):
        self.store.append(
            order_executed_event("o1", "AAPL", "buy", 100.0, 150.0),
            aggregate_id="order-1",
        )
        self.store.append(
            alert_triggered_event("a1", "info", "unrelated"),
        )
        self.store.append(
            order_executed_event("o1", "AAPL", "buy", 50.0, 151.0),
            aggregate_id="order-1",
        )
        events = self.store.get_aggregate_events("order-1")
        assert len(events) == 2

    def test_create_snapshot(self):
        self.store.append(
            order_executed_event("o1", "AAPL", "buy", 100.0, 150.0),
            aggregate_id="order-1",
            aggregate_type="Order",
        )
        snapshot = self.store.create_snapshot(
            "order-1", "Order", {"status": "filled", "quantity": 100},
        )
        assert snapshot.aggregate_id == "order-1"
        assert snapshot.state["status"] == "filled"

    def test_get_snapshot(self):
        self.store.append(
            order_executed_event("o1", "AAPL", "buy", 100.0, 150.0),
            aggregate_id="order-1",
        )
        self.store.create_snapshot("order-1", "Order", {"filled": True})
        snapshot = self.store.get_snapshot("order-1")
        assert snapshot is not None
        assert snapshot.state["filled"] is True

    def test_get_snapshot_not_found(self):
        assert self.store.get_snapshot("nonexistent") is None

    def test_replay_from_snapshot(self):
        self.store.append(
            order_executed_event("o1", "AAPL", "buy", 100.0, 150.0),
            aggregate_id="order-1",
        )
        self.store.create_snapshot("order-1", "Order", {"step": 1})
        self.store.append(
            order_executed_event("o2", "AAPL", "sell", 50.0, 155.0),
            aggregate_id="order-1",
        )
        snapshot, events = self.store.replay_from_snapshot("order-1")
        assert snapshot is not None
        assert len(events) == 1  # only events after snapshot

    def test_replay_from_snapshot_no_snapshot(self):
        self.store.append(
            order_executed_event("o1", "AAPL", "buy", 100.0, 150.0),
            aggregate_id="order-1",
        )
        snapshot, events = self.store.replay_from_snapshot("order-1")
        assert snapshot is None
        assert len(events) == 1

    def test_size(self):
        assert self.store.size == 0
        self.store.append(order_executed_event("o1", "A", "b", 1.0, 1.0))
        assert self.store.size == 1

    def test_statistics(self):
        self.store.append(order_executed_event("o1", "A", "b", 1.0, 1.0))
        self.store.append(alert_triggered_event("a1", "info", "test"))
        stats = self.store.get_statistics()
        assert stats["total_events"] == 2
        assert stats["event_types"]["OrderExecuted"] == 1
        assert stats["event_types"]["AlertTriggered"] == 1


class TestAsyncConsumer:
    """Tests for the async consumer."""

    def setup_method(self):
        self.store = EventStore()
        self.consumer = AsyncConsumer(self.store)
        self.processed: list[EventEnvelope] = []

    def _handler(self, event: EventEnvelope) -> None:
        self.processed.append(event)

    def test_create_group(self):
        group = self.consumer.create_group("test_group", "*", self._handler)
        assert group.name == "test_group"
        assert group.active is True

    def test_add_member(self):
        group = self.consumer.create_group("g1", "*")
        assert self.consumer.add_member(group.group_id, "worker-1") is True
        assert "worker-1" in group.members

    def test_add_member_nonexistent_group(self):
        assert self.consumer.add_member("fake", "worker-1") is False

    def test_remove_member(self):
        group = self.consumer.create_group("g1", "*")
        self.consumer.add_member(group.group_id, "worker-1")
        assert self.consumer.remove_member(group.group_id, "worker-1") is True
        assert "worker-1" not in group.members

    def test_remove_member_not_found(self):
        group = self.consumer.create_group("g1", "*")
        assert self.consumer.remove_member(group.group_id, "fake") is False

    def test_consume_events(self):
        self.store.append(order_executed_event("o1", "AAPL", "buy", 1.0, 1.0))
        self.store.append(order_executed_event("o2", "TSLA", "sell", 1.0, 1.0))
        group = self.consumer.create_group("g1", "*", self._handler)
        result = self.consumer.consume(group.group_id)
        assert result["processed"] == 2
        assert len(self.processed) == 2

    def test_consume_no_new_events(self):
        self.store.append(order_executed_event("o1", "AAPL", "buy", 1.0, 1.0))
        group = self.consumer.create_group("g1", "*", self._handler)
        self.consumer.consume(group.group_id)
        result = self.consumer.consume(group.group_id)
        assert result["processed"] == 0  # already consumed

    def test_consume_with_errors(self):
        self.store.append(order_executed_event("o1", "AAPL", "buy", 1.0, 1.0))

        def bad_handler(e: EventEnvelope) -> None:
            raise ValueError("fail")

        group = self.consumer.create_group("g1", "*", bad_handler)
        result = self.consumer.consume(group.group_id)
        assert result["failed"] == 1
        assert len(self.consumer.get_errors()) == 1

    def test_consume_nonexistent_group(self):
        result = self.consumer.consume("fake")
        assert result["error"] == "Group not found"

    def test_consume_inactive_group(self):
        group = self.consumer.create_group("g1", "*", self._handler)
        self.consumer.pause_group(group.group_id)
        result = self.consumer.consume(group.group_id)
        assert result["error"] == "Group is inactive"

    def test_checkpoint_tracking(self):
        self.store.append(order_executed_event("o1", "A", "b", 1.0, 1.0))
        self.store.append(order_executed_event("o2", "B", "s", 1.0, 1.0))
        group = self.consumer.create_group("g1", "*", self._handler)
        self.consumer.consume(group.group_id)
        cp = self.consumer.get_checkpoint(group.group_id)
        assert cp is not None
        assert cp.last_sequence == 2
        assert cp.events_processed == 2

    def test_reset_checkpoint(self):
        self.store.append(order_executed_event("o1", "A", "b", 1.0, 1.0))
        group = self.consumer.create_group("g1", "*", self._handler)
        self.consumer.consume(group.group_id)
        assert self.consumer.reset_checkpoint(group.group_id, 0) is True
        result = self.consumer.consume(group.group_id)
        assert result["processed"] == 1  # re-consumed

    def test_reset_checkpoint_nonexistent(self):
        assert self.consumer.reset_checkpoint("fake") is False

    def test_pause_resume_group(self):
        group = self.consumer.create_group("g1", "*", self._handler)
        assert self.consumer.pause_group(group.group_id) is True
        assert group.active is False
        assert self.consumer.resume_group(group.group_id) is True
        assert group.active is True

    def test_pause_nonexistent(self):
        assert self.consumer.pause_group("fake") is False
        assert self.consumer.resume_group("fake") is False

    def test_get_group(self):
        group = self.consumer.create_group("g1", "*")
        retrieved = self.consumer.get_group(group.group_id)
        assert retrieved is not None
        assert retrieved.name == "g1"

    def test_list_groups(self):
        self.consumer.create_group("g1", "*")
        self.consumer.create_group("g2", "orders")
        groups = self.consumer.list_groups()
        assert len(groups) == 2

    def test_consume_max_events(self):
        for i in range(10):
            self.store.append(order_executed_event(f"o{i}", "A", "b", 1.0, 1.0))
        group = self.consumer.create_group("g1", "*", self._handler)
        result = self.consumer.consume(group.group_id, max_events=3)
        assert result["processed"] == 3

    def test_statistics(self):
        self.store.append(order_executed_event("o1", "A", "b", 1.0, 1.0))
        group = self.consumer.create_group("g1", "*", self._handler)
        self.consumer.consume(group.group_id)
        stats = self.consumer.get_statistics()
        assert stats["total_groups"] == 1
        assert stats["total_processed"] == 1


class TestEventBusDataclasses:
    """Tests for dataclass models."""

    def test_event_envelope(self):
        event = EventEnvelope(event_type="Test", data={"key": "val"})
        assert event.event_id  # auto-generated
        assert event.timestamp is not None
        assert event.version == 1

    def test_event_envelope_correlation(self):
        event = EventEnvelope(
            event_type="Test",
            correlation_id="corr-1",
            causation_id="cause-1",
        )
        assert event.correlation_id == "corr-1"
        assert event.causation_id == "cause-1"

    def test_schema_definition(self):
        schema = SchemaDefinition(
            event_type="OrderExecuted",
            required_fields=["order_id"],
        )
        assert schema.schema_id
        assert schema.version == 1

    def test_subscriber(self):
        sub = Subscriber(name="test", topic_pattern="orders.*")
        assert sub.subscriber_id
        assert sub.state == SubscriberState.ACTIVE

    def test_delivery_record(self):
        record = DeliveryRecord(event_id="e1", subscriber_id="s1")
        assert record.status == DeliveryStatus.PENDING
        assert record.attempts == 0

    def test_event_record(self):
        record = EventRecord(sequence_number=1)
        assert record.stored_at is not None

    def test_snapshot(self):
        snap = Snapshot(aggregate_id="a1", state={"key": "val"})
        assert snap.snapshot_id
        assert snap.state["key"] == "val"

    def test_consumer_checkpoint(self):
        cp = ConsumerCheckpoint(consumer_id="c1", topic="orders")
        assert cp.last_sequence == 0
        assert cp.events_processed == 0

    def test_consumer_group(self):
        group = ConsumerGroup(name="g1", topic="*")
        assert group.group_id
        assert group.active is True
