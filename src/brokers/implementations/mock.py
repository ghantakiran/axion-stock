"""Mock Broker Implementation.

A mock broker for testing and development.
"""

from datetime import datetime, timezone
from typing import Optional
import logging
import random

from src.brokers.config import (
    BrokerType,
    BrokerCapabilities,
    OrderStatus,
    AssetType,
    AccountType,
    AccountStatus,
)
from src.brokers.models import (
    BrokerAccount,
    AccountBalances,
    Position,
    Order,
    OrderRequest,
    OrderModify,
    OrderResult,
    Quote,
)
from src.brokers.interface import BaseBroker

logger = logging.getLogger(__name__)


class MockBroker(BaseBroker):
    """Mock broker for testing.
    
    Simulates broker behavior without making actual API calls.
    Useful for testing and development.
    
    Example:
        broker = MockBroker(broker_type=BrokerType.SCHWAB)
        await broker.connect()
        positions = await broker.get_positions()
    """
    
    def __init__(
        self,
        broker_type: BrokerType = BrokerType.ALPACA,
        account_id: str = "mock_account",
    ):
        super().__init__(account_id)
        self._broker_type = broker_type
        
        # Mock data
        self._cash = 100000.0
        self._positions: list[Position] = []
        self._orders: list[Order] = []
        
        # Initialize with some positions
        self._init_mock_data()
    
    def _init_mock_data(self):
        """Initialize mock data."""
        self._positions = [
            Position(
                account_id=self._account_id,
                symbol="AAPL",
                asset_type=AssetType.STOCK,
                quantity=100,
                quantity_available=100,
                average_cost=150.0,
                current_price=185.0,
                market_value=18500.0,
                unrealized_pnl=3500.0,
                unrealized_pnl_pct=23.33,
                side="long",
            ),
            Position(
                account_id=self._account_id,
                symbol="MSFT",
                asset_type=AssetType.STOCK,
                quantity=50,
                quantity_available=50,
                average_cost=350.0,
                current_price=378.0,
                market_value=18900.0,
                unrealized_pnl=1400.0,
                unrealized_pnl_pct=8.0,
                side="long",
            ),
            Position(
                account_id=self._account_id,
                symbol="GOOGL",
                asset_type=AssetType.STOCK,
                quantity=75,
                quantity_available=75,
                average_cost=130.0,
                current_price=141.0,
                market_value=10575.0,
                unrealized_pnl=825.0,
                unrealized_pnl_pct=8.46,
                side="long",
            ),
        ]
    
    @property
    def broker_type(self) -> BrokerType:
        return self._broker_type
    
    @property
    def capabilities(self) -> BrokerCapabilities:
        return BrokerCapabilities(
            broker=self._broker_type,
            stocks=True,
            options=True,
            etfs=True,
            margin=True,
            short_selling=True,
            extended_hours=True,
            fractional_shares=True,
        )
    
    async def connect(self) -> bool:
        """Connect to mock broker."""
        self._connected = True
        logger.info(f"Connected to mock {self._broker_type.value}")
        return True
    
    async def disconnect(self) -> None:
        """Disconnect from mock broker."""
        self._connected = False
        logger.info(f"Disconnected from mock {self._broker_type.value}")
    
    async def refresh_token(self) -> bool:
        """Refresh token (always succeeds for mock)."""
        return True
    
    async def get_account(self) -> BrokerAccount:
        """Get mock account info."""
        return BrokerAccount(
            account_id=self._account_id,
            broker=self._broker_type,
            account_type=AccountType.MARGIN,
            account_name=f"Mock {self._broker_type.value.title()} Account",
            status=AccountStatus.ACTIVE,
            can_trade_stocks=True,
            can_trade_options=True,
            can_trade_margin=True,
            can_short=True,
            currency="USD",
        )
    
    async def get_balances(self) -> AccountBalances:
        """Get mock account balances."""
        market_value = sum(p.market_value for p in self._positions)
        total_pnl = sum(p.unrealized_pnl for p in self._positions)
        
        return AccountBalances(
            account_id=self._account_id,
            currency="USD",
            cash=self._cash,
            cash_available=self._cash * 0.9,
            cash_withdrawable=self._cash * 0.8,
            buying_power=self._cash * 2,
            day_trading_buying_power=self._cash * 4,
            margin_buying_power=self._cash * 2,
            total_value=self._cash + market_value,
            market_value=market_value,
            long_market_value=market_value,
            day_pnl=random.uniform(-500, 500),
            total_pnl=total_pnl,
        )
    
    async def get_positions(self) -> list[Position]:
        """Get mock positions."""
        # Update prices slightly for realism
        for pos in self._positions:
            change = random.uniform(-0.02, 0.02)
            pos.current_price *= (1 + change)
            pos.market_value = pos.quantity * pos.current_price
            pos.unrealized_pnl = pos.market_value - (pos.quantity * pos.average_cost)
            pos.unrealized_pnl_pct = (pos.unrealized_pnl / (pos.quantity * pos.average_cost)) * 100
        
        return self._positions.copy()
    
    async def place_order(self, order: OrderRequest) -> OrderResult:
        """Place a mock order."""
        import uuid
        order_id = uuid.uuid4().hex[:12]
        
        # Simulate market order fill
        fill_price = 100.0  # Would get from quote
        
        new_order = Order(
            order_id=order_id,
            account_id=self._account_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            time_in_force=order.time_in_force,
            limit_price=order.limit_price,
            stop_price=order.stop_price,
            status=OrderStatus.FILLED,
            filled_quantity=order.quantity,
            filled_avg_price=fill_price,
        )
        
        self._orders.append(new_order)
        
        return OrderResult(
            success=True,
            order_id=order_id,
            status=OrderStatus.FILLED,
            message="Order filled (mock)",
            filled_quantity=order.quantity,
            filled_price=fill_price,
        )
    
    async def modify_order(self, order_id: str, changes: OrderModify) -> OrderResult:
        """Modify a mock order."""
        for order in self._orders:
            if order.order_id == order_id and order.status == OrderStatus.OPEN:
                if changes.quantity:
                    order.quantity = changes.quantity
                if changes.limit_price:
                    order.limit_price = changes.limit_price
                
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    status=order.status,
                    message="Order modified (mock)",
                )
        
        return OrderResult(
            success=False,
            message="Order not found or not modifiable",
        )
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a mock order."""
        for order in self._orders:
            if order.order_id == order_id and order.status == OrderStatus.OPEN:
                order.status = OrderStatus.CANCELED
                return True
        return False
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get mock order by ID."""
        for order in self._orders:
            if order.order_id == order_id:
                return order
        return None
    
    async def get_orders(
        self,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
    ) -> list[Order]:
        """Get mock orders."""
        orders = self._orders.copy()
        if status:
            orders = [o for o in orders if o.status == status]
        return orders[:limit]
    
    async def get_quote(self, symbol: str) -> Quote:
        """Get mock quote."""
        base_prices = {
            "AAPL": 185.0,
            "MSFT": 378.0,
            "GOOGL": 141.0,
            "AMZN": 178.0,
            "TSLA": 250.0,
        }
        
        base = base_prices.get(symbol, 100.0)
        spread = base * 0.001  # 0.1% spread
        
        return Quote(
            symbol=symbol,
            bid=base - spread/2,
            ask=base + spread/2,
            last=base,
            volume=random.randint(1000000, 50000000),
            bid_size=random.randint(100, 1000),
            ask_size=random.randint(100, 1000),
        )
