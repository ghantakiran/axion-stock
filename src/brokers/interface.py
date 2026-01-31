"""Broker Interface Protocol.

Defines the unified interface that all broker implementations must follow.
"""

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Optional, Protocol, runtime_checkable

from src.brokers.config import BrokerType, OrderStatus, BrokerCapabilities
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


@runtime_checkable
class BrokerInterface(Protocol):
    """Protocol defining the unified broker interface.
    
    All broker implementations must implement these methods
    to ensure consistent behavior across different brokers.
    """
    
    # Properties
    @property
    def broker_type(self) -> BrokerType:
        """Get the broker type."""
        ...
    
    @property
    def capabilities(self) -> BrokerCapabilities:
        """Get broker capabilities."""
        ...
    
    # Authentication
    async def connect(self) -> bool:
        """Connect to the broker.
        
        Returns:
            True if connection successful.
        """
        ...
    
    async def disconnect(self) -> None:
        """Disconnect from the broker."""
        ...
    
    async def refresh_token(self) -> bool:
        """Refresh authentication token.
        
        Returns:
            True if refresh successful.
        """
        ...
    
    def is_connected(self) -> bool:
        """Check if connected to broker.
        
        Returns:
            True if connected and authenticated.
        """
        ...
    
    # Account
    async def get_account(self) -> BrokerAccount:
        """Get account information.
        
        Returns:
            BrokerAccount object.
        """
        ...
    
    async def get_balances(self) -> AccountBalances:
        """Get account balances.
        
        Returns:
            AccountBalances object.
        """
        ...
    
    async def get_positions(self) -> list[Position]:
        """Get all positions.
        
        Returns:
            List of Position objects.
        """
        ...
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a specific symbol.
        
        Args:
            symbol: Stock symbol.
            
        Returns:
            Position if exists, None otherwise.
        """
        ...
    
    # Orders
    async def place_order(self, order: OrderRequest) -> OrderResult:
        """Place a new order.
        
        Args:
            order: Order request.
            
        Returns:
            OrderResult with success/failure info.
        """
        ...
    
    async def modify_order(self, order_id: str, changes: OrderModify) -> OrderResult:
        """Modify an existing order.
        
        Args:
            order_id: ID of order to modify.
            changes: Changes to apply.
            
        Returns:
            OrderResult with success/failure info.
        """
        ...
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order.
        
        Args:
            order_id: ID of order to cancel.
            
        Returns:
            True if canceled successfully.
        """
        ...
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID.
        
        Args:
            order_id: Order ID.
            
        Returns:
            Order if found, None otherwise.
        """
        ...
    
    async def get_orders(
        self,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
    ) -> list[Order]:
        """Get orders, optionally filtered by status.
        
        Args:
            status: Filter by status (None for all).
            limit: Maximum number of orders.
            
        Returns:
            List of Order objects.
        """
        ...
    
    # History
    async def get_order_history(
        self,
        start: date,
        end: date,
        symbol: Optional[str] = None,
    ) -> list[Order]:
        """Get historical orders.
        
        Args:
            start: Start date.
            end: End date.
            symbol: Optional symbol filter.
            
        Returns:
            List of historical Order objects.
        """
        ...
    
    async def get_transactions(
        self,
        start: date,
        end: date,
        transaction_type: Optional[str] = None,
    ) -> list[Transaction]:
        """Get account transactions.
        
        Args:
            start: Start date.
            end: End date.
            transaction_type: Optional type filter.
            
        Returns:
            List of Transaction objects.
        """
        ...
    
    # Market Data
    async def get_quote(self, symbol: str) -> Quote:
        """Get quote for a symbol.
        
        Args:
            symbol: Stock symbol.
            
        Returns:
            Quote object.
        """
        ...
    
    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Get quotes for multiple symbols.
        
        Args:
            symbols: List of symbols.
            
        Returns:
            Dict of symbol -> Quote.
        """
        ...


class BaseBroker(ABC):
    """Abstract base class for broker implementations.
    
    Provides common functionality and enforces interface compliance.
    
    Example:
        class MyBroker(BaseBroker):
            async def connect(self) -> bool:
                # Implementation
                pass
    """
    
    def __init__(self, account_id: str = ""):
        self._account_id = account_id
        self._connected = False
        self._last_error: Optional[str] = None
    
    @property
    @abstractmethod
    def broker_type(self) -> BrokerType:
        """Get the broker type."""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> BrokerCapabilities:
        """Get broker capabilities."""
        pass
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the broker."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the broker."""
        pass
    
    @abstractmethod
    async def refresh_token(self) -> bool:
        """Refresh authentication token."""
        pass
    
    @abstractmethod
    async def get_account(self) -> BrokerAccount:
        """Get account information."""
        pass
    
    @abstractmethod
    async def get_balances(self) -> AccountBalances:
        """Get account balances."""
        pass
    
    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Get all positions."""
        pass
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a symbol."""
        positions = await self.get_positions()
        for pos in positions:
            if pos.symbol == symbol:
                return pos
        return None
    
    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResult:
        """Place a new order."""
        pass
    
    @abstractmethod
    async def modify_order(self, order_id: str, changes: OrderModify) -> OrderResult:
        """Modify an existing order."""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        pass
    
    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        pass
    
    @abstractmethod
    async def get_orders(
        self,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
    ) -> list[Order]:
        """Get orders."""
        pass
    
    async def get_order_history(
        self,
        start: date,
        end: date,
        symbol: Optional[str] = None,
    ) -> list[Order]:
        """Get historical orders (default implementation)."""
        orders = await self.get_orders(limit=1000)
        return [
            o for o in orders
            if o.created_at.date() >= start and o.created_at.date() <= end
            and (symbol is None or o.symbol == symbol)
        ]
    
    async def get_transactions(
        self,
        start: date,
        end: date,
        transaction_type: Optional[str] = None,
    ) -> list[Transaction]:
        """Get transactions (default empty implementation)."""
        return []
    
    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote:
        """Get quote for a symbol."""
        pass
    
    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Get quotes for multiple symbols."""
        quotes = {}
        for symbol in symbols:
            try:
                quotes[symbol] = await self.get_quote(symbol)
            except Exception:
                pass
        return quotes
    
    def _log_error(self, error: str) -> None:
        """Log an error."""
        self._last_error = error
    
    def get_last_error(self) -> Optional[str]:
        """Get the last error message."""
        return self._last_error
