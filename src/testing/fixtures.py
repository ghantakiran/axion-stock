"""Factory functions for common test data objects."""

import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TestOrder:
    """Test order fixture."""

    order_id: str = ""
    symbol: str = "AAPL"
    side: str = "buy"
    quantity: int = 100
    price: float = 150.0
    order_type: str = "limit"
    status: str = "pending"
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.order_id:
            self.order_id = str(uuid.uuid4())[:8]


@dataclass
class TestPortfolio:
    """Test portfolio fixture."""

    portfolio_id: str = ""
    name: str = "Test Portfolio"
    cash: float = 100000.0
    positions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    total_value: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.portfolio_id:
            self.portfolio_id = str(uuid.uuid4())[:8]
        if self.total_value == 0.0:
            position_value = sum(
                p.get("quantity", 0) * p.get("price", 0)
                for p in self.positions.values()
            )
            self.total_value = self.cash + position_value


@dataclass
class TestSignal:
    """Test trading signal fixture."""

    signal_id: str = ""
    symbol: str = "AAPL"
    signal_type: str = "buy"
    strength: float = 0.75
    source: str = "test_model"
    confidence: float = 0.8
    created_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        if not self.signal_id:
            self.signal_id = str(uuid.uuid4())[:8]


@dataclass
class TestMarketData:
    """Test market data fixture."""

    symbol: str = "AAPL"
    open: float = 150.0
    high: float = 155.0
    low: float = 148.0
    close: float = 153.0
    volume: int = 5000000
    timestamp: datetime = field(default_factory=datetime.now)
    vwap: float = 0.0

    def __post_init__(self):
        if self.vwap == 0.0:
            self.vwap = (self.high + self.low + self.close) / 3.0


def create_test_order(
    symbol: str = "AAPL",
    side: str = "buy",
    quantity: int = 100,
    price: float = 150.0,
    order_type: str = "limit",
    status: str = "pending",
) -> TestOrder:
    """Factory: create a TestOrder with defaults."""
    return TestOrder(
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        order_type=order_type,
        status=status,
    )


def create_test_portfolio(
    name: str = "Test Portfolio",
    cash: float = 100000.0,
    positions: Optional[Dict[str, Dict[str, Any]]] = None,
) -> TestPortfolio:
    """Factory: create a TestPortfolio with defaults."""
    return TestPortfolio(
        name=name,
        cash=cash,
        positions=positions or {},
    )


def create_test_signal(
    symbol: str = "AAPL",
    signal_type: str = "buy",
    strength: float = 0.75,
    source: str = "test_model",
    confidence: float = 0.8,
) -> TestSignal:
    """Factory: create a TestSignal with defaults."""
    return TestSignal(
        symbol=symbol,
        signal_type=signal_type,
        strength=strength,
        source=source,
        confidence=confidence,
    )


def create_test_market_data(
    symbol: str = "AAPL",
    open_price: float = 150.0,
    high: float = 155.0,
    low: float = 148.0,
    close: float = 153.0,
    volume: int = 5000000,
) -> TestMarketData:
    """Factory: create a TestMarketData bar with defaults."""
    return TestMarketData(
        symbol=symbol,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def create_test_orders_batch(
    symbols: Optional[List[str]] = None,
    n: int = 10,
) -> List[TestOrder]:
    """Create a batch of test orders across multiple symbols."""
    symbols = symbols or ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
    orders = []
    for i in range(n):
        sym = symbols[i % len(symbols)]
        side = "buy" if i % 2 == 0 else "sell"
        price = round(random.uniform(50, 500), 2)
        qty = random.randint(10, 500)
        orders.append(create_test_order(symbol=sym, side=side, quantity=qty, price=price))
    return orders


def create_test_portfolio_with_positions(
    n_positions: int = 5,
) -> TestPortfolio:
    """Create a portfolio pre-loaded with random positions."""
    symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "META", "NVDA", "JPM"]
    positions = {}
    for sym in symbols[:n_positions]:
        positions[sym] = {
            "quantity": random.randint(10, 200),
            "price": round(random.uniform(50, 500), 2),
            "cost_basis": round(random.uniform(40, 450), 2),
        }
    return create_test_portfolio(positions=positions)
