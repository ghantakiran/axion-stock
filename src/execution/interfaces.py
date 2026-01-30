"""Broker interface definitions.

Defines the abstract interface that all broker implementations must follow.
This enables seamless switching between paper trading, Alpaca, IB, etc.
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional

from src.execution.models import (
    AccountInfo,
    Order,
    OrderRequest,
    Position,
    Trade,
)


class BrokerInterface(ABC):
    """Abstract interface for all brokerage integrations.
    
    All broker implementations (Paper, Alpaca, IB, etc.) must implement
    this interface to ensure consistent behavior across the platform.
    """
    
    # =========================================================================
    # Connection Management
    # =========================================================================
    
    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the brokerage.
        
        Returns:
            True if connection successful, False otherwise.
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the brokerage."""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if currently connected to the brokerage."""
        pass
    
    # =========================================================================
    # Account Information
    # =========================================================================
    
    @abstractmethod
    async def get_account(self) -> AccountInfo:
        """Get current account information.
        
        Returns:
            AccountInfo with buying power, equity, margin, etc.
        """
        pass
    
    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Get all current positions.
        
        Returns:
            List of Position objects for all holdings.
        """
        pass
    
    @abstractmethod
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a specific symbol.
        
        Args:
            symbol: The ticker symbol.
            
        Returns:
            Position if exists, None otherwise.
        """
        pass
    
    # =========================================================================
    # Order Management
    # =========================================================================
    
    @abstractmethod
    async def submit_order(self, order: OrderRequest) -> Order:
        """Submit an order for execution.
        
        Args:
            order: OrderRequest with order details.
            
        Returns:
            Order object with execution status.
            
        Raises:
            OrderValidationError: If order fails pre-trade validation.
            BrokerError: If broker rejects the order.
        """
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order.
        
        Args:
            order_id: The order ID to cancel.
            
        Returns:
            True if cancellation successful, False otherwise.
        """
        pass
    
    @abstractmethod
    async def cancel_all_orders(self) -> int:
        """Cancel all pending orders.
        
        Returns:
            Number of orders cancelled.
        """
        pass
    
    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID.
        
        Args:
            order_id: The order ID.
            
        Returns:
            Order if found, None otherwise.
        """
        pass
    
    @abstractmethod
    async def get_orders(
        self,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[Order]:
        """Get orders with optional filtering.
        
        Args:
            status: Filter by status ('open', 'closed', 'all').
            limit: Maximum number of orders to return.
            
        Returns:
            List of Order objects.
        """
        pass
    
    # =========================================================================
    # Market Data (Basic)
    # =========================================================================
    
    @abstractmethod
    async def get_last_price(self, symbol: str) -> float:
        """Get the last traded price for a symbol.
        
        Args:
            symbol: The ticker symbol.
            
        Returns:
            Last traded price.
        """
        pass
    
    @abstractmethod
    async def get_last_prices(self, symbols: list[str]) -> dict[str, float]:
        """Get last prices for multiple symbols.
        
        Args:
            symbols: List of ticker symbols.
            
        Returns:
            Dict mapping symbol to last price.
        """
        pass
    
    # =========================================================================
    # Streaming (Optional)
    # =========================================================================
    
    async def stream_trade_updates(self, callback: Callable[[Order], None]) -> None:
        """Stream real-time trade/order updates.
        
        Args:
            callback: Function called with each order update.
        """
        raise NotImplementedError("Streaming not supported by this broker")
    
    async def stream_positions(self, callback: Callable[[Position], None]) -> None:
        """Stream real-time position updates.
        
        Args:
            callback: Function called with each position update.
        """
        raise NotImplementedError("Streaming not supported by this broker")
    
    # =========================================================================
    # Portfolio History
    # =========================================================================
    
    async def get_portfolio_history(
        self,
        period: str = "1M",
        timeframe: str = "1D",
    ) -> list[dict]:
        """Get historical portfolio values.
        
        Args:
            period: History period ('1D', '1W', '1M', '3M', '1Y', 'all').
            timeframe: Data granularity ('1Min', '5Min', '1H', '1D').
            
        Returns:
            List of dicts with timestamp, equity, profit_loss, etc.
        """
        raise NotImplementedError("Portfolio history not supported by this broker")
    
    # =========================================================================
    # Trade History
    # =========================================================================
    
    async def get_trades(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 100,
    ) -> list[Trade]:
        """Get historical trades.
        
        Args:
            start: Start date (ISO format).
            end: End date (ISO format).
            limit: Maximum number of trades.
            
        Returns:
            List of Trade objects.
        """
        raise NotImplementedError("Trade history not supported by this broker")


class BrokerError(Exception):
    """Base exception for broker-related errors."""
    pass


class OrderValidationError(BrokerError):
    """Raised when order fails pre-trade validation."""
    pass


class InsufficientFundsError(BrokerError):
    """Raised when account has insufficient buying power."""
    pass


class PositionLimitError(BrokerError):
    """Raised when order would exceed position limits."""
    pass


class MarketClosedError(BrokerError):
    """Raised when trying to trade while market is closed."""
    pass
