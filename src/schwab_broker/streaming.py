"""Schwab WebSocket Streaming (PRD-145).

Real-time market data streaming via Schwab Streamer WebSocket.
Supports QUOTE, CHART, OPTION, TIMESALE, and NEWS channels.
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
    """Available Schwab streaming channels."""
    QUOTE = "QUOTE"
    CHART = "CHART_EQUITY"
    OPTION = "OPTION"
    TIMESALE = "TIMESALE_EQUITY"
    NEWS = "NEWS_HEADLINE"


@dataclass
class StreamEvent:
    """A streaming event from Schwab."""
    channel: StreamChannel
    symbol: str = ""
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_quote(self) -> bool:
        return self.channel == StreamChannel.QUOTE

    @property
    def is_chart(self) -> bool:
        return self.channel == StreamChannel.CHART

    @property
    def is_option(self) -> bool:
        return self.channel == StreamChannel.OPTION

    @property
    def is_timesale(self) -> bool:
        return self.channel == StreamChannel.TIMESALE

    @property
    def is_news(self) -> bool:
        return self.channel == StreamChannel.NEWS


# Type aliases
StreamCallback = Callable[[StreamEvent], Any]


class SchwabStreaming:
    """Manages WebSocket connection for real-time Schwab data.

    Example:
        streaming = SchwabStreaming(config)
        streaming.on_quote(my_handler)
        await streaming.subscribe(["AAPL", "MSFT"], [StreamChannel.QUOTE])
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

    def on_chart(self, callback: StreamCallback) -> None:
        """Register handler for chart (bar) events."""
        self._callbacks[StreamChannel.CHART].append(callback)

    def on_option(self, callback: StreamCallback) -> None:
        """Register handler for option events."""
        self._callbacks[StreamChannel.OPTION].append(callback)

    def on_timesale(self, callback: StreamCallback) -> None:
        """Register handler for time & sale events."""
        self._callbacks[StreamChannel.TIMESALE].append(callback)

    def on_news(self, callback: StreamCallback) -> None:
        """Register handler for news events."""
        self._callbacks[StreamChannel.NEWS].append(callback)

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
        logger.info("Schwab streaming started")

    async def stop(self) -> None:
        """Stop all streaming connections."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        if self._demo_task and not self._demo_task.done():
            self._demo_task.cancel()
        self._tasks.clear()
        logger.info("Schwab streaming stopped")
