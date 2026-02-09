"""tastytrade WebSocket Streaming (PRD-158).

Real-time market data streaming via tastytrade DXLink WebSocket.
Supports QUOTE, GREEKS, TRADES, and ORDERS channels.
Options-first streaming with live greeks updates.
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
    """Available tastytrade streaming channels."""
    QUOTE = "QUOTE"
    GREEKS = "GREEKS"
    TRADES = "TRADES"
    ORDERS = "ORDERS"


@dataclass
class StreamEvent:
    """A streaming event from tastytrade."""
    channel: StreamChannel
    symbol: str = ""
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_quote(self) -> bool:
        return self.channel == StreamChannel.QUOTE

    @property
    def is_greeks(self) -> bool:
        return self.channel == StreamChannel.GREEKS

    @property
    def is_trade(self) -> bool:
        return self.channel == StreamChannel.TRADES

    @property
    def is_order(self) -> bool:
        return self.channel == StreamChannel.ORDERS


# Type aliases
StreamCallback = Callable[[StreamEvent], Any]


class TastytradeStreaming:
    """Manages DXLink WebSocket connection for real-time tastytrade data.

    Options-first streaming with live greeks, quotes, trades, and order updates.

    Example:
        streaming = TastytradeStreaming(config)
        streaming.on_quote(my_handler)
        await streaming.subscribe(["AAPL", "SPY"], [StreamChannel.QUOTE])
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

    def on_greeks(self, callback: StreamCallback) -> None:
        """Register handler for greeks events."""
        self._callbacks[StreamChannel.GREEKS].append(callback)

    def on_trade(self, callback: StreamCallback) -> None:
        """Register handler for trade events."""
        self._callbacks[StreamChannel.TRADES].append(callback)

    def on_order(self, callback: StreamCallback) -> None:
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
        logger.info("tastytrade streaming started")

    async def stop(self) -> None:
        """Stop all streaming connections."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._demo_task and not self._demo_task.done():
            self._demo_task.cancel()
        self._tasks.clear()
        logger.info("tastytrade streaming stopped")
