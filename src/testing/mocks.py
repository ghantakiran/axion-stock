"""Mock services for testing: broker, market data, Redis."""

import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MockOrder:
    """Simulated order result."""

    order_id: str = ""
    symbol: str = ""
    side: str = "buy"
    quantity: int = 0
    price: float = 0.0
    status: str = "pending"
    filled_quantity: int = 0
    filled_price: float = 0.0
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    latency_ms: float = 0.0

    def __post_init__(self):
        if not self.order_id:
            self.order_id = str(uuid.uuid4())[:8]
        if not self.submitted_at:
            self.submitted_at = datetime.now()


class MockBroker:
    """Simulated broker for order submission with configurable latency
    and fill probability.

    Usage:
        broker = MockBroker(latency_ms=15.0, fill_probability=0.9)
        order = broker.submit_order("AAPL", "buy", 100, 150.0)
    """

    def __init__(
        self,
        latency_ms: float = 10.0,
        fill_probability: float = 0.95,
        slippage_bps: float = 1.0,
    ):
        self.latency_ms = latency_ms
        self.fill_probability = fill_probability
        self.slippage_bps = slippage_bps
        self._orders: List[MockOrder] = []
        self._connected = False
        logger.info(
            f"MockBroker initialized: latency={latency_ms}ms, "
            f"fill_prob={fill_probability}"
        )

    def connect(self) -> bool:
        """Simulate broker connection."""
        self._connected = True
        return True

    def disconnect(self) -> None:
        """Simulate broker disconnection."""
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def submit_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float,
    ) -> MockOrder:
        """Submit a simulated order with configurable latency and fill probability."""
        start = time.time()

        # Simulate latency
        if self.latency_ms > 0:
            time.sleep(self.latency_ms / 1000.0)

        order = MockOrder(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
        )

        # Determine if order fills
        if random.random() < self.fill_probability:
            # Apply slippage
            slippage_mult = 1.0 + (self.slippage_bps / 10000.0)
            if side == "buy":
                order.filled_price = price * slippage_mult
            else:
                order.filled_price = price / slippage_mult
            order.filled_quantity = quantity
            order.status = "filled"
            order.filled_at = datetime.now()
        else:
            order.status = "rejected"

        order.latency_ms = (time.time() - start) * 1000
        self._orders.append(order)
        return order

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        for order in self._orders:
            if order.order_id == order_id and order.status == "pending":
                order.status = "cancelled"
                return True
        return False

    def get_orders(self) -> List[MockOrder]:
        """Return all submitted orders."""
        return list(self._orders)

    def get_order(self, order_id: str) -> Optional[MockOrder]:
        """Get a specific order by ID."""
        for order in self._orders:
            if order.order_id == order_id:
                return order
        return None

    def get_filled_orders(self) -> List[MockOrder]:
        """Return only filled orders."""
        return [o for o in self._orders if o.status == "filled"]

    def get_fill_rate(self) -> float:
        """Compute actual fill rate from order history."""
        if not self._orders:
            return 0.0
        filled = len([o for o in self._orders if o.status == "filled"])
        return filled / len(self._orders)

    def reset(self) -> None:
        """Clear order history."""
        self._orders.clear()


@dataclass
class OHLCVBar:
    """Single OHLCV price bar."""

    timestamp: datetime = field(default_factory=datetime.now)
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0


class MockMarketData:
    """Generate realistic OHLCV market data with configurable volatility.

    Usage:
        md = MockMarketData(volatility=0.02)
        bars = md.generate_bars("AAPL", 100, start_price=150.0)
    """

    def __init__(self, volatility: float = 0.02, seed: Optional[int] = None):
        self.volatility = volatility
        self._cache: Dict[str, List[OHLCVBar]] = {}
        if seed is not None:
            random.seed(seed)
        logger.info(f"MockMarketData initialized: volatility={volatility}")

    def generate_bars(
        self,
        symbol: str,
        n_bars: int = 100,
        start_price: float = 100.0,
        start_date: Optional[datetime] = None,
        interval_minutes: int = 1,
    ) -> List[OHLCVBar]:
        """Generate n_bars of realistic OHLCV data using a random walk."""
        if start_date is None:
            start_date = datetime.now() - timedelta(minutes=n_bars * interval_minutes)

        bars: List[OHLCVBar] = []
        price = start_price

        for i in range(n_bars):
            # Random walk with drift
            ret = random.gauss(0.0001, self.volatility)
            price = price * (1.0 + ret)

            # Generate intrabar volatility
            intra_vol = abs(random.gauss(0, self.volatility * price))
            open_price = price
            close_price = price * (1.0 + random.gauss(0, self.volatility * 0.5))
            high_price = max(open_price, close_price) + intra_vol * 0.5
            low_price = min(open_price, close_price) - intra_vol * 0.5
            volume = max(1000, int(random.gauss(500000, 200000)))

            bar = OHLCVBar(
                timestamp=start_date + timedelta(minutes=i * interval_minutes),
                open=round(open_price, 2),
                high=round(high_price, 2),
                low=round(low_price, 2),
                close=round(close_price, 2),
                volume=volume,
            )
            bars.append(bar)
            price = close_price

        self._cache[symbol] = bars
        return bars

    def get_latest_price(self, symbol: str) -> Optional[float]:
        """Get the latest close price for a symbol."""
        if symbol in self._cache and self._cache[symbol]:
            return self._cache[symbol][-1].close
        return None

    def get_bars(self, symbol: str, n: int = 0) -> List[OHLCVBar]:
        """Retrieve cached bars for a symbol, optionally limited to last n."""
        bars = self._cache.get(symbol, [])
        if n > 0:
            return bars[-n:]
        return list(bars)

    def get_symbols(self) -> List[str]:
        """Return list of symbols with cached data."""
        return list(self._cache.keys())

    def clear_cache(self) -> None:
        """Clear all cached market data."""
        self._cache.clear()


class MockRedis:
    """In-memory Redis mock implementing get/set/delete/exists.

    Usage:
        redis = MockRedis()
        redis.set("key", "value", ttl=60)
        val = redis.get("key")
    """

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._ttls: Dict[str, datetime] = {}
        self._connected = True
        logger.info("MockRedis initialized")

    def _check_expired(self, key: str) -> bool:
        """Check and remove key if expired. Returns True if expired."""
        if key in self._ttls:
            if datetime.now() > self._ttls[key]:
                del self._store[key]
                del self._ttls[key]
                return True
        return False

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a key-value pair with optional TTL in seconds."""
        self._store[key] = value
        if ttl is not None:
            self._ttls[key] = datetime.now() + timedelta(seconds=ttl)
        elif key in self._ttls:
            del self._ttls[key]
        return True

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value by key, returning default if missing or expired."""
        if self._check_expired(key):
            return default
        return self._store.get(key, default)

    def delete(self, key: str) -> bool:
        """Delete a key. Returns True if the key existed."""
        existed = key in self._store
        self._store.pop(key, None)
        self._ttls.pop(key, None)
        return existed

    def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired."""
        if self._check_expired(key):
            return False
        return key in self._store

    def keys(self, pattern: str = "*") -> List[str]:
        """Return all keys matching a simple pattern (supports * wildcard)."""
        # Clean up expired keys first
        for key in list(self._store.keys()):
            self._check_expired(key)

        if pattern == "*":
            return list(self._store.keys())

        # Simple prefix match for patterns like "prefix:*"
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            return [k for k in self._store if k.startswith(prefix)]

        return [k for k in self._store if k == pattern]

    def flush(self) -> None:
        """Clear all data."""
        self._store.clear()
        self._ttls.clear()

    def size(self) -> int:
        """Return number of stored keys (excluding expired)."""
        for key in list(self._store.keys()):
            self._check_expired(key)
        return len(self._store)

    @property
    def is_connected(self) -> bool:
        return self._connected

    def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False

    def connect(self) -> None:
        """Simulate reconnection."""
        self._connected = True
