"""Polygon.io WebSocket client for real-time price streaming.

Connects to Polygon WebSocket, subscribes to trade events,
and pushes updates to Redis quote cache in real-time.
"""

import asyncio
import json
import logging
from typing import Callable, Optional

import websockets

from src.cache.redis_client import cache
from src.settings import get_settings

logger = logging.getLogger(__name__)


class PolygonWebSocket:
    """Real-time price streaming via Polygon.io WebSocket."""

    def __init__(self):
        self.settings = get_settings()
        self._ws = None
        self._subscriptions: set[str] = set()
        self._callbacks: list[Callable] = []
        self._running = False
        self._reconnect_delay = 5

    @property
    def _enabled(self) -> bool:
        return bool(self.settings.polygon_api_key)

    async def connect(self) -> bool:
        """Connect and authenticate to Polygon WebSocket."""
        if not self._enabled:
            logger.info("Polygon WebSocket disabled (no API key)")
            return False

        try:
            self._ws = await websockets.connect(
                self.settings.polygon_ws_url,
                ping_interval=30,
                ping_timeout=10,
            )
            # Authenticate
            await self._ws.send(json.dumps({
                "action": "auth",
                "params": self.settings.polygon_api_key,
            }))
            response = await self._ws.recv()
            messages = json.loads(response)
            if isinstance(messages, list) and messages[0].get("status") == "auth_success":
                logger.info("Polygon WebSocket authenticated")
                return True
            else:
                logger.error("Polygon WebSocket auth failed: %s", messages)
                return False
        except Exception as e:
            logger.error("Polygon WebSocket connect failed: %s", e)
            return False

    async def subscribe(self, tickers: list[str]) -> None:
        """Subscribe to trade events for given tickers."""
        if not self._ws:
            return

        channels = [f"T.{t}" for t in tickers]
        self._subscriptions.update(tickers)
        await self._ws.send(json.dumps({
            "action": "subscribe",
            "params": ",".join(channels),
        }))
        logger.info("Subscribed to %d tickers", len(tickers))

    async def unsubscribe(self, tickers: list[str]) -> None:
        """Unsubscribe from trade events."""
        if not self._ws:
            return

        channels = [f"T.{t}" for t in tickers]
        self._subscriptions.difference_update(tickers)
        await self._ws.send(json.dumps({
            "action": "unsubscribe",
            "params": ",".join(channels),
        }))

    def on_trade(self, callback: Callable) -> None:
        """Register a callback for trade events."""
        self._callbacks.append(callback)

    async def listen(self) -> None:
        """Main event loop. Processes incoming trades and updates cache."""
        self._running = True
        logger.info("Polygon WebSocket listener started")

        while self._running:
            try:
                msg = await asyncio.wait_for(self._ws.recv(), timeout=30)
                events = json.loads(msg)

                if not isinstance(events, list):
                    events = [events]

                for event in events:
                    ev_type = event.get("ev")
                    if ev_type == "T":  # Trade event
                        ticker = event.get("sym")
                        quote = {
                            "ticker": ticker,
                            "price": event.get("p"),
                            "size": event.get("s"),
                            "timestamp": event.get("t"),
                            "conditions": event.get("c", []),
                            "exchange": event.get("x"),
                            "source": "polygon_ws",
                        }
                        # Update Redis cache
                        await cache.set_quote(ticker, quote)

                        # Notify callbacks
                        for cb in self._callbacks:
                            try:
                                if asyncio.iscoroutinefunction(cb):
                                    await cb(ticker, quote)
                                else:
                                    cb(ticker, quote)
                            except Exception as e:
                                logger.warning("Trade callback error: %s", e)

                    elif ev_type == "status":
                        logger.debug("Polygon status: %s", event.get("message"))

            except asyncio.TimeoutError:
                # No data received, send implicit heartbeat via ping
                continue
            except websockets.ConnectionClosed:
                logger.warning("Polygon WebSocket disconnected, reconnecting...")
                await self._reconnect()
            except Exception as e:
                logger.error("Polygon WebSocket error: %s", e)
                await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the listener and close connection."""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        logger.info("Polygon WebSocket stopped")

    async def _reconnect(self) -> None:
        """Reconnect with exponential backoff."""
        delay = self._reconnect_delay
        for attempt in range(5):
            logger.info("Reconnect attempt %d in %ds...", attempt + 1, delay)
            await asyncio.sleep(delay)
            if await self.connect():
                if self._subscriptions:
                    await self.subscribe(list(self._subscriptions))
                return
            delay = min(delay * 2, 60)

        logger.error("Failed to reconnect after 5 attempts")
        self._running = False
