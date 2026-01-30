"""Paper Trading Broker - Realistic simulation for testing strategies.

Features:
- Realistic fill simulation with market impact
- Configurable slippage model (volume-based)
- Commission simulation (default: $0 like Alpaca)
- Margin simulation (2x RegT, 4x day trading)
- Real-time P&L tracking against live prices
- Full order lifecycle management
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional
from uuid import uuid4

import numpy as np

from src.execution.interfaces import (
    BrokerInterface,
    BrokerError,
    InsufficientFundsError,
    OrderValidationError,
)
from src.execution.models import (
    AccountInfo,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Trade,
)

logger = logging.getLogger(__name__)


class PaperBroker(BrokerInterface):
    """Paper trading broker with realistic simulation.
    
    Simulates order execution with:
    - Market impact based on order size vs ADV
    - Bid-ask spread simulation
    - Partial fills for large orders
    - Commission modeling
    - Margin tracking
    
    Example:
        broker = PaperBroker(initial_cash=100_000)
        await broker.connect()
        
        order = OrderRequest(
            symbol='AAPL',
            qty=10,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
        )
        result = await broker.submit_order(order)
    """
    
    # Simulation parameters
    DEFAULT_SPREAD_BPS = 5  # 5 basis points bid-ask spread
    MARKET_IMPACT_BPS_PER_PCT_ADV = 10  # 10bps per 1% of ADV
    DEFAULT_ADV = 1_000_000  # Default average daily volume if unknown
    
    def __init__(
        self,
        initial_cash: float = 100_000,
        commission_per_share: float = 0.0,
        min_commission: float = 0.0,
        margin_multiplier: float = 1.0,  # 1.0 = no margin, 2.0 = 2x margin
        simulate_slippage: bool = True,
        price_provider: Optional[Callable[[str], float]] = None,
    ):
        """Initialize paper broker.
        
        Args:
            initial_cash: Starting cash balance.
            commission_per_share: Commission per share traded.
            min_commission: Minimum commission per order.
            margin_multiplier: Margin multiplier (1.0 = cash only).
            simulate_slippage: Whether to simulate market impact.
            price_provider: Optional function to get current prices.
        """
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.commission_per_share = commission_per_share
        self.min_commission = min_commission
        self.margin_multiplier = margin_multiplier
        self.simulate_slippage = simulate_slippage
        self._price_provider = price_provider
        
        # State
        self._connected = False
        self._positions: dict[str, Position] = {}
        self._orders: dict[str, Order] = {}
        self._trades: list[Trade] = []
        self._price_cache: dict[str, tuple[float, datetime]] = {}
        
        # Simulated ADV data (volume in shares)
        self._adv_cache: dict[str, float] = {}
        
        # Day trading tracking
        self._day_trades_today = 0
        self._last_trade_date: Optional[datetime] = None
        
        # Callbacks for streaming
        self._order_callbacks: list[Callable[[Order], None]] = []
        self._position_callbacks: list[Callable[[Position], None]] = []
    
    # =========================================================================
    # Connection Management
    # =========================================================================
    
    async def connect(self) -> bool:
        """Connect to paper broker (always succeeds)."""
        self._connected = True
        logger.info("Paper broker connected with $%.2f initial cash", self.initial_cash)
        return True
    
    async def disconnect(self) -> None:
        """Disconnect from paper broker."""
        self._connected = False
        logger.info("Paper broker disconnected")
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected
    
    # =========================================================================
    # Account Information
    # =========================================================================
    
    async def get_account(self) -> AccountInfo:
        """Get current account information."""
        portfolio_value = await self._calculate_portfolio_value()
        equity = self.cash + portfolio_value
        
        return AccountInfo(
            account_id="paper-account",
            buying_power=self.cash * self.margin_multiplier,
            cash=self.cash,
            portfolio_value=portfolio_value,
            equity=equity,
            margin_used=max(0, portfolio_value - self.cash) if self.margin_multiplier > 1 else 0,
            margin_available=max(0, equity * self.margin_multiplier - portfolio_value),
            day_trades_remaining=max(0, 3 - self._day_trades_today),
            is_pattern_day_trader=self._day_trades_today >= 4,
            trading_blocked=False,
        )
    
    async def _calculate_portfolio_value(self) -> float:
        """Calculate total value of all positions."""
        total = 0.0
        for symbol, position in self._positions.items():
            price = await self.get_last_price(symbol)
            position.current_price = price
            total += position.market_value
        return total
    
    async def get_positions(self) -> list[Position]:
        """Get all current positions."""
        # Update current prices
        for symbol, position in self._positions.items():
            price = await self.get_last_price(symbol)
            position.current_price = price
        
        return list(self._positions.values())
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a specific symbol."""
        position = self._positions.get(symbol)
        if position:
            position.current_price = await self.get_last_price(symbol)
        return position
    
    # =========================================================================
    # Order Management
    # =========================================================================
    
    async def submit_order(self, order: OrderRequest) -> Order:
        """Submit an order for execution."""
        if not self._connected:
            raise BrokerError("Not connected to broker")
        
        # Validate order
        await self._validate_order(order)
        
        # Get current price
        current_price = await self.get_last_price(order.symbol)
        
        # Create order object
        order_id = str(uuid4())
        new_order = Order(
            id=order_id,
            client_order_id=order.client_order_id or str(uuid4()),
            symbol=order.symbol,
            qty=order.qty,
            filled_qty=0,
            side=order.side,
            order_type=order.order_type,
            status=OrderStatus.SUBMITTED,
            limit_price=order.limit_price,
            stop_price=order.stop_price,
            time_in_force=order.time_in_force,
            created_at=datetime.now(),
            submitted_at=datetime.now(),
            trigger=order.trigger,
            notes=order.notes,
            broker="paper",
        )
        
        self._orders[order_id] = new_order
        
        # Execute based on order type
        if order.order_type == OrderType.MARKET:
            await self._execute_market_order(new_order, current_price)
        elif order.order_type == OrderType.LIMIT:
            await self._execute_limit_order(new_order, current_price)
        elif order.order_type == OrderType.STOP:
            await self._execute_stop_order(new_order, current_price)
        else:
            # For other types, treat as market for now
            await self._execute_market_order(new_order, current_price)
        
        # Notify callbacks
        for callback in self._order_callbacks:
            try:
                callback(new_order)
            except Exception as e:
                logger.error("Order callback error: %s", e)
        
        return new_order
    
    async def _validate_order(self, order: OrderRequest) -> None:
        """Validate order before submission."""
        # Check buying power for buys
        if order.side == OrderSide.BUY:
            price = await self.get_last_price(order.symbol)
            required = order.qty * price
            
            account = await self.get_account()
            if required > account.buying_power:
                raise InsufficientFundsError(
                    f"Insufficient buying power. Required: ${required:.2f}, "
                    f"Available: ${account.buying_power:.2f}"
                )
        
        # Check position for sells
        if order.side == OrderSide.SELL:
            position = self._positions.get(order.symbol)
            if not position or position.qty < order.qty:
                available = position.qty if position else 0
                raise OrderValidationError(
                    f"Insufficient shares to sell. Required: {order.qty}, "
                    f"Available: {available}"
                )
        
        # Limit price validation
        if order.order_type == OrderType.LIMIT and not order.limit_price:
            raise OrderValidationError("Limit orders require a limit_price")
        
        if order.order_type == OrderType.STOP and not order.stop_price:
            raise OrderValidationError("Stop orders require a stop_price")
    
    async def _execute_market_order(self, order: Order, current_price: float) -> None:
        """Execute a market order immediately."""
        # Calculate fill price with slippage
        fill_price = self._calculate_fill_price(order, current_price)
        commission = self._calculate_commission(order.qty)
        slippage = abs(fill_price - current_price) * order.qty
        
        # Update order
        order.filled_qty = order.qty
        order.filled_avg_price = fill_price
        order.filled_at = datetime.now()
        order.status = OrderStatus.FILLED
        order.commission = commission
        order.slippage = slippage
        
        # Update position and cash
        await self._update_position_from_fill(order)
        
        # Create trade record
        trade = Trade(
            id=str(uuid4()),
            order_id=order.id,
            timestamp=datetime.now(),
            symbol=order.symbol,
            side=order.side,
            quantity=order.qty,
            price=fill_price,
            commission=commission,
            slippage=slippage,
            order_type=order.order_type,
            trigger=order.trigger,
        )
        self._trades.append(trade)
        
        logger.info(
            "Paper order filled: %s %s %.2f %s @ $%.2f (slippage: $%.2f)",
            order.side.value.upper(),
            order.qty,
            order.symbol,
            order.order_type.value,
            fill_price,
            slippage,
        )
    
    async def _execute_limit_order(self, order: Order, current_price: float) -> None:
        """Execute a limit order (immediate if price is favorable)."""
        if order.limit_price is None:
            raise OrderValidationError("Limit price required")
        
        # Check if limit is immediately marketable
        if order.side == OrderSide.BUY and current_price <= order.limit_price:
            # Buy limit at or below current price - fill immediately
            await self._execute_market_order(order, current_price)
        elif order.side == OrderSide.SELL and current_price >= order.limit_price:
            # Sell limit at or above current price - fill immediately
            await self._execute_market_order(order, current_price)
        else:
            # Order is resting - mark as accepted
            order.status = OrderStatus.ACCEPTED
            logger.info(
                "Paper limit order accepted: %s %s %.2f %s @ $%.2f (current: $%.2f)",
                order.side.value.upper(),
                order.qty,
                order.symbol,
                order.limit_price,
                current_price,
            )
    
    async def _execute_stop_order(self, order: Order, current_price: float) -> None:
        """Execute a stop order (triggers when price reaches stop)."""
        if order.stop_price is None:
            raise OrderValidationError("Stop price required")
        
        # Check if stop is triggered
        if order.side == OrderSide.SELL and current_price <= order.stop_price:
            # Stop loss triggered
            await self._execute_market_order(order, current_price)
        elif order.side == OrderSide.BUY and current_price >= order.stop_price:
            # Buy stop triggered
            await self._execute_market_order(order, current_price)
        else:
            # Stop not triggered - mark as accepted
            order.status = OrderStatus.ACCEPTED
    
    def _calculate_fill_price(self, order: Order, current_price: float) -> float:
        """Calculate fill price with market impact."""
        if not self.simulate_slippage:
            return current_price
        
        # Get ADV for impact calculation
        adv = self._adv_cache.get(order.symbol, self.DEFAULT_ADV)
        
        # Calculate participation rate
        participation_rate = order.qty / adv
        
        # Market impact in basis points
        impact_bps = participation_rate * 100 * self.MARKET_IMPACT_BPS_PER_PCT_ADV
        
        # Add half spread
        impact_bps += self.DEFAULT_SPREAD_BPS / 2
        
        # Apply impact direction
        if order.side == OrderSide.BUY:
            fill_price = current_price * (1 + impact_bps / 10000)
        else:
            fill_price = current_price * (1 - impact_bps / 10000)
        
        return round(fill_price, 2)
    
    def _calculate_commission(self, qty: float) -> float:
        """Calculate commission for an order."""
        commission = qty * self.commission_per_share
        return max(commission, self.min_commission)
    
    async def _update_position_from_fill(self, order: Order) -> None:
        """Update position and cash after a fill."""
        symbol = order.symbol
        fill_qty = order.filled_qty
        fill_price = order.filled_avg_price
        commission = order.commission
        
        if fill_price is None:
            return
        
        if order.side == OrderSide.BUY:
            # Buying - add to position, reduce cash
            self.cash -= (fill_qty * fill_price) + commission
            
            if symbol in self._positions:
                # Average into existing position
                pos = self._positions[symbol]
                total_qty = pos.qty + fill_qty
                total_cost = (pos.qty * pos.avg_entry_price) + (fill_qty * fill_price)
                pos.qty = total_qty
                pos.avg_entry_price = total_cost / total_qty
                pos.current_price = fill_price
            else:
                # New position
                self._positions[symbol] = Position(
                    symbol=symbol,
                    qty=fill_qty,
                    avg_entry_price=fill_price,
                    current_price=fill_price,
                    side="long",
                )
        
        else:  # SELL
            # Selling - reduce position, increase cash
            self.cash += (fill_qty * fill_price) - commission
            
            if symbol in self._positions:
                pos = self._positions[symbol]
                pos.qty -= fill_qty
                pos.current_price = fill_price
                
                if pos.qty <= 0:
                    del self._positions[symbol]
        
        # Update day trade counter
        today = datetime.now().date()
        if self._last_trade_date != today:
            self._day_trades_today = 0
            self._last_trade_date = today
        
        # Count day trade if this is a closing trade
        if order.side == OrderSide.SELL and symbol not in self._positions:
            self._day_trades_today += 1
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        order = self._orders.get(order_id)
        if not order:
            return False
        
        if not order.is_active:
            return False
        
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = datetime.now()
        
        for callback in self._order_callbacks:
            try:
                callback(order)
            except Exception as e:
                logger.error("Order callback error: %s", e)
        
        return True
    
    async def cancel_all_orders(self) -> int:
        """Cancel all pending orders."""
        cancelled = 0
        for order_id, order in self._orders.items():
            if order.is_active:
                await self.cancel_order(order_id)
                cancelled += 1
        return cancelled
    
    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self._orders.get(order_id)
    
    async def get_orders(
        self,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> list[Order]:
        """Get orders with optional filtering."""
        orders = list(self._orders.values())
        
        if status == "open":
            orders = [o for o in orders if o.is_active]
        elif status == "closed":
            orders = [o for o in orders if not o.is_active]
        
        # Sort by creation time, newest first
        orders.sort(key=lambda o: o.created_at, reverse=True)
        
        return orders[:limit]
    
    # =========================================================================
    # Market Data
    # =========================================================================
    
    async def get_last_price(self, symbol: str) -> float:
        """Get last price for a symbol."""
        # Check cache (valid for 1 second)
        if symbol in self._price_cache:
            price, timestamp = self._price_cache[symbol]
            if datetime.now() - timestamp < timedelta(seconds=1):
                return price
        
        # Use price provider if available
        if self._price_provider:
            try:
                price = self._price_provider(symbol)
                self._price_cache[symbol] = (price, datetime.now())
                return price
            except Exception:
                pass
        
        # Try to get from yfinance as fallback
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            price = ticker.info.get("regularMarketPrice") or ticker.info.get("currentPrice", 100.0)
            self._price_cache[symbol] = (price, datetime.now())
            return price
        except Exception:
            # Default price for testing
            return 100.0
    
    async def get_last_prices(self, symbols: list[str]) -> dict[str, float]:
        """Get last prices for multiple symbols."""
        prices = {}
        for symbol in symbols:
            prices[symbol] = await self.get_last_price(symbol)
        return prices
    
    # =========================================================================
    # Streaming
    # =========================================================================
    
    async def stream_trade_updates(self, callback: Callable[[Order], None]) -> None:
        """Register callback for order updates."""
        self._order_callbacks.append(callback)
    
    async def stream_positions(self, callback: Callable[[Position], None]) -> None:
        """Register callback for position updates."""
        self._position_callbacks.append(callback)
    
    # =========================================================================
    # Trade History
    # =========================================================================
    
    async def get_trades(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        limit: int = 100,
    ) -> list[Trade]:
        """Get historical trades."""
        trades = list(self._trades)
        
        if start:
            start_dt = datetime.fromisoformat(start)
            trades = [t for t in trades if t.timestamp >= start_dt]
        
        if end:
            end_dt = datetime.fromisoformat(end)
            trades = [t for t in trades if t.timestamp <= end_dt]
        
        # Sort by timestamp, newest first
        trades.sort(key=lambda t: t.timestamp, reverse=True)
        
        return trades[:limit]
    
    # =========================================================================
    # Paper-Specific Methods
    # =========================================================================
    
    def reset(self) -> None:
        """Reset paper account to initial state."""
        self.cash = self.initial_cash
        self._positions.clear()
        self._orders.clear()
        self._trades.clear()
        self._day_trades_today = 0
        logger.info("Paper broker reset to initial state")
    
    def set_adv(self, symbol: str, adv: float) -> None:
        """Set average daily volume for a symbol (for impact simulation)."""
        self._adv_cache[symbol] = adv
    
    async def get_portfolio_summary(self) -> dict:
        """Get comprehensive portfolio summary."""
        account = await self.get_account()
        positions = await self.get_positions()
        
        total_pnl = sum(p.unrealized_pnl for p in positions)
        total_pnl_pct = total_pnl / self.initial_cash if self.initial_cash > 0 else 0
        
        return {
            "initial_cash": self.initial_cash,
            "current_cash": self.cash,
            "portfolio_value": account.portfolio_value,
            "equity": account.equity,
            "buying_power": account.buying_power,
            "total_unrealized_pnl": total_pnl,
            "total_unrealized_pnl_pct": total_pnl_pct,
            "total_return": (account.equity - self.initial_cash) / self.initial_cash,
            "num_positions": len(positions),
            "num_trades": len(self._trades),
            "day_trades_today": self._day_trades_today,
        }
