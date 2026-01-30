"""Base broker interface for order execution.

Defines the Protocol that all broker implementations must follow,
enabling paper trading, Alpaca, and future broker integrations.
"""

from typing import Callable, Optional, Protocol, runtime_checkable

from src.execution.models import (
    AccountInfo,
    Order,
    OrderRequest,
    OrderStatus,
    Position,
)


@runtime_checkable
class BrokerInterface(Protocol):
    """Protocol defining the broker interface.

    All broker implementations (paper, Alpaca, IB) must implement
    these methods to be interchangeable.
    """

    async def connect(self) -> bool:
        """Connect to the broker.

        Returns:
            True if connection successful, False otherwise.
        """
        ...

    async def disconnect(self) -> None:
        """Disconnect from the broker."""
        ...

    async def get_account(self) -> AccountInfo:
        """Get current account information.

        Returns:
            AccountInfo with equity, cash, buying power, etc.
        """
        ...

    async def get_positions(self) -> list[Position]:
        """Get all current positions.

        Returns:
            List of Position objects for all holdings.
        """
        ...

    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a specific symbol.

        Args:
            symbol: Stock ticker symbol.

        Returns:
            Position if held, None otherwise.
        """
        ...

    async def get_orders(
        self,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
    ) -> list[Order]:
        """Get orders, optionally filtered by status.

        Args:
            status: Filter by order status (None for all).
            limit: Maximum number of orders to return.

        Returns:
            List of Order objects.
        """
        ...

    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get a specific order by ID.

        Args:
            order_id: Order identifier (UUID or broker ID).

        Returns:
            Order if found, None otherwise.
        """
        ...

    async def submit_order(self, request: OrderRequest) -> Order:
        """Submit an order for execution.

        Args:
            request: OrderRequest with symbol, qty, side, type, etc.

        Returns:
            Order object with status and ID.

        Raises:
            ValueError: If order validation fails.
            RuntimeError: If broker rejects order.
        """
        ...

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order.

        Args:
            order_id: Order identifier to cancel.

        Returns:
            True if cancellation requested, False if order not found.
        """
        ...

    async def cancel_all_orders(self) -> int:
        """Cancel all pending orders.

        Returns:
            Number of orders cancelled.
        """
        ...

    async def get_quote(self, symbol: str) -> dict:
        """Get current quote for a symbol.

        Args:
            symbol: Stock ticker symbol.

        Returns:
            Dict with 'bid', 'ask', 'last', 'volume' keys.
        """
        ...

    async def stream_trade_updates(
        self,
        callback: Callable[[Order], None],
    ) -> None:
        """Stream real-time order updates.

        Args:
            callback: Function called with Order on each update.
        """
        ...

    @property
    def is_paper(self) -> bool:
        """Whether this is a paper trading account."""
        ...

    @property
    def is_connected(self) -> bool:
        """Whether currently connected to broker."""
        ...


class BaseBroker:
    """Base class with common broker functionality.

    Provides shared utilities for broker implementations.
    Not meant to be instantiated directly.
    """

    def __init__(self):
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def _validate_order_request(self, request: OrderRequest) -> None:
        """Validate an order request before submission.

        Raises:
            ValueError: If request is invalid.
        """
        if request.qty <= 0:
            raise ValueError("Order quantity must be positive")

        if request.symbol is None or len(request.symbol) == 0:
            raise ValueError("Order symbol is required")

        # Limit price validation
        if request.limit_price is not None and request.limit_price <= 0:
            raise ValueError("Limit price must be positive")

        # Stop price validation
        if request.stop_price is not None and request.stop_price <= 0:
            raise ValueError("Stop price must be positive")
