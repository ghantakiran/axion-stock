"""PRD-172: Bot API & WebSocket Control — tests.

Tests REST endpoints, WebSocket handler, and broadcast logic.
~40 tests across 4 classes.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch

from src.api.routes.bot import (
    BotStatusResponse,
    ConfigUpdate,
    KillRequest,
    MessageResponse,
    StartRequest,
    get_controller,
    router,
)
from src.api.routes.bot_ws import (
    BOT_CHANNELS,
    broadcast_bot_event,
    handle_bot_connect,
    handle_bot_disconnect,
    handle_bot_message,
    get_ws_manager,
)
from src.bot_dashboard.state import BotController, DashboardConfig


# ═════════════════════════════════════════════════════════════════════
# Test BotController REST API Logic
# ═════════════════════════════════════════════════════════════════════


class TestBotControllerAPI:
    """Test BotController state management used by REST endpoints."""

    def test_controller_starts_in_paper_mode(self):
        ctrl = BotController()
        assert ctrl.state.status == "paper"

    def test_start_paper_mode(self):
        ctrl = BotController(DashboardConfig(paper_mode=False))
        ctrl.start(paper_mode=True)
        assert ctrl.state.status == "paper"
        assert ctrl.state.active_broker == "paper"

    def test_start_live_mode(self):
        ctrl = BotController()
        ctrl.start(paper_mode=False)
        assert ctrl.state.status == "live"
        assert ctrl.state.active_broker == "alpaca"

    def test_pause(self):
        ctrl = BotController()
        ctrl.start(paper_mode=True)
        ctrl.pause()
        assert ctrl.state.status == "paused"

    def test_resume_from_paused(self):
        ctrl = BotController()
        ctrl.start(paper_mode=True)
        ctrl.pause()
        ctrl.resume()
        assert ctrl.state.status == "paper"

    def test_kill_switch(self):
        ctrl = BotController()
        ctrl.kill(reason="test kill")
        assert ctrl.state.status == "killed"
        assert ctrl.state.kill_switch_active is True

    def test_reset_kill_switch(self):
        ctrl = BotController()
        ctrl.kill(reason="test")
        ctrl.reset_kill_switch()
        assert ctrl.state.kill_switch_active is False
        assert ctrl.state.status == "paused"

    def test_update_config(self):
        ctrl = BotController()
        ctrl.update_config({"refresh_interval_seconds": 10})
        assert ctrl.config.refresh_interval_seconds == 10

    def test_state_to_dict(self):
        ctrl = BotController()
        d = ctrl.state.to_dict()
        assert "status" in d
        assert "daily_pnl" in d
        assert "kill_switch_active" in d

    def test_get_events(self):
        ctrl = BotController()
        ctrl.start(paper_mode=True)
        ctrl.pause()
        events = ctrl.get_events(limit=10)
        assert len(events) >= 2


# ═════════════════════════════════════════════════════════════════════
# Test Request/Response Models
# ═════════════════════════════════════════════════════════════════════


class TestRequestResponseModels:
    """Test Pydantic request/response models."""

    def test_start_request_defaults(self):
        req = StartRequest()
        assert req.paper_mode is True

    def test_start_request_live(self):
        req = StartRequest(paper_mode=False)
        assert req.paper_mode is False

    def test_kill_request_default(self):
        req = KillRequest()
        assert "API kill switch" in req.reason

    def test_kill_request_custom(self):
        req = KillRequest(reason="Emergency")
        assert req.reason == "Emergency"

    def test_config_update_partial(self):
        update = ConfigUpdate(refresh_interval_seconds=15)
        dumped = update.model_dump()
        assert dumped["refresh_interval_seconds"] == 15
        assert dumped["paper_mode"] is None

    def test_message_response(self):
        resp = MessageResponse(message="ok")
        assert resp.message == "ok"

    def test_bot_status_response(self):
        resp = BotStatusResponse(
            status="paper",
            instrument_mode="both",
            uptime_seconds=100,
            account_equity=100000.0,
            daily_pnl=50.0,
            daily_pnl_pct=0.0005,
            win_rate=0.6,
            total_trades_today=5,
            open_positions=2,
            kill_switch_active=False,
            data_feed_status="connected",
        )
        assert resp.status == "paper"
        assert resp.open_positions == 2


# ═════════════════════════════════════════════════════════════════════
# Test WebSocket Handler
# ═════════════════════════════════════════════════════════════════════


class TestWebSocketHandler:
    """Test WebSocket connection, message handling, and broadcasting."""

    def test_connect_returns_connection_id(self):
        conn_id, success, msg = handle_bot_connect("user1")
        assert success is True
        assert len(conn_id) == 16
        # Cleanup
        handle_bot_disconnect(conn_id)

    def test_connect_auto_subscribes_to_bot_channels(self):
        conn_id, success, _ = handle_bot_connect("user2")
        mgr = get_ws_manager()
        info = mgr.get_connection_info(conn_id)
        assert info is not None
        for ch in BOT_CHANNELS:
            assert ch in info["subscriptions"]
        handle_bot_disconnect(conn_id)

    def test_disconnect(self):
        conn_id, _, _ = handle_bot_connect("user3")
        handle_bot_disconnect(conn_id)
        mgr = get_ws_manager()
        assert mgr.get_connection_info(conn_id) is None

    def test_handle_subscribe_message(self):
        conn_id, _, _ = handle_bot_connect("user4")
        responses = handle_bot_message(conn_id, json.dumps({"action": "subscribe", "channel": "signals"}))
        assert responses[0]["action"] == "subscribed"
        assert responses[0]["ok"] is True
        handle_bot_disconnect(conn_id)

    def test_handle_unsubscribe_message(self):
        conn_id, _, _ = handle_bot_connect("user5")
        responses = handle_bot_message(conn_id, json.dumps({"action": "unsubscribe", "channel": "signals"}))
        assert responses[0]["action"] == "unsubscribed"
        handle_bot_disconnect(conn_id)

    def test_handle_heartbeat(self):
        conn_id, _, _ = handle_bot_connect("user6")
        responses = handle_bot_message(conn_id, json.dumps({"action": "heartbeat"}))
        assert responses[0]["action"] == "heartbeat_ack"
        assert "timestamp" in responses[0]
        handle_bot_disconnect(conn_id)

    def test_handle_invalid_json(self):
        conn_id, _, _ = handle_bot_connect("user7")
        responses = handle_bot_message(conn_id, "not json")
        assert "error" in responses[0]
        handle_bot_disconnect(conn_id)

    def test_handle_unknown_action(self):
        conn_id, _, _ = handle_bot_connect("user8")
        responses = handle_bot_message(conn_id, json.dumps({"action": "fly"}))
        assert "error" in responses[0]
        handle_bot_disconnect(conn_id)

    def test_handle_unknown_channel(self):
        conn_id, _, _ = handle_bot_connect("user9")
        responses = handle_bot_message(conn_id, json.dumps({"action": "subscribe", "channel": "unknown_ch"}))
        assert "error" in responses[0]
        handle_bot_disconnect(conn_id)


# ═════════════════════════════════════════════════════════════════════
# Test Broadcast
# ═════════════════════════════════════════════════════════════════════


class TestBroadcast:
    """Test event broadcasting to WebSocket subscribers."""

    def test_broadcast_trade_executed(self):
        conn_id, _, _ = handle_bot_connect("bcast_user1")
        messages = broadcast_bot_event("trade_executed", {"ticker": "AAPL", "pnl": 100})
        assert len(messages) >= 1
        for m in messages:
            assert "connection_id" in m
            payload = json.loads(m["message"])
            assert payload["channel"] == "orders"
        handle_bot_disconnect(conn_id)

    def test_broadcast_kill_switch(self):
        conn_id, _, _ = handle_bot_connect("bcast_user2")
        messages = broadcast_bot_event("kill_switch", {"reason": "daily loss"})
        found_alert = any(
            json.loads(m["message"])["channel"] == "alerts"
            for m in messages
        )
        assert found_alert
        handle_bot_disconnect(conn_id)

    def test_broadcast_signal_received(self):
        conn_id, _, _ = handle_bot_connect("bcast_user3")
        messages = broadcast_bot_event("signal_received", {"ticker": "NVDA"})
        found_signal = any(
            json.loads(m["message"])["channel"] == "signals"
            for m in messages
        )
        assert found_signal
        handle_bot_disconnect(conn_id)

    def test_broadcast_lifecycle_event(self):
        conn_id, _, _ = handle_bot_connect("bcast_user4")
        messages = broadcast_bot_event("bot_started", {"mode": "paper"})
        found_lifecycle = any(
            json.loads(m["message"])["channel"] == "lifecycle"
            for m in messages
        )
        assert found_lifecycle
        handle_bot_disconnect(conn_id)

    def test_broadcast_performance_snapshot(self):
        conn_id, _, _ = handle_bot_connect("bcast_user5")
        messages = broadcast_bot_event("performance_snapshot", {"sharpe": 1.5})
        found_metrics = any(
            json.loads(m["message"])["channel"] == "metrics"
            for m in messages
        )
        assert found_metrics
        handle_bot_disconnect(conn_id)

    def test_broadcast_unknown_event_defaults_to_lifecycle(self):
        conn_id, _, _ = handle_bot_connect("bcast_user6")
        messages = broadcast_bot_event("some_custom_event", {"info": "test"})
        if messages:
            payload = json.loads(messages[0]["message"])
            assert payload["channel"] == "lifecycle"
        handle_bot_disconnect(conn_id)

    def test_bot_channels_constant(self):
        assert "signals" in BOT_CHANNELS
        assert "orders" in BOT_CHANNELS
        assert "alerts" in BOT_CHANNELS
        assert "lifecycle" in BOT_CHANNELS
        assert "metrics" in BOT_CHANNELS
