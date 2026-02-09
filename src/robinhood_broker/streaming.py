"""Robinhood Polling-Based Streaming (PRD-143).

Robinhood does not expose a public WebSocket API, so this module
implements polling-based quote and order updates with configurable
intervals and callback dispatch.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional
import logging
import threading
import time

logger = logging.getLogger(__name__)


# =====================================================================
# Update Models
# =====================================================================


@dataclass
class QuoteUpdate:
    """A polled quote update event."""
    symbol: str = ""
    bid_price: float = 0.0
    ask_price: float = 0.0
    last_trade_price: float = 0.0
    volume: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "bid_price": self.bid_price,
            "ask_price": self.ask_price,
            "last_trade_price": self.last_trade_price,
            "volume": self.volume,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class OrderStatusUpdate:
    """A polled order status change event."""
    order_id: str = ""
    symbol: str = ""
    status: str = ""
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    side: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "status": self.status,
            "filled_quantity": self.filled_quantity,
            "average_fill_price": self.average_fill_price,
            "side": self.side,
            "timestamp": self.timestamp.isoformat(),
        }


# Type aliases
QuoteCallback = Callable[[QuoteUpdate], Any]
OrderCallback = Callable[[OrderStatusUpdate], Any]


# =====================================================================
# Streaming Manager
# =====================================================================


class RobinhoodStreaming:
    """Polling-based streaming for Robinhood quotes and orders.

    Since Robinhood lacks a public WebSocket API, this class polls the
    REST API at configurable intervals and dispatches updates to callbacks.

    Example:
        streaming = RobinhoodStreaming(client)
        streaming.on_quote_update(my_quote_handler)
        streaming.on_order_update(my_order_handler)
        streaming.start_polling(interval_seconds=5)
        # ... later
        streaming.stop_polling()
    """

    def __init__(self, client: Any = None):
        self._client = client
        self._running = False
        self._poll_thread: Optional[threading.Thread] = None
        self._interval: float = 5.0
        self._quote_callbacks: list[QuoteCallback] = []
        self._order_callbacks: list[OrderCallback] = []
        self._watched_symbols: list[str] = []
        self._last_order_states: dict[str, str] = {}

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def watched_symbols(self) -> list[str]:
        return list(self._watched_symbols)

    def add_symbols(self, symbols: list[str]) -> None:
        """Add symbols to watch for quote updates."""
        for s in symbols:
            upper = s.upper()
            if upper not in self._watched_symbols:
                self._watched_symbols.append(upper)

    def remove_symbols(self, symbols: list[str]) -> None:
        """Remove symbols from watch list."""
        for s in symbols:
            upper = s.upper()
            if upper in self._watched_symbols:
                self._watched_symbols.remove(upper)

    def on_quote_update(self, callback: QuoteCallback) -> None:
        """Register a callback for quote updates."""
        self._quote_callbacks.append(callback)

    def on_order_update(self, callback: OrderCallback) -> None:
        """Register a callback for order status changes."""
        self._order_callbacks.append(callback)

    def start_polling(self, interval_seconds: float = 5.0) -> None:
        """Start polling for updates in a background thread."""
        if self._running:
            return

        self._interval = interval_seconds
        self._running = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="rh-polling"
        )
        self._poll_thread.start()
        logger.info(f"Robinhood polling started (interval={interval_seconds}s)")

    def stop_polling(self) -> None:
        """Stop the polling loop."""
        self._running = False
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=self._interval + 1)
        self._poll_thread = None
        logger.info("Robinhood polling stopped")

    def _poll_loop(self) -> None:
        """Main polling loop running in background thread."""
        import random

        while self._running:
            try:
                self._poll_quotes()
                self._poll_orders()
            except Exception as e:
                logger.error(f"Polling error: {e}")

            # Sleep in small increments for responsive shutdown
            elapsed = 0.0
            while elapsed < self._interval and self._running:
                time.sleep(min(0.5, self._interval - elapsed))
                elapsed += 0.5

    def _poll_quotes(self) -> None:
        """Poll quotes for watched symbols."""
        if not self._watched_symbols:
            return

        for symbol in self._watched_symbols:
            try:
                if self._client:
                    quote = self._client.get_quote(symbol)
                    update = QuoteUpdate(
                        symbol=quote.symbol,
                        bid_price=quote.bid_price,
                        ask_price=quote.ask_price,
                        last_trade_price=quote.last_trade_price,
                        volume=quote.volume,
                    )
                else:
                    # Demo mode: generate small random fluctuations
                    import random
                    base_prices = {"AAPL": 187.50, "NVDA": 624.00, "TSLA": 325.00}
                    base = base_prices.get(symbol, 150.0)
                    jitter = random.uniform(-0.50, 0.50)
                    update = QuoteUpdate(
                        symbol=symbol,
                        bid_price=round(base + jitter - 0.25, 2),
                        ask_price=round(base + jitter + 0.25, 2),
                        last_trade_price=round(base + jitter, 2),
                        volume=random.randint(1_000_000, 50_000_000),
                    )

                for cb in self._quote_callbacks:
                    try:
                        cb(update)
                    except Exception as e:
                        logger.error(f"Quote callback error: {e}")

            except Exception as e:
                logger.warning(f"Quote poll failed for {symbol}: {e}")

    def _poll_orders(self) -> None:
        """Poll for order status changes."""
        try:
            if self._client:
                orders = self._client.get_orders()
            else:
                return  # No demo order polling without client

            for order in orders:
                prev_status = self._last_order_states.get(order.order_id)
                if prev_status != order.status:
                    self._last_order_states[order.order_id] = order.status
                    if prev_status is not None:  # Skip first-seen orders
                        update = OrderStatusUpdate(
                            order_id=order.order_id,
                            symbol=order.symbol,
                            status=order.status,
                            filled_quantity=order.filled_quantity,
                            average_fill_price=order.average_fill_price,
                            side=order.side,
                        )
                        for cb in self._order_callbacks:
                            try:
                                cb(update)
                            except Exception as e:
                                logger.error(f"Order callback error: {e}")

        except Exception as e:
            logger.warning(f"Order poll failed: {e}")
