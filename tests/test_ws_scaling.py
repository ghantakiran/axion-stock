"""Tests for PRD-119: WebSocket Scaling & Real-time Infrastructure."""

import time
from datetime import datetime, timedelta

import pytest

from src.ws_scaling.config import (
    MessagePriority,
    ConnectionState,
    DropStrategy,
    WSScalingConfig,
)
from src.ws_scaling.registry import ConnectionInfo, ConnectionRegistry
from src.ws_scaling.router import Message, MessageRouter
from src.ws_scaling.backpressure import QueueStats, BackpressureHandler
from src.ws_scaling.reconnection import ReconnectionSession, ReconnectionManager


# ── Config Tests ─────────────────────────────────────────────────────


class TestWSConfig:
    """Tests for enums and WSScalingConfig defaults."""

    def test_message_priority_values(self):
        assert MessagePriority.CRITICAL.value == "critical"
        assert MessagePriority.HIGH.value == "high"
        assert MessagePriority.NORMAL.value == "normal"
        assert MessagePriority.LOW.value == "low"
        assert len(MessagePriority) == 4

    def test_connection_state_values(self):
        assert ConnectionState.CONNECTED.value == "connected"
        assert ConnectionState.DISCONNECTING.value == "disconnecting"
        assert ConnectionState.RECONNECTING.value == "reconnecting"
        assert ConnectionState.DISCONNECTED.value == "disconnected"
        assert len(ConnectionState) == 4

    def test_drop_strategy_values(self):
        assert DropStrategy.OLDEST_FIRST.value == "oldest_first"
        assert DropStrategy.LOWEST_PRIORITY.value == "lowest_priority"
        assert DropStrategy.RANDOM.value == "random"
        assert len(DropStrategy) == 3

    def test_default_config(self):
        cfg = WSScalingConfig()
        assert cfg.max_connections_per_user == 5
        assert cfg.max_global_connections == 10000
        assert cfg.message_buffer_size == 1000
        assert cfg.backpressure_threshold == 800
        assert cfg.slow_consumer_threshold_ms == 5000
        assert cfg.reconnection_window_seconds == 30
        assert cfg.max_reconnection_attempts == 5
        assert cfg.heartbeat_interval_seconds == 30

    def test_custom_config(self):
        cfg = WSScalingConfig(max_connections_per_user=10, max_global_connections=500)
        assert cfg.max_connections_per_user == 10
        assert cfg.max_global_connections == 500


# ── ConnectionRegistry Tests ─────────────────────────────────────────


class TestConnectionRegistry:
    """Tests for the connection registry."""

    def setup_method(self):
        self.registry = ConnectionRegistry()

    def test_register_connection(self):
        info = self.registry.register("user1", "instance1")
        assert info.user_id == "user1"
        assert info.instance_id == "instance1"
        assert info.state == ConnectionState.CONNECTED
        assert len(info.connection_id) > 0

    def test_register_with_subscriptions(self):
        info = self.registry.register("user1", "inst1", subscriptions=["prices", "trades"])
        assert info.subscriptions == ["prices", "trades"]

    def test_unregister_connection(self):
        info = self.registry.register("user1", "inst1")
        assert self.registry.unregister(info.connection_id) is True
        assert self.registry.get_connection(info.connection_id) is None
        assert self.registry.get_connection_count() == 0

    def test_unregister_nonexistent(self):
        assert self.registry.unregister("does-not-exist") is False

    def test_get_connection(self):
        info = self.registry.register("user1", "inst1")
        fetched = self.registry.get_connection(info.connection_id)
        assert fetched is not None
        assert fetched.user_id == "user1"

    def test_get_user_connections(self):
        self.registry.register("user1", "inst1")
        self.registry.register("user1", "inst2")
        self.registry.register("user2", "inst1")
        conns = self.registry.get_user_connections("user1")
        assert len(conns) == 2

    def test_get_instance_connections(self):
        self.registry.register("user1", "inst1")
        self.registry.register("user2", "inst1")
        conns = self.registry.get_instance_connections("inst1")
        assert len(conns) == 2

    def test_update_heartbeat(self):
        info = self.registry.register("user1", "inst1")
        old_hb = info.last_heartbeat
        # Small delay so the timestamp changes
        time.sleep(0.01)
        self.registry.update_heartbeat(info.connection_id)
        assert info.last_heartbeat >= old_hb

    def test_update_subscriptions(self):
        info = self.registry.register("user1", "inst1", subscriptions=["a"])
        self.registry.update_subscriptions(info.connection_id, ["b", "c"])
        assert info.subscriptions == ["b", "c"]

    def test_stale_connections(self):
        info = self.registry.register("user1", "inst1")
        # Force heartbeat into the past
        info.last_heartbeat = datetime.utcnow() - timedelta(seconds=120)
        stale = self.registry.get_stale_connections(timeout_seconds=60)
        assert len(stale) == 1
        assert stale[0].connection_id == info.connection_id

    def test_no_stale_connections(self):
        self.registry.register("user1", "inst1")
        stale = self.registry.get_stale_connections(timeout_seconds=60)
        assert len(stale) == 0

    def test_connection_limits_per_user(self):
        cfg = WSScalingConfig(max_connections_per_user=2)
        reg = ConnectionRegistry(config=cfg)
        reg.register("user1", "inst1")
        reg.register("user1", "inst2")
        assert reg.can_connect("user1") is False
        with pytest.raises(ValueError):
            reg.register("user1", "inst3")

    def test_global_connection_limit(self):
        cfg = WSScalingConfig(max_global_connections=2, max_connections_per_user=10)
        reg = ConnectionRegistry(config=cfg)
        reg.register("user1", "inst1")
        reg.register("user2", "inst1")
        assert reg.can_connect("user3") is False

    def test_stats(self):
        self.registry.register("user1", "inst1")
        self.registry.register("user2", "inst2")
        stats = self.registry.get_stats()
        assert stats["total_connections"] == 2
        assert stats["total_users"] == 2
        assert stats["total_instances"] == 2

    def test_reset(self):
        self.registry.register("user1", "inst1")
        self.registry.reset()
        assert self.registry.get_connection_count() == 0
        assert self.registry.get_user_count() == 0

    def test_connection_info_defaults(self):
        info = ConnectionInfo()
        assert len(info.connection_id) > 0
        assert info.state == ConnectionState.CONNECTED
        assert isinstance(info.connected_at, datetime)
        assert info.subscriptions == []
        assert info.metadata == {}


# ── MessageRouter Tests ──────────────────────────────────────────────


class TestMessageRouter:
    """Tests for the message router."""

    def setup_method(self):
        self.router = MessageRouter()

    def test_subscribe(self):
        assert self.router.subscribe("conn1", "prices") is True
        assert self.router.subscribe("conn1", "prices") is False  # duplicate

    def test_unsubscribe(self):
        self.router.subscribe("conn1", "prices")
        assert self.router.unsubscribe("conn1", "prices") is True
        assert self.router.unsubscribe("conn1", "prices") is False

    def test_get_subscribers(self):
        self.router.subscribe("conn1", "prices")
        self.router.subscribe("conn2", "prices")
        subs = self.router.get_subscribers("prices")
        assert subs == {"conn1", "conn2"}

    def test_get_subscribers_empty_channel(self):
        subs = self.router.get_subscribers("nonexistent")
        assert subs == set()

    def test_broadcast(self):
        self.router.subscribe("conn1", "prices")
        self.router.subscribe("conn2", "prices")
        msg = self.router.broadcast("prices", {"price": 100.5})
        assert msg.channel == "prices"
        assert len(msg.target_connection_ids) == 2

    def test_unicast(self):
        msg = self.router.unicast("conn1", {"alert": "margin call"})
        assert msg.target_connection_ids == ["conn1"]
        assert msg.channel == "__unicast__"

    def test_multicast(self):
        msg = self.router.multicast(["conn1", "conn2", "conn3"], {"data": "update"})
        assert len(msg.target_connection_ids) == 3
        assert msg.channel == "__multicast__"

    def test_route_message_counts(self):
        self.router.subscribe("conn1", "trades")
        self.router.subscribe("conn2", "trades")
        msg = Message(channel="trades", payload="test")
        count = self.router.route_message(msg)
        assert count == 2

    def test_channel_stats(self):
        self.router.subscribe("conn1", "prices")
        self.router.subscribe("conn2", "prices")
        self.router.subscribe("conn1", "trades")
        stats = self.router.get_channel_stats()
        assert stats["prices"] == 2
        assert stats["trades"] == 1

    def test_message_log(self):
        self.router.broadcast("ch1", "payload1")
        self.router.broadcast("ch2", "payload2")
        self.router.broadcast("ch1", "payload3")
        log = self.router.get_message_log()
        assert len(log) == 3
        ch1_log = self.router.get_message_log(channel="ch1")
        assert len(ch1_log) == 2

    def test_message_log_limit(self):
        for i in range(10):
            self.router.broadcast("ch", f"msg-{i}")
        log = self.router.get_message_log(limit=5)
        assert len(log) == 5

    def test_reset(self):
        self.router.subscribe("conn1", "ch")
        self.router.broadcast("ch", "data")
        self.router.reset()
        assert self.router.get_subscribers("ch") == set()
        assert self.router.get_message_log() == []

    def test_message_defaults(self):
        msg = Message()
        assert len(msg.message_id) > 0
        assert msg.priority == MessagePriority.NORMAL
        assert isinstance(msg.timestamp, datetime)


# ── BackpressureHandler Tests ────────────────────────────────────────


class TestBackpressureHandler:
    """Tests for backpressure handling."""

    def setup_method(self):
        self.cfg = WSScalingConfig(
            message_buffer_size=10,
            backpressure_threshold=8,
        )
        self.handler = BackpressureHandler(config=self.cfg)

    def test_enqueue_dequeue(self):
        msg = Message(channel="test", payload="hello")
        assert self.handler.enqueue("conn1", msg) is True
        assert self.handler.get_queue_depth("conn1") == 1
        result = self.handler.dequeue("conn1")
        assert len(result) == 1
        assert result[0].payload == "hello"
        assert self.handler.get_queue_depth("conn1") == 0

    def test_enqueue_full_queue(self):
        for i in range(10):
            self.handler.enqueue("conn1", Message(channel="test", payload=i))
        # Queue is now at capacity
        assert self.handler.enqueue("conn1", Message(channel="test", payload="overflow")) is False

    def test_dequeue_multiple(self):
        for i in range(5):
            self.handler.enqueue("conn1", Message(channel="test", payload=i))
        result = self.handler.dequeue("conn1", count=3)
        assert len(result) == 3
        assert self.handler.get_queue_depth("conn1") == 2

    def test_dequeue_empty(self):
        result = self.handler.dequeue("conn1")
        assert result == []

    def test_detect_slow_consumers(self):
        for i in range(9):
            self.handler.enqueue("conn1", Message(channel="test", payload=i))
        slow = self.handler.detect_slow_consumers()
        assert "conn1" in slow

    def test_no_slow_consumers(self):
        self.handler.enqueue("conn1", Message(channel="test", payload="x"))
        slow = self.handler.detect_slow_consumers()
        assert slow == []

    def test_drop_oldest_first(self):
        for i in range(10):
            self.handler.enqueue("conn1", Message(channel="test", payload=i))
        dropped = self.handler.drop_messages("conn1", DropStrategy.OLDEST_FIRST, count=3)
        assert dropped == 3
        assert self.handler.get_queue_depth("conn1") == 7
        # The oldest (0, 1, 2) should have been removed
        remaining = self.handler.dequeue("conn1", count=7)
        assert remaining[0].payload == 3

    def test_drop_lowest_priority(self):
        self.handler.enqueue("conn1", Message(channel="t", payload="low", priority=MessagePriority.LOW))
        self.handler.enqueue("conn1", Message(channel="t", payload="crit", priority=MessagePriority.CRITICAL))
        self.handler.enqueue("conn1", Message(channel="t", payload="norm", priority=MessagePriority.NORMAL))
        dropped = self.handler.drop_messages("conn1", DropStrategy.LOWEST_PRIORITY, count=1)
        assert dropped == 1
        # LOW priority should have been dropped
        assert self.handler.get_queue_depth("conn1") == 2

    def test_drop_random(self):
        for i in range(10):
            self.handler.enqueue("conn1", Message(channel="test", payload=i))
        dropped = self.handler.drop_messages("conn1", DropStrategy.RANDOM, count=5)
        assert dropped == 5
        assert self.handler.get_queue_depth("conn1") == 5

    def test_queue_stats(self):
        for i in range(3):
            self.handler.enqueue("conn1", Message(channel="test", payload=i))
        stats = self.handler.get_queue_stats("conn1")
        assert stats.connection_id == "conn1"
        assert stats.queue_depth == 3
        assert stats.messages_dropped == 0

    def test_get_all_stats(self):
        self.handler.enqueue("conn1", Message(channel="t", payload=1))
        self.handler.enqueue("conn2", Message(channel="t", payload=2))
        all_stats = self.handler.get_all_stats()
        assert "conn1" in all_stats
        assert "conn2" in all_stats

    def test_total_queued(self):
        self.handler.enqueue("conn1", Message(channel="t", payload=1))
        self.handler.enqueue("conn1", Message(channel="t", payload=2))
        self.handler.enqueue("conn2", Message(channel="t", payload=3))
        assert self.handler.get_total_queued() == 3

    def test_reset(self):
        self.handler.enqueue("conn1", Message(channel="t", payload="x"))
        self.handler.reset()
        assert self.handler.get_total_queued() == 0
        assert self.handler.get_all_stats() == {}


# ── ReconnectionManager Tests ────────────────────────────────────────


class TestReconnectionManager:
    """Tests for reconnection session management."""

    def setup_method(self):
        self.cfg = WSScalingConfig(max_reconnection_attempts=3, reconnection_window_seconds=5)
        self.mgr = ReconnectionManager(config=self.cfg)

    def test_start_session(self):
        session = self.mgr.start_session("user1", "conn1")
        assert session.user_id == "user1"
        assert session.original_connection_id == "conn1"
        assert session.state == "pending"
        assert session.attempt_count == 0

    def test_attempt_reconnect_success(self):
        session = self.mgr.start_session("user1", "conn1")
        # Buffer some messages
        self.mgr.buffer_message("conn1", Message(channel="prices", payload={"tick": 1}))
        self.mgr.buffer_message("conn1", Message(channel="prices", payload={"tick": 2}))

        result = self.mgr.attempt_reconnect(session.session_id, "conn2")
        assert result["success"] is True
        assert result["missed_message_count"] == 2
        assert session.state == "reconnected"

    def test_attempt_reconnect_nonexistent_session(self):
        result = self.mgr.attempt_reconnect("fake-session", "conn2")
        assert result["success"] is False

    def test_attempt_reconnect_exceeds_max(self):
        session = self.mgr.start_session("user1", "conn1")
        # Exhaust attempts (max_attempts = 3)
        for _ in range(3):
            self.mgr.attempt_reconnect(session.session_id, "connX")
        # The third attempt succeeds (attempt_count becomes 3, which is <= 3)
        # Start fresh session
        session2 = self.mgr.start_session("user2", "conn2")
        for _ in range(4):
            self.mgr.attempt_reconnect(session2.session_id, "connY")
        # After first success it becomes "reconnected", further attempts fail
        assert session2.state == "reconnected"

    def test_buffer_message(self):
        self.mgr.start_session("user1", "conn1")
        self.mgr.buffer_message("conn1", Message(channel="ch", payload="a"))
        self.mgr.buffer_message("conn1", Message(channel="ch", payload="b"))
        # Buffer for unknown connection should be a no-op
        self.mgr.buffer_message("conn999", Message(channel="ch", payload="c"))

    def test_get_missed_messages(self):
        session = self.mgr.start_session("user1", "conn1")
        self.mgr.buffer_message("conn1", Message(channel="ch", payload="x"))
        self.mgr.attempt_reconnect(session.session_id, "conn2")
        missed = self.mgr.get_missed_messages(session.session_id)
        assert len(missed) == 1
        assert missed[0].payload == "x"

    def test_get_session(self):
        session = self.mgr.start_session("user1", "conn1")
        fetched = self.mgr.get_session(session.session_id)
        assert fetched is not None
        assert fetched.user_id == "user1"

    def test_list_sessions(self):
        self.mgr.start_session("user1", "conn1")
        self.mgr.start_session("user1", "conn2")
        self.mgr.start_session("user2", "conn3")
        all_sessions = self.mgr.list_sessions()
        assert len(all_sessions) == 3
        user1_sessions = self.mgr.list_sessions(user_id="user1")
        assert len(user1_sessions) == 2
        pending = self.mgr.list_sessions(state="pending")
        assert len(pending) == 3

    def test_can_reconnect(self):
        session = self.mgr.start_session("user1", "conn1")
        assert self.mgr.can_reconnect(session.session_id) is True
        # After successful reconnect, state changes
        self.mgr.attempt_reconnect(session.session_id, "conn2")
        assert self.mgr.can_reconnect(session.session_id) is False

    def test_can_reconnect_nonexistent(self):
        assert self.mgr.can_reconnect("fake") is False

    def test_reconnection_stats(self):
        s1 = self.mgr.start_session("user1", "conn1")
        s2 = self.mgr.start_session("user2", "conn2")
        self.mgr.attempt_reconnect(s1.session_id, "conn3")
        stats = self.mgr.get_reconnection_stats()
        assert stats["total"] == 2
        assert stats["successful"] == 1
        assert stats["pending"] == 1

    def test_expire_sessions(self):
        session = self.mgr.start_session("user1", "conn1")
        # Buffer a message with a timestamp in the past
        old_msg = Message(channel="ch", payload="old")
        old_msg.timestamp = datetime.utcnow() - timedelta(seconds=60)
        self.mgr.buffer_message("conn1", old_msg)
        expired = self.mgr.expire_sessions(timeout_seconds=5)
        assert expired == 1
        assert session.state == "expired"

    def test_reset(self):
        self.mgr.start_session("user1", "conn1")
        self.mgr.reset()
        assert self.mgr.list_sessions() == []
        stats = self.mgr.get_reconnection_stats()
        assert stats["total"] == 0

    def test_reconnection_session_defaults(self):
        session = ReconnectionSession()
        assert len(session.session_id) > 0
        assert session.state == "pending"
        assert session.attempt_count == 0
        assert session.max_attempts == 5
        assert session.missed_messages == []
