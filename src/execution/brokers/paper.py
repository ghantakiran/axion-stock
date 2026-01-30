"""Paper trading broker with simulated execution.

Provides realistic paper trading with slippage modeling,
commission simulation, and in-memory position tracking.
"""

import asyncio
from datetime import datetime
from typing import Callable, Optional
from uuid import uuid4

from src.execution.brokers.base import BaseBroker
from src.execution.models import (
    AccountInfo,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Trade,
    TriggerReason,
)


class SlippageModel:
    """Models market impact and slippage for simulated fills.

    Uses a linear impact model: slippage = participation_rate * impact_factor
    where participation_rate = order_size / avg_daily_volume.
    """

    def __init__(
        self,
        impact_bps_per_pct: float = 10.0,
        base_spread_bps: float = 2.0,
    ):
        """Initialize slippage model.

        Args:
            impact_bps_per_pct: Basis points of impact per 1% of ADV.
            base_spread_bps: Base bid-ask spread in basis points.
        """
        self.impact_bps_per_pct = impact_bps_per_pct
        self.base_spread_bps = base_spread_bps
        # Default ADV for unknown symbols (moderate liquidity)
        self.default_adv = 1_000_000

    def calculate_slippage(
        self,
        price: float,
        qty: float,
        side: OrderSide,
        avg_daily_volume: Optional[float] = None,
    ) -> float:
        """Calculate expected slippage for an order.

        Args:
            price: Current market price.
            qty: Order quantity.
            side: Buy or sell.
            avg_daily_volume: Average daily volume (shares).

        Returns:
            Slippage in dollars (positive = cost).
        """
        adv = avg_daily_volume or self.default_adv

        # Participation rate (what % of daily volume is this order)
        participation_rate = qty / adv

        # Market impact: 10bps per 1% of ADV
        impact_bps = participation_rate * 100 * self.impact_bps_per_pct

        # Add half the spread (we pay the spread)
        total_bps = impact_bps + (self.base_spread_bps / 2)

        # Convert to dollars
        slippage_per_share = price * total_bps / 10_000

        # Sign: buys pay more, sells receive less
        if side == OrderSide.BUY:
            return slippage_per_share * qty
        else:
            return slippage_per_share * qty

    def get_fill_price(
        self,
        price: float,
        qty: float,
        side: OrderSide,
        avg_daily_volume: Optional[float] = None,
    ) -> float:
        """Get the expected fill price including slippage.

        Args:
            price: Current market price.
            qty: Order quantity.
            side: Buy or sell.
            avg_daily_volume: Average daily volume.

        Returns:
            Expected fill price.
        """
        slippage = self.calculate_slippage(price, qty, side, avg_daily_volume)
        slippage_per_share = slippage / qty if qty > 0 else 0

        if side == OrderSide.BUY:
            return price + slippage_per_share
        else:
            return price - slippage_per_share


class PaperBroker(BaseBroker):
    """Paper trading broker with realistic simulated execution.

    Maintains in-memory state for positions, orders, and account.
    Uses SlippageModel for realistic fill simulation.
    """

    def __init__(
        self,
        initial_cash: float = 100_000.0,
        commission_per_share: float = 0.0,
        min_commission: float = 0.0,
        slippage_model: Optional[SlippageModel] = None,
    ):
        """Initialize paper broker.

        Args:
            initial_cash: Starting cash balance.
            commission_per_share: Commission per share traded.
            min_commission: Minimum commission per order.
            slippage_model: Custom slippage model (default: standard).
        """
        super().__init__()
        self._initial_cash = initial_cash
        self._cash = initial_cash
        self._commission_per_share = commission_per_share
        self._min_commission = min_commission
        self._slippage = slippage_model or SlippageModel()

        # In-memory state
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, Order] = {}
        self._trades: list[Trade] = []
        self._update_callbacks: list[Callable[[Order], None]] = []

        # Simulated market prices (updated via set_price or external feed)
        self._prices: dict[str, float] = {}

    @property
    def is_paper(self) -> bool:
        return True

    async def connect(self) -> bool:
        """Paper broker is always connected."""
        self._connected = True
        return True

    async def disconnect(self) -> None:
        """Disconnect (no-op for paper)."""
        self._connected = False

    async def get_account(self) -> AccountInfo:
        """Get current account state."""
        portfolio_value = self._cash + sum(
            p.market_value for p in self._positions.values()
        )
        return AccountInfo(
            equity=portfolio_value,
            cash=self._cash,
            buying_power=self._cash,  # No margin in paper trading
            portfolio_value=portfolio_value,
            margin_used=0.0,
            day_trades_remaining=3,
            pattern_day_trader=False,
            trading_blocked=False,
            account_blocked=False,
        )

    async def get_positions(self) -> list[Position]:
        """Get all current positions with updated prices."""
        positions = []
        for symbol, pos in self._positions.items():
            # Update current price
            if symbol in self._prices:
                pos.current_price = self._prices[symbol]
            positions.append(pos)
        return positions

    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a specific symbol."""
        pos = self._positions.get(symbol)
        if pos and symbol in self._prices:
            pos.current_price = self._prices[symbol]
        return pos

    async def get_orders(
        self,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
    ) -> list[Order]:
        """Get orders, optionally filtered by status."""
        orders = list(self._orders.values())

        if status is not None:
            orders = [o for o in orders if o.status == status]

        # Sort by created_at descending
        orders.sort(key=lambda o: o.created_at, reverse=True)
        return orders[:limit]

    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get a specific order by ID."""
        return self._orders.get(order_id)

    async def submit_order(self, request: OrderRequest) -> Order:
        """Submit and immediately fill order (simulated).

        Paper trading fills market orders immediately. Limit orders
        are filled if price is favorable.
        """
        self._validate_order_request(request)

        # Create order
        order = Order(
            id=uuid4(),
            symbol=request.symbol,
            qty=request.qty,
            side=request.side,
            order_type=request.order_type,
            status=OrderStatus.SUBMITTED,
            limit_price=request.limit_price,
            stop_price=request.stop_price,
            time_in_force=request.time_in_force,
            submitted_at=datetime.utcnow(),
            client_order_id=request.client_order_id,
        )

        self._orders[str(order.id)] = order

        # Get current price
        price = self._prices.get(request.symbol)
        if price is None:
            # Can't fill without price - leave as submitted
            await self._notify_update(order)
            return order

        # Attempt to fill
        should_fill = self._should_fill(order, price)

        if should_fill:
            await self._fill_order(order, price)
        else:
            order.status = OrderStatus.ACCEPTED
            await self._notify_update(order)

        return order

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        order = self._orders.get(order_id)
        if order is None:
            return False

        if order.is_complete:
            return False

        order.status = OrderStatus.CANCELLED
        order.cancelled_at = datetime.utcnow()
        await self._notify_update(order)
        return True

    async def cancel_all_orders(self) -> int:
        """Cancel all pending orders."""
        cancelled = 0
        for order_id, order in self._orders.items():
            if not order.is_complete:
                order.status = OrderStatus.CANCELLED
                order.cancelled_at = datetime.utcnow()
                await self._notify_update(order)
                cancelled += 1
        return cancelled

    async def get_quote(self, symbol: str) -> dict:
        """Get current quote for a symbol."""
        price = self._prices.get(symbol, 0.0)
        spread = price * 0.0002  # 2bps spread
        return {
            "bid": price - spread / 2,
            "ask": price + spread / 2,
            "last": price,
            "volume": 1_000_000,  # Default volume
        }

    async def stream_trade_updates(
        self,
        callback: Callable[[Order], None],
    ) -> None:
        """Register callback for order updates."""
        self._update_callbacks.append(callback)

    def set_price(self, symbol: str, price: float) -> None:
        """Set current price for a symbol (for testing/simulation)."""
        self._prices[symbol] = price
        # Update position if held
        if symbol in self._positions:
            self._positions[symbol].current_price = price

    def set_prices(self, prices: dict[str, float]) -> None:
        """Set prices for multiple symbols."""
        for symbol, price in prices.items():
            self.set_price(symbol, price)

    def _should_fill(self, order: Order, current_price: float) -> bool:
        """Determine if order should fill at current price."""
        if order.order_type == OrderType.MARKET:
            return True

        if order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY:
                return current_price <= order.limit_price
            else:
                return current_price >= order.limit_price

        if order.order_type == OrderType.STOP:
            if order.side == OrderSide.SELL:
                return current_price <= order.stop_price
            else:
                return current_price >= order.stop_price

        # MOC orders wait for close (simulate immediate for now)
        if order.order_type == OrderType.MOC:
            return True

        return False

    async def _fill_order(self, order: Order, market_price: float) -> None:
        """Fill an order with slippage and commission."""
        # Calculate fill price with slippage
        fill_price = self._slippage.get_fill_price(
            market_price,
            order.qty,
            order.side,
        )

        # Calculate commission
        commission = max(
            order.qty * self._commission_per_share,
            self._min_commission,
        )

        # Calculate total slippage
        slippage = abs(fill_price - market_price) * order.qty

        # Update order
        order.filled_qty = order.qty
        order.filled_avg_price = fill_price
        order.filled_at = datetime.utcnow()
        order.status = OrderStatus.FILLED

        # Create trade record
        trade = Trade(
            id=uuid4(),
            order_id=order.id,
            symbol=order.symbol,
            qty=order.qty,
            price=fill_price,
            side=order.side,
            timestamp=datetime.utcnow(),
            commission=commission,
            slippage=slippage,
        )
        self._trades.append(trade)

        # Update position
        self._update_position(order, fill_price)

        # Update cash
        notional = order.qty * fill_price
        if order.side == OrderSide.BUY:
            self._cash -= notional + commission
        else:
            self._cash += notional - commission

        await self._notify_update(order)

    def _update_position(self, order: Order, fill_price: float) -> None:
        """Update position based on filled order."""
        symbol = order.symbol
        current_pos = self._positions.get(symbol)

        if order.side == OrderSide.BUY:
            if current_pos is None:
                # New position
                self._positions[symbol] = Position(
                    symbol=symbol,
                    qty=order.qty,
                    avg_entry_price=fill_price,
                    current_price=fill_price,
                    side="long",
                )
            else:
                # Add to position (average in)
                total_qty = current_pos.qty + order.qty
                avg_price = (
                    current_pos.qty * current_pos.avg_entry_price
                    + order.qty * fill_price
                ) / total_qty
                current_pos.qty = total_qty
                current_pos.avg_entry_price = avg_price
                current_pos.current_price = fill_price

        else:  # SELL
            if current_pos is None:
                # Short position (not supported yet)
                return

            new_qty = current_pos.qty - order.qty
            if new_qty <= 0:
                # Position closed
                del self._positions[symbol]
            else:
                current_pos.qty = new_qty
                current_pos.current_price = fill_price

    async def _notify_update(self, order: Order) -> None:
        """Notify callbacks of order update."""
        for callback in self._update_callbacks:
            try:
                callback(order)
            except Exception:
                pass  # Don't let callback errors break execution

    def get_trades(self) -> list[Trade]:
        """Get all executed trades."""
        return self._trades.copy()

    def reset(self) -> None:
        """Reset paper broker to initial state."""
        self._cash = self._initial_cash
        self._positions.clear()
        self._orders.clear()
        self._trades.clear()
        self._prices.clear()
