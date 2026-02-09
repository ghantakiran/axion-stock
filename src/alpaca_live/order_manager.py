"""Alpaca Order Lifecycle Manager (PRD-139).

Manages the full order lifecycle: submit → track → fill/cancel.
Bridges between the trade executor's OrderRequest and Alpaca's API.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional
import logging
import uuid

from src.alpaca_live.client import AlpacaClient, AlpacaOrder
from src.alpaca_live.streaming import AlpacaStreaming, OrderUpdate

logger = logging.getLogger(__name__)


class OrderLifecycleState(str, Enum):
    """Order lifecycle states."""
    PENDING = "pending"         # Created locally, not yet submitted
    SUBMITTED = "submitted"     # Sent to Alpaca
    ACCEPTED = "accepted"       # Accepted by Alpaca
    PARTIAL = "partial_fill"    # Partially filled
    FILLED = "filled"           # Fully filled
    CANCELED = "canceled"       # Canceled
    REJECTED = "rejected"       # Rejected by Alpaca
    EXPIRED = "expired"         # Expired
    FAILED = "failed"           # Submission failed


@dataclass
class ManagedOrder:
    """An order tracked through its full lifecycle."""
    local_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    alpaca_order_id: str = ""

    # Order details
    symbol: str = ""
    side: str = "buy"
    qty: float = 0.0
    order_type: str = "market"
    time_in_force: str = "day"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    trail_percent: Optional[float] = None
    extended_hours: bool = False

    # State
    state: OrderLifecycleState = OrderLifecycleState.PENDING
    filled_qty: float = 0.0
    filled_avg_price: float = 0.0
    remaining_qty: float = 0.0

    # Metadata
    signal_id: Optional[str] = None  # Link to EMA signal
    strategy: str = ""
    notes: str = ""

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    last_update: Optional[datetime] = None

    # Error tracking
    error_message: str = ""
    retry_count: int = 0

    @property
    def is_terminal(self) -> bool:
        """Check if order is in a terminal state."""
        return self.state in (
            OrderLifecycleState.FILLED,
            OrderLifecycleState.CANCELED,
            OrderLifecycleState.REJECTED,
            OrderLifecycleState.EXPIRED,
            OrderLifecycleState.FAILED,
        )

    @property
    def is_active(self) -> bool:
        """Check if order is still active."""
        return self.state in (
            OrderLifecycleState.PENDING,
            OrderLifecycleState.SUBMITTED,
            OrderLifecycleState.ACCEPTED,
            OrderLifecycleState.PARTIAL,
        )

    @property
    def fill_pct(self) -> float:
        """Fill percentage."""
        if self.qty <= 0:
            return 0.0
        return (self.filled_qty / self.qty) * 100

    def update_from_alpaca(self, alpaca_order: AlpacaOrder) -> None:
        """Update from Alpaca order data."""
        self.alpaca_order_id = alpaca_order.order_id
        self.filled_qty = alpaca_order.filled_qty
        self.filled_avg_price = alpaca_order.filled_avg_price
        self.remaining_qty = self.qty - alpaca_order.filled_qty
        self.last_update = datetime.now(timezone.utc)

        status_map = {
            "new": OrderLifecycleState.SUBMITTED,
            "accepted": OrderLifecycleState.ACCEPTED,
            "partially_filled": OrderLifecycleState.PARTIAL,
            "filled": OrderLifecycleState.FILLED,
            "canceled": OrderLifecycleState.CANCELED,
            "expired": OrderLifecycleState.EXPIRED,
            "rejected": OrderLifecycleState.REJECTED,
            "pending_new": OrderLifecycleState.SUBMITTED,
            "pending_cancel": OrderLifecycleState.SUBMITTED,
            "pending_replace": OrderLifecycleState.SUBMITTED,
        }
        self.state = status_map.get(alpaca_order.status, self.state)

        if self.state == OrderLifecycleState.FILLED and not self.filled_at:
            self.filled_at = datetime.now(timezone.utc)
        elif self.state == OrderLifecycleState.CANCELED and not self.canceled_at:
            self.canceled_at = datetime.now(timezone.utc)

    def update_from_stream(self, update: OrderUpdate) -> None:
        """Update from streaming order update."""
        self.filled_qty = update.filled_qty
        self.filled_avg_price = update.filled_avg_price
        self.remaining_qty = self.qty - update.filled_qty
        self.last_update = datetime.now(timezone.utc)

        event_map = {
            "new": OrderLifecycleState.SUBMITTED,
            "fill": OrderLifecycleState.FILLED,
            "partial_fill": OrderLifecycleState.PARTIAL,
            "canceled": OrderLifecycleState.CANCELED,
            "expired": OrderLifecycleState.EXPIRED,
            "rejected": OrderLifecycleState.REJECTED,
            "replaced": OrderLifecycleState.SUBMITTED,
        }
        self.state = event_map.get(update.event, self.state)

        if self.state == OrderLifecycleState.FILLED:
            self.filled_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "local_id": self.local_id,
            "alpaca_order_id": self.alpaca_order_id,
            "symbol": self.symbol,
            "side": self.side,
            "qty": self.qty,
            "order_type": self.order_type,
            "state": self.state.value,
            "filled_qty": self.filled_qty,
            "filled_avg_price": self.filled_avg_price,
            "fill_pct": self.fill_pct,
            "signal_id": self.signal_id,
            "created_at": self.created_at.isoformat(),
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "error_message": self.error_message,
        }


# Callback type
OrderLifecycleCallback = Callable[[ManagedOrder, str], Any]


class OrderManager:
    """Manages order lifecycle from creation through fill/cancel.

    Integrates with AlpacaClient for REST operations and
    AlpacaStreaming for real-time order updates.

    Example:
        manager = OrderManager(client, streaming)
        order = await manager.submit_order(
            symbol="AAPL", qty=10, side="buy",
            signal_id="ema_signal_123",
        )
        print(order.state)  # OrderLifecycleState.SUBMITTED
    """

    def __init__(
        self,
        client: AlpacaClient,
        streaming: Optional[AlpacaStreaming] = None,
        max_retries: int = 2,
    ):
        self._client = client
        self._streaming = streaming
        self._max_retries = max_retries
        self._orders: dict[str, ManagedOrder] = {}  # local_id -> ManagedOrder
        self._alpaca_map: dict[str, str] = {}  # alpaca_order_id -> local_id
        self._callbacks: list[OrderLifecycleCallback] = []

        # Register streaming handler
        if streaming:
            streaming.on_order_update(self._handle_order_update)

    @property
    def orders(self) -> dict[str, ManagedOrder]:
        """Get all managed orders."""
        return dict(self._orders)

    @property
    def active_orders(self) -> list[ManagedOrder]:
        """Get active (non-terminal) orders."""
        return [o for o in self._orders.values() if o.is_active]

    @property
    def filled_orders(self) -> list[ManagedOrder]:
        """Get filled orders."""
        return [o for o in self._orders.values()
                if o.state == OrderLifecycleState.FILLED]

    def on_lifecycle_event(self, callback: OrderLifecycleCallback) -> None:
        """Register callback for order lifecycle events."""
        self._callbacks.append(callback)

    async def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        time_in_force: str = "day",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        trail_percent: Optional[float] = None,
        extended_hours: bool = False,
        signal_id: Optional[str] = None,
        strategy: str = "",
    ) -> ManagedOrder:
        """Submit an order and track its lifecycle."""
        order = ManagedOrder(
            symbol=symbol,
            side=side,
            qty=qty,
            order_type=order_type,
            time_in_force=time_in_force,
            limit_price=limit_price,
            stop_price=stop_price,
            trail_percent=trail_percent,
            extended_hours=extended_hours,
            signal_id=signal_id,
            strategy=strategy,
            remaining_qty=qty,
        )

        self._orders[order.local_id] = order

        try:
            alpaca_order = await self._client.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                order_type=order_type,
                time_in_force=time_in_force,
                limit_price=limit_price,
                stop_price=stop_price,
                trail_percent=trail_percent,
                extended_hours=extended_hours,
                client_order_id=order.local_id,
            )

            order.update_from_alpaca(alpaca_order)
            order.submitted_at = datetime.now(timezone.utc)
            self._alpaca_map[alpaca_order.order_id] = order.local_id

            await self._notify("submitted", order)
            logger.info(
                f"Order submitted: {symbol} {side} {qty} "
                f"(local={order.local_id}, alpaca={alpaca_order.order_id})"
            )

        except Exception as e:
            order.state = OrderLifecycleState.FAILED
            order.error_message = str(e)
            await self._notify("failed", order)
            logger.error(f"Order submission failed: {e}")

        return order

    async def cancel_order(self, local_id: str) -> bool:
        """Cancel a managed order."""
        order = self._orders.get(local_id)
        if not order or order.is_terminal:
            return False

        try:
            success = await self._client.cancel_order(order.alpaca_order_id)
            if success:
                order.state = OrderLifecycleState.CANCELED
                order.canceled_at = datetime.now(timezone.utc)
                await self._notify("canceled", order)
            return success
        except Exception as e:
            logger.error(f"Cancel failed for {local_id}: {e}")
            return False

    async def cancel_all(self) -> int:
        """Cancel all active orders."""
        canceled = 0
        for order in self.active_orders:
            if await self.cancel_order(order.local_id):
                canceled += 1
        return canceled

    async def refresh_order(self, local_id: str) -> Optional[ManagedOrder]:
        """Refresh order state from Alpaca API."""
        order = self._orders.get(local_id)
        if not order or not order.alpaca_order_id:
            return order

        try:
            alpaca_order = await self._client.get_order(order.alpaca_order_id)
            if alpaca_order:
                old_state = order.state
                order.update_from_alpaca(alpaca_order)
                if order.state != old_state:
                    await self._notify(order.state.value, order)
        except Exception as e:
            logger.error(f"Refresh failed for {local_id}: {e}")

        return order

    def get_order(self, local_id: str) -> Optional[ManagedOrder]:
        """Get managed order by local ID."""
        return self._orders.get(local_id)

    def get_orders_for_symbol(self, symbol: str) -> list[ManagedOrder]:
        """Get all orders for a symbol."""
        return [o for o in self._orders.values() if o.symbol == symbol]

    def get_order_history(self) -> list[dict]:
        """Get order history as list of dicts."""
        return [o.to_dict() for o in sorted(
            self._orders.values(),
            key=lambda x: x.created_at,
            reverse=True,
        )]

    async def _handle_order_update(self, update: OrderUpdate) -> None:
        """Handle streaming order update."""
        local_id = self._alpaca_map.get(update.order_id)
        if not local_id:
            return

        order = self._orders.get(local_id)
        if not order:
            return

        old_state = order.state
        order.update_from_stream(update)

        if order.state != old_state:
            await self._notify(update.event, order)
            logger.info(
                f"Order update: {order.symbol} {old_state.value} → {order.state.value}"
            )

    async def _notify(self, event: str, order: ManagedOrder) -> None:
        """Notify callbacks of lifecycle event."""
        for cb in self._callbacks:
            try:
                result = cb(order, event)
                if hasattr(result, "__await__"):
                    await result
            except Exception as e:
                logger.error(f"Lifecycle callback error: {e}")
