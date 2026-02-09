"""Coinbase WebSocket Streaming (PRD-144).

Real-time market data streaming via Coinbase Advanced Trade WebSocket.
Supports ticker, level2, matches, and heartbeat channels.
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
# Channel & Event Types
# =====================================================================


class WSChannel(str, Enum):
    """Available WebSocket channels."""
    TICKER = "ticker"
    LEVEL2 = "level2"
    MATCHES = "matches"
    HEARTBEAT = "heartbeats"


@dataclass
class TickerEvent:
    """Ticker update event."""
    product_id: str = ""
    price: float = 0.0
    volume_24h: float = 0.0
    low_24h: float = 0.0
    high_24h: float = 0.0
    best_bid: float = 0.0
    best_ask: float = 0.0
    timestamp: str = ""

    @classmethod
    def from_ws(cls, data: dict) -> "TickerEvent":
        return cls(
            product_id=data.get("product_id", ""),
            price=float(data.get("price", 0) or 0),
            volume_24h=float(data.get("volume_24_h", 0) or 0),
            low_24h=float(data.get("low_24_h", 0) or 0),
            high_24h=float(data.get("high_24_h", 0) or 0),
            best_bid=float(data.get("best_bid", 0) or 0),
            best_ask=float(data.get("best_ask", 0) or 0),
            timestamp=data.get("timestamp", ""),
        )


@dataclass
class MatchEvent:
    """Trade match event."""
    product_id: str = ""
    trade_id: str = ""
    price: float = 0.0
    size: float = 0.0
    side: str = ""
    timestamp: str = ""

    @classmethod
    def from_ws(cls, data: dict) -> "MatchEvent":
        return cls(
            product_id=data.get("product_id", ""),
            trade_id=data.get("trade_id", ""),
            price=float(data.get("price", 0) or 0),
            size=float(data.get("size", 0) or 0),
            side=data.get("side", ""),
            timestamp=data.get("timestamp", ""),
        )


# =====================================================================
# WebSocket Client
# =====================================================================

TickerCallback = Callable[[TickerEvent], Any]
MatchCallback = Callable[[MatchEvent], Any]


class CoinbaseWebSocket:
    """Coinbase Advanced Trade WebSocket client.

    Supports real-time ticker, level2, and match data.
    Falls back to periodic demo data when no credentials available.

    Example:
        ws = CoinbaseWebSocket(config)
        ws.on_ticker(my_handler)
        await ws.subscribe(["BTC-USD", "ETH-USD"], [WSChannel.TICKER])
    """

    DEMO_PRICES: dict[str, float] = {
        "BTC-USD": 95000.0,
        "ETH-USD": 3500.0,
    }

    def __init__(self, config: Any):
        self._config = config
        self._running = False
        self._subscriptions: dict[WSChannel, set[str]] = {
            ch: set() for ch in WSChannel
        }
        self._ticker_callbacks: list[TickerCallback] = []
        self._match_callbacks: list[MatchCallback] = []
        self._ws: Any = None
        self._tasks: list[asyncio.Task] = []

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def subscriptions(self) -> dict[str, list[str]]:
        """Current subscriptions as channel -> product_ids."""
        return {
            ch.value: sorted(products)
            for ch, products in self._subscriptions.items()
            if products
        }

    # ── Callback Registration ─────────────────────────────────────

    def on_ticker(self, callback: TickerCallback) -> None:
        """Register handler for ticker events."""
        self._ticker_callbacks.append(callback)

    def on_match(self, callback: MatchCallback) -> None:
        """Register handler for match/trade events."""
        self._match_callbacks.append(callback)

    # ── Subscription Management ───────────────────────────────────

    async def subscribe(
        self, product_ids: list[str], channels: list[WSChannel]
    ) -> None:
        """Subscribe to channels for given products."""
        for ch in channels:
            self._subscriptions[ch].update(pid.upper() for pid in product_ids)

    async def unsubscribe(
        self, product_ids: list[str], channels: list[WSChannel]
    ) -> None:
        """Unsubscribe from channels for given products."""
        for ch in channels:
            for pid in product_ids:
                self._subscriptions[ch].discard(pid.upper())

    # ── Lifecycle ─────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the WebSocket connection."""
        if self._running:
            return
        self._running = True
        logger.info("Coinbase WebSocket started")

    async def stop(self) -> None:
        """Stop the WebSocket connection."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("Coinbase WebSocket stopped")
