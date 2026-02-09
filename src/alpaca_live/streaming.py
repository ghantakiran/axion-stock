"""Alpaca WebSocket Streaming (PRD-139).

Real-time market data and trade update streaming via WebSocket.
Supports quote, trade, bar, and order update channels.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional
import asyncio
import json
import logging

from src.alpaca_live.client import AlpacaConfig, AlpacaBar, AlpacaQuote

logger = logging.getLogger(__name__)

_HAS_WEBSOCKETS = False
try:
    import websockets
    _HAS_WEBSOCKETS = True
except ImportError:
    websockets = None  # type: ignore


# ═══════════════════════════════════════════════════════════════════════
# Stream Event Types
# ═══════════════════════════════════════════════════════════════════════


class StreamChannel(str, Enum):
    """Available streaming channels."""
    TRADES = "trades"
    QUOTES = "quotes"
    BARS = "bars"
    DAILY_BARS = "dailyBars"
    UPDATED_BARS = "updatedBars"
    ORDER_UPDATES = "trade_updates"


@dataclass
class StreamEvent:
    """A streaming event from Alpaca."""
    channel: StreamChannel
    symbol: str = ""
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_trade(self) -> bool:
        return self.channel == StreamChannel.TRADES

    @property
    def is_quote(self) -> bool:
        return self.channel == StreamChannel.QUOTES

    @property
    def is_bar(self) -> bool:
        return self.channel in (
            StreamChannel.BARS, StreamChannel.DAILY_BARS, StreamChannel.UPDATED_BARS
        )

    @property
    def is_order_update(self) -> bool:
        return self.channel == StreamChannel.ORDER_UPDATES

    def as_bar(self) -> AlpacaBar:
        """Convert to AlpacaBar (for bar events)."""
        return AlpacaBar.from_api(self.data)

    def as_quote(self) -> AlpacaQuote:
        """Convert to AlpacaQuote (for quote events)."""
        return AlpacaQuote.from_api(self.data, symbol=self.symbol)


@dataclass
class OrderUpdate:
    """Order status update from streaming."""
    event: str = ""  # new, fill, partial_fill, canceled, expired, etc.
    order_id: str = ""
    symbol: str = ""
    side: str = ""
    qty: float = 0.0
    filled_qty: float = 0.0
    filled_avg_price: float = 0.0
    order_type: str = ""
    status: str = ""
    timestamp: str = ""

    @classmethod
    def from_stream(cls, data: dict) -> "OrderUpdate":
        order = data.get("order", {})
        return cls(
            event=data.get("event", ""),
            order_id=order.get("id", ""),
            symbol=order.get("symbol", ""),
            side=order.get("side", ""),
            qty=float(order.get("qty", 0)),
            filled_qty=float(order.get("filled_qty", 0) or 0),
            filled_avg_price=float(order.get("filled_avg_price", 0) or 0),
            order_type=order.get("type", ""),
            status=order.get("status", ""),
            timestamp=data.get("timestamp", ""),
        )


# ═══════════════════════════════════════════════════════════════════════
# Streaming Manager
# ═══════════════════════════════════════════════════════════════════════

# Type alias for stream callbacks
StreamCallback = Callable[[StreamEvent], Any]
OrderCallback = Callable[[OrderUpdate], Any]


class AlpacaStreaming:
    """Manages WebSocket connections for real-time Alpaca data.

    Two separate streams:
    - Market data stream (quotes, trades, bars)
    - Trading stream (order updates)

    Example:
        streaming = AlpacaStreaming(config)
        streaming.on_quote(my_quote_handler)
        streaming.on_order_update(my_order_handler)
        await streaming.subscribe(["AAPL", "MSFT"], [StreamChannel.QUOTES])
        await streaming.start()
    """

    def __init__(self, config: AlpacaConfig):
        self._config = config
        self._running = False
        self._subscriptions: dict[StreamChannel, set[str]] = {
            ch: set() for ch in StreamChannel
        }
        self._callbacks: dict[StreamChannel, list[StreamCallback]] = {
            ch: [] for ch in StreamChannel
        }
        self._order_callbacks: list[OrderCallback] = []
        self._data_ws: Any = None
        self._trading_ws: Any = None
        self._tasks: list[asyncio.Task] = []
        self._reconnect_delay = 1.0
        self._max_reconnect_delay = 60.0

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

    # ── Callback Registration ─────────────────────────────────────────

    def on_trade(self, callback: StreamCallback) -> None:
        """Register handler for trade events."""
        self._callbacks[StreamChannel.TRADES].append(callback)

    def on_quote(self, callback: StreamCallback) -> None:
        """Register handler for quote events."""
        self._callbacks[StreamChannel.QUOTES].append(callback)

    def on_bar(self, callback: StreamCallback) -> None:
        """Register handler for bar events."""
        self._callbacks[StreamChannel.BARS].append(callback)

    def on_daily_bar(self, callback: StreamCallback) -> None:
        """Register handler for daily bar events."""
        self._callbacks[StreamChannel.DAILY_BARS].append(callback)

    def on_order_update(self, callback: OrderCallback) -> None:
        """Register handler for order update events."""
        self._order_callbacks.append(callback)

    # ── Subscription Management ───────────────────────────────────────

    async def subscribe(
        self, symbols: list[str], channels: list[StreamChannel]
    ) -> None:
        """Subscribe to channels for given symbols."""
        for channel in channels:
            self._subscriptions[channel].update(s.upper() for s in symbols)

        if self._running and self._data_ws:
            await self._send_subscription_message()

    async def unsubscribe(
        self, symbols: list[str], channels: list[StreamChannel]
    ) -> None:
        """Unsubscribe from channels for given symbols."""
        for channel in channels:
            for s in symbols:
                self._subscriptions[channel].discard(s.upper())

    # ── Stream Lifecycle ──────────────────────────────────────────────

    async def start(self) -> None:
        """Start streaming connections."""
        if self._running:
            return

        if not _HAS_WEBSOCKETS:
            logger.warning("websockets not installed — streaming unavailable")
            self._running = True  # Mark as running for testing
            return

        self._running = True

        # Start market data stream
        data_task = asyncio.create_task(self._run_data_stream())
        self._tasks.append(data_task)

        # Start trading stream (order updates)
        trading_task = asyncio.create_task(self._run_trading_stream())
        self._tasks.append(trading_task)

        logger.info("Alpaca streaming started")

    async def stop(self) -> None:
        """Stop all streaming connections."""
        self._running = False

        for task in self._tasks:
            task.cancel()

        if self._data_ws:
            try:
                await self._data_ws.close()
            except Exception:
                pass

        if self._trading_ws:
            try:
                await self._trading_ws.close()
            except Exception:
                pass

        self._tasks.clear()
        logger.info("Alpaca streaming stopped")

    # ── Internal Stream Loops ─────────────────────────────────────────

    async def _run_data_stream(self) -> None:
        """Run the market data WebSocket stream with reconnection."""
        delay = self._reconnect_delay

        while self._running:
            try:
                async with websockets.connect(self._config.stream_url) as ws:
                    self._data_ws = ws
                    delay = self._reconnect_delay

                    # Authenticate
                    auth_msg = {
                        "action": "auth",
                        "key": self._config.api_key,
                        "secret": self._config.api_secret,
                    }
                    await ws.send(json.dumps(auth_msg))
                    auth_resp = await ws.recv()
                    logger.info(f"Data stream auth: {auth_resp}")

                    # Subscribe
                    await self._send_subscription_message()

                    # Listen
                    async for message in ws:
                        if not self._running:
                            break
                        await self._handle_data_message(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    logger.warning(f"Data stream error: {e}, reconnecting in {delay}s")
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, self._max_reconnect_delay)

    async def _run_trading_stream(self) -> None:
        """Run the trading WebSocket stream for order updates."""
        delay = self._reconnect_delay

        while self._running:
            try:
                async with websockets.connect(self._config.trading_stream_url) as ws:
                    self._trading_ws = ws
                    delay = self._reconnect_delay

                    # Authenticate
                    auth_msg = {
                        "action": "authenticate",
                        "data": {
                            "key_id": self._config.api_key,
                            "secret_key": self._config.api_secret,
                        },
                    }
                    await ws.send(json.dumps(auth_msg))
                    auth_resp = await ws.recv()
                    logger.info(f"Trading stream auth: {auth_resp}")

                    # Listen for trade updates
                    listen_msg = {
                        "action": "listen",
                        "data": {"streams": ["trade_updates"]},
                    }
                    await ws.send(json.dumps(listen_msg))

                    async for message in ws:
                        if not self._running:
                            break
                        await self._handle_trading_message(message)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._running:
                    logger.warning(f"Trading stream error: {e}, reconnecting in {delay}s")
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, self._max_reconnect_delay)

    async def _send_subscription_message(self) -> None:
        """Send subscription request to data WebSocket."""
        if not self._data_ws:
            return

        sub_msg: dict[str, Any] = {"action": "subscribe"}
        for channel in [StreamChannel.TRADES, StreamChannel.QUOTES, StreamChannel.BARS]:
            symbols = self._subscriptions.get(channel, set())
            if symbols:
                sub_msg[channel.value] = sorted(symbols)

        await self._data_ws.send(json.dumps(sub_msg))
        logger.info(f"Subscribed: {sub_msg}")

    async def _handle_data_message(self, raw: str) -> None:
        """Handle incoming market data message."""
        try:
            messages = json.loads(raw)
            if not isinstance(messages, list):
                messages = [messages]

            for msg in messages:
                msg_type = msg.get("T", "")
                symbol = msg.get("S", "")

                if msg_type == "t":  # trade
                    event = StreamEvent(
                        channel=StreamChannel.TRADES, symbol=symbol, data=msg
                    )
                elif msg_type == "q":  # quote
                    event = StreamEvent(
                        channel=StreamChannel.QUOTES, symbol=symbol, data=msg
                    )
                elif msg_type == "b":  # bar
                    event = StreamEvent(
                        channel=StreamChannel.BARS, symbol=symbol, data=msg
                    )
                elif msg_type == "d":  # daily bar
                    event = StreamEvent(
                        channel=StreamChannel.DAILY_BARS, symbol=symbol, data=msg
                    )
                else:
                    continue

                # Dispatch to callbacks
                for cb in self._callbacks.get(event.channel, []):
                    try:
                        result = cb(event)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"Callback error: {e}")

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from data stream: {raw[:100]}")

    async def _handle_trading_message(self, raw: str) -> None:
        """Handle incoming trading stream message."""
        try:
            msg = json.loads(raw)
            stream = msg.get("stream", "")

            if stream == "trade_updates":
                data = msg.get("data", {})
                update = OrderUpdate.from_stream(data)

                for cb in self._order_callbacks:
                    try:
                        result = cb(update)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"Order callback error: {e}")

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from trading stream: {raw[:100]}")
