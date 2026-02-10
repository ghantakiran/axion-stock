"""PRD-172: Bot WebSocket endpoint — real-time event streaming.

Provides a single WebSocket endpoint at /ws/bot that streams
bot events (signals, orders, alerts) to connected clients.
Uses WebSocketManager from src/api/websocket.py.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from src.api.websocket import WebSocketManager

logger = logging.getLogger(__name__)

# Shared WebSocket manager instance
_ws_manager = WebSocketManager()


def get_ws_manager() -> WebSocketManager:
    """Return the global WebSocketManager instance."""
    return _ws_manager


# Bot-specific channels
BOT_CHANNELS = {"signals", "orders", "alerts", "lifecycle", "metrics"}


def handle_bot_connect(user_id: str = "anonymous") -> tuple[str, bool, str]:
    """Register a new bot WebSocket connection.

    Args:
        user_id: User identifier.

    Returns:
        Tuple of (connection_id, success, message).
    """
    conn_id = uuid.uuid4().hex[:16]
    mgr = get_ws_manager()
    success, msg = mgr.connect(conn_id, user_id)
    if success:
        # Auto-subscribe to all bot channels
        for ch in BOT_CHANNELS:
            mgr.subscribe(conn_id, ch)
    return conn_id, success, msg


def handle_bot_disconnect(connection_id: str) -> None:
    """Disconnect a bot WebSocket connection."""
    mgr = get_ws_manager()
    mgr.disconnect(connection_id)


def handle_bot_message(connection_id: str, raw_message: str) -> list[dict]:
    """Handle incoming WebSocket message from a client.

    Supports:
    - {"action": "subscribe", "channel": "signals"}
    - {"action": "unsubscribe", "channel": "orders"}
    - {"action": "heartbeat"}

    Returns:
        List of response messages to send back.
    """
    mgr = get_ws_manager()
    try:
        msg = json.loads(raw_message)
    except json.JSONDecodeError:
        return [{"error": "Invalid JSON"}]

    action = msg.get("action")
    responses = []

    if action == "subscribe":
        ch = msg.get("channel", "")
        if ch in BOT_CHANNELS:
            ok, m = mgr.subscribe(connection_id, ch)
            responses.append({"action": "subscribed", "channel": ch, "ok": ok, "message": m})
        else:
            responses.append({"error": f"Unknown channel: {ch}", "available": sorted(BOT_CHANNELS)})

    elif action == "unsubscribe":
        ch = msg.get("channel", "")
        ok, m = mgr.unsubscribe(connection_id, ch)
        responses.append({"action": "unsubscribed", "channel": ch, "ok": ok})

    elif action == "heartbeat":
        mgr.heartbeat(connection_id)
        responses.append({"action": "heartbeat_ack", "timestamp": datetime.now(timezone.utc).isoformat()})

    else:
        responses.append({"error": f"Unknown action: {action}"})

    return responses


def broadcast_bot_event(event_type: str, data: dict) -> list[dict]:
    """Broadcast a bot event to all WebSocket subscribers.

    Maps event types to channels:
    - trade_executed, position_closed → orders
    - signal_received, signal_rejected → signals
    - kill_switch, emergency_close → alerts
    - bot_started, bot_stopped → lifecycle
    - performance_snapshot → metrics

    Args:
        event_type: Type of event.
        data: Event payload.

    Returns:
        List of {connection_id, message} dicts to send.
    """
    channel_map = {
        "trade_executed": "orders",
        "position_closed": "orders",
        "order_submitted": "orders",
        "signal_received": "signals",
        "signal_rejected": "signals",
        "signal_fused": "signals",
        "kill_switch": "alerts",
        "emergency_close": "alerts",
        "daily_loss_warning": "alerts",
        "error": "alerts",
        "bot_started": "lifecycle",
        "bot_stopped": "lifecycle",
        "bot_paused": "lifecycle",
        "bot_resumed": "lifecycle",
        "performance_snapshot": "metrics",
        "weight_update": "metrics",
    }

    channel = channel_map.get(event_type, "lifecycle")
    mgr = get_ws_manager()

    payload = {
        "event": event_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return mgr.broadcast(channel, payload)
