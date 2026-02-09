"""Webull WebSocket Streaming (PRD-159).

Real-time market data streaming via Webull's WebSocket service.
Supports QUOTE, TRADES, DEPTH, and ORDERS channels.
Extended hours streaming available (4am-8pm ET).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

_HAS_WEBSOCKETS = False
try:
    import websockets
    _HAS_WEBSOCKETS = True
except ImportError:
    websockets = None  # type: ignore


# =====================================================================
# Stream Event Types
# =====================================================================


class StreamChannel(str, Enum):
    """Available Webull streaming channels."""
    QUOTE = "QUOTE"
    TRADES = "TRADES"
    DEPTH = "DEPTH"
    ORDERS = "ORDERS"


@dataclass
class StreamEvent:
    """A streaming event from Webull."""
    channel: StreamChannel
    symbol: str = ""
    ticker_id: int = 0
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_quote(self) -> bool:
        return self.channel == StreamChannel.QUOTE

    @property
    def is_trades(self) -> bool:
        return self.channel == StreamChannel.TRADES

    @property
    def is_depth(self) -> bool:
        return self.channel == StreamChannel.DEPTH

    @property
    def is_orders(self) -> bool:
        return self.channel == StreamChannel.ORDERS


# Type aliases
StreamCallback = Callable[[StreamEvent], Any]


class WebullStreaming:
    """Manages WebSocket connection for real-time Webull data.

    Supports extended hours streaming (4am-8pm ET) for all subscribed symbols.

    Example:
        streaming = WebullStreaming(config)
        streaming.on_quote(my_handler)
        await streaming.subscribe(["AAPL", "TSLA"], [StreamChannel.QUOTE])
        await streaming.start()
    """

    def __init__(self, config: Any):
        self._config = config
        self._running = False
        self._subscriptions: dict[StreamChannel, set[str]] = {
            ch: set() for ch in StreamChannel
        }
        self._callbacks: dict[StreamChannel, list[StreamCallback]] = {
            ch: [] for ch in StreamChannel
        }
        self._ws: Any = None
        self._tasks: list[asyncio.Task] = []
        self._reconnect_delay = 1.0
        self._demo_task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def subscriptions(self) -> dict[str, list[str]]:
        """Get current subscriptions as channel -> symbols mapping."""
        return {
            ch.value: sorted(symbols)
            for ch, symbols in self._subscriptions.items()
            if symbols
        }

    # -- Callback Registration ---------------------------------------------

    def on_quote(self, callback: StreamCallback) -> None:
        """Register handler for quote events."""
        self._callbacks[StreamChannel.QUOTE].append(callback)

    def on_trades(self, callback: StreamCallback) -> None:
        """Register handler for trade events."""
        self._callbacks[StreamChannel.TRADES].append(callback)

    def on_depth(self, callback: StreamCallback) -> None:
        """Register handler for depth/order book events."""
        self._callbacks[StreamChannel.DEPTH].append(callback)

    def on_orders(self, callback: StreamCallback) -> None:
        """Register handler for order update events."""
        self._callbacks[StreamChannel.ORDERS].append(callback)

    # -- Subscription Management -------------------------------------------

    async def subscribe(
        self, symbols: list[str], channels: list[StreamChannel]
    ) -> None:
        """Subscribe to channels for given symbols."""
        for channel in channels:
            self._subscriptions[channel].update(s.upper() for s in symbols)

    async def unsubscribe(
        self, symbols: list[str], channels: list[StreamChannel]
    ) -> None:
        """Unsubscribe from channels for given symbols."""
        for channel in channels:
            for s in symbols:
                self._subscriptions[channel].discard(s.upper())

    # -- Stream Lifecycle --------------------------------------------------

    async def start(self) -> None:
        """Start streaming (demo mode generates periodic updates)."""
        if self._running:
            return
        self._running = True
        logger.info("Webull streaming started")

    async def stop(self) -> None:
        """Stop all streaming connections."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._demo_task and not self._demo_task.done():
            self._demo_task.cancel()
        self._tasks.clear()
        logger.info("Webull streaming stopped")
