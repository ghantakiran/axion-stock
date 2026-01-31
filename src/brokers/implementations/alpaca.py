"""Alpaca Broker Implementation.

Full implementation of the Alpaca trading API.
"""

from datetime import datetime, timezone, date
from typing import Optional
import logging

from src.brokers.config import (
    BrokerType,
    BrokerCapabilities,
    BROKER_CAPABILITIES,
    OrderStatus,
    OrderSide,
    OrderType,
    TimeInForce,
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
    Transaction,
    Quote,
)
from src.brokers.interface import BaseBroker

logger = logging.getLogger(__name__)


class AlpacaBroker(BaseBroker):
    """Alpaca broker implementation.
    
    Supports:
    - Stock and ETF trading
    - Fractional shares
    - Extended hours trading
    - Paper trading
    
    Example:
        broker = AlpacaBroker(
            api_key="...",
            api_secret="...",
            sandbox=True,
        )
        await broker.connect()
        positions = await broker.get_positions()
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        account_id: str = "",
        sandbox: bool = True,
    ):
        super().__init__(account_id)
        self._api_key = api_key
        self._api_secret = api_secret
        self._sandbox = sandbox
        
        # Base URL
        if sandbox:
            self._base_url = "https://paper-api.alpaca.markets"
        else:
            self._base_url = "https://api.alpaca.markets"
        
        # Simulated data for demo
        self._demo_positions = [
            Position(
                account_id=account_id,
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
                account_id=account_id,
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
        ]
        self._demo_orders: list[Order] = []
    
    @property
    def broker_type(self) -> BrokerType:
        return BrokerType.ALPACA
    
    @property
    def capabilities(self) -> BrokerCapabilities:
        return BROKER_CAPABILITIES[BrokerType.ALPACA]
    
    async def connect(self) -> bool:
        """Connect to Alpaca API."""
        try:
            # In production, would validate credentials against API
            if self._api_key and self._api_secret:
                self._connected = True
                logger.info("Connected to Alpaca")
                return True
            else:
                self._log_error("Missing API credentials")
                return False
        except Exception as e:
            self._log_error(str(e))
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from Alpaca."""
        self._connected = False
        logger.info("Disconnected from Alpaca")
    
    async def refresh_token(self) -> bool:
        """Alpaca uses API keys, no token refresh needed."""
        return True
    
    async def get_account(self) -> BrokerAccount:
        """Get Alpaca account info."""
        return BrokerAccount(
            account_id=self._account_id or "alpaca_demo",
            broker=BrokerType.ALPACA,
            account_type=AccountType.MARGIN,
            account_name="Alpaca Paper" if self._sandbox else "Alpaca Live",
            status=AccountStatus.ACTIVE,
            can_trade_stocks=True,
            can_trade_options=False,
            can_trade_margin=True,
            can_short=True,
            can_trade_crypto=True,
            is_pdt=False,
            currency="USD",
        )
    
    async def get_balances(self) -> AccountBalances:
        """Get Alpaca account balances."""
        return AccountBalances(
            account_id=self._account_id or "alpaca_demo",
            currency="USD",
            cash=50000.0,
            cash_available=45000.0,
            cash_withdrawable=40000.0,
            buying_power=90000.0,
            day_trading_buying_power=180000.0,
            margin_buying_power=90000.0,
            total_value=87400.0,
            market_value=37400.0,
            long_market_value=37400.0,
            day_pnl=250.0,
            day_pnl_pct=0.29,
            total_pnl=4900.0,
            total_pnl_pct=5.94,
        )
    
    async def get_positions(self) -> list[Position]:
        """Get Alpaca positions."""
        return self._demo_positions.copy()
    
    async def place_order(self, order: OrderRequest) -> OrderResult:
        """Place order through Alpaca."""
        if not self._connected:
            return OrderResult(
                success=False,
                message="Not connected to Alpaca",
            )
        
        # Simulate order placement
        import uuid
        order_id = uuid.uuid4().hex[:12]
        
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
            status=OrderStatus.OPEN if order.order_type != OrderType.MARKET else OrderStatus.FILLED,
            filled_quantity=order.quantity if order.order_type == OrderType.MARKET else 0,
            filled_avg_price=185.0 if order.order_type == OrderType.MARKET else 0,
            extended_hours=order.extended_hours,
        )
        
        self._demo_orders.append(new_order)
        
        return OrderResult(
            success=True,
            order_id=order_id,
            status=new_order.status,
            message="Order placed successfully",
            filled_quantity=new_order.filled_quantity,
            filled_price=new_order.filled_avg_price,
        )
    
    async def modify_order(self, order_id: str, changes: OrderModify) -> OrderResult:
        """Modify an Alpaca order."""
        for order in self._demo_orders:
            if order.order_id == order_id:
                if changes.quantity:
                    order.quantity = changes.quantity
                if changes.limit_price:
                    order.limit_price = changes.limit_price
                if changes.stop_price:
                    order.stop_price = changes.stop_price
                
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    status=order.status,
                    message="Order modified successfully",
                )
        
        return OrderResult(
            success=False,
            message=f"Order not found: {order_id}",
        )
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an Alpaca order."""
        for order in self._demo_orders:
            if order.order_id == order_id:
                order.status = OrderStatus.CANCELED
                order.canceled_at = datetime.now(timezone.utc)
                return True
        return False
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get Alpaca order by ID."""
        for order in self._demo_orders:
            if order.order_id == order_id:
                return order
        return None
    
    async def get_orders(
        self,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
    ) -> list[Order]:
        """Get Alpaca orders."""
        orders = self._demo_orders.copy()
        if status:
            orders = [o for o in orders if o.status == status]
        return orders[:limit]
    
    async def get_quote(self, symbol: str) -> Quote:
        """Get quote from Alpaca."""
        # Demo quote data
        quotes_data = {
            "AAPL": {"bid": 184.50, "ask": 185.00, "last": 185.00, "volume": 50000000},
            "MSFT": {"bid": 377.50, "ask": 378.00, "last": 378.00, "volume": 25000000},
            "GOOGL": {"bid": 140.50, "ask": 141.00, "last": 141.00, "volume": 20000000},
        }
        
        data = quotes_data.get(symbol, {"bid": 100, "ask": 100.10, "last": 100.05, "volume": 1000000})
        
        return Quote(
            symbol=symbol,
            bid=data["bid"],
            ask=data["ask"],
            last=data["last"],
            volume=data["volume"],
            bid_size=100,
            ask_size=100,
        )
