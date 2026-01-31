"""Base Bot Implementation.

Abstract base class for all trading bots.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Protocol
import logging

from src.bots.config import (
    BotConfig,
    BotType,
    BotStatus,
    ExecutionStatus,
    TradeSide,
    OrderType,
    RiskConfig,
)
from src.bots.models import (
    BotExecution,
    BotOrder,
    BotPosition,
    BotPerformance,
)

logger = logging.getLogger(__name__)


class BrokerInterface(Protocol):
    """Protocol for broker implementations."""
    
    def get_quote(self, symbol: str) -> dict:
        """Get current quote for symbol."""
        ...
    
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str,
        limit_price: Optional[float] = None,
    ) -> dict:
        """Place an order."""
        ...
    
    def get_position(self, symbol: str) -> Optional[dict]:
        """Get current position."""
        ...
    
    def get_account(self) -> dict:
        """Get account information."""
        ...


class BaseBot(ABC):
    """Abstract base class for trading bots.
    
    All bot types inherit from this class and implement
    the generate_orders method.
    """
    
    def __init__(
        self,
        config: BotConfig,
        broker: Optional[BrokerInterface] = None,
    ):
        self.config = config
        self.broker = broker
        self.status = BotStatus.ACTIVE if config.enabled else BotStatus.PAUSED
        
        # State
        self._positions: dict[str, BotPosition] = {}
        self._executions: list[BotExecution] = []
        self._daily_trades: int = 0
        self._daily_loss: float = 0.0
        self._last_reset_date: Optional[datetime] = None
        
        # Callbacks
        self._on_order_filled: Optional[Callable[[BotOrder], None]] = None
        self._on_execution_complete: Optional[Callable[[BotExecution], None]] = None
    
    @property
    def bot_id(self) -> str:
        return self.config.bot_id
    
    @property
    def name(self) -> str:
        return self.config.name
    
    @property
    def bot_type(self) -> BotType:
        return self.config.bot_type
    
    @property
    def is_active(self) -> bool:
        return self.status == BotStatus.ACTIVE
    
    @abstractmethod
    def generate_orders(self, market_data: dict[str, dict]) -> list[BotOrder]:
        """Generate orders based on bot strategy.
        
        Args:
            market_data: Dict of symbol -> price data.
            
        Returns:
            List of orders to execute.
        """
        pass
    
    def execute(
        self,
        market_data: Optional[dict[str, dict]] = None,
        trigger_reason: str = "scheduled",
    ) -> BotExecution:
        """Execute the bot strategy.
        
        Args:
            market_data: Market data (fetched if not provided).
            trigger_reason: Why this execution was triggered.
            
        Returns:
            BotExecution record.
        """
        execution = BotExecution(
            bot_id=self.bot_id,
            bot_name=self.name,
            bot_type=self.bot_type,
            scheduled_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            trigger_reason=trigger_reason,
            status=ExecutionStatus.RUNNING,
        )
        
        try:
            # Reset daily counters if needed
            self._reset_daily_counters()
            
            # Pre-execution checks
            if not self._pre_execution_checks(execution):
                execution.status = ExecutionStatus.SKIPPED
                execution.completed_at = datetime.now(timezone.utc)
                self._executions.append(execution)
                return execution
            
            # Fetch market data if not provided
            if market_data is None:
                market_data = self._fetch_market_data()
            
            # Generate orders
            orders = self.generate_orders(market_data)
            
            if not orders:
                execution.status = ExecutionStatus.SUCCESS
                execution.warnings.append("No orders generated")
                execution.completed_at = datetime.now(timezone.utc)
                self._executions.append(execution)
                return execution
            
            # Apply risk checks to orders
            orders = self._apply_risk_checks(orders, market_data)
            
            # Execute orders
            for order in orders:
                filled_order = self._execute_order(order)
                execution.add_order(filled_order)
                
                if filled_order.is_filled:
                    self._update_position(filled_order)
                    self._daily_trades += 1
            
            # Determine final status
            if all(o.is_filled for o in execution.orders):
                execution.status = ExecutionStatus.SUCCESS
            elif any(o.is_filled for o in execution.orders):
                execution.status = ExecutionStatus.PARTIAL
            else:
                execution.status = ExecutionStatus.FAILED
            
            execution.completed_at = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"Bot execution error: {e}")
            execution.status = ExecutionStatus.FAILED
            execution.error_message = str(e)
            execution.completed_at = datetime.now(timezone.utc)
        
        self._executions.append(execution)
        
        # Fire callback
        if self._on_execution_complete:
            self._on_execution_complete(execution)
        
        return execution
    
    def _pre_execution_checks(self, execution: BotExecution) -> bool:
        """Run pre-execution checks.
        
        Returns:
            True if execution should proceed.
        """
        if not self.is_active:
            execution.error_message = "Bot is not active"
            return False
        
        risk = self.config.risk
        
        # Daily trade limit
        if self._daily_trades >= risk.max_daily_trades:
            execution.error_message = f"Daily trade limit reached ({risk.max_daily_trades})"
            return False
        
        # Daily loss limit
        if self._daily_loss >= risk.max_daily_loss:
            execution.error_message = f"Daily loss limit reached (${risk.max_daily_loss})"
            return False
        
        return True
    
    def _apply_risk_checks(
        self,
        orders: list[BotOrder],
        market_data: dict[str, dict],
    ) -> list[BotOrder]:
        """Apply risk controls to orders.
        
        Args:
            orders: Orders to check.
            market_data: Current market data.
            
        Returns:
            Filtered/modified orders.
        """
        risk = self.config.risk
        approved_orders = []
        
        for order in orders:
            # Get price
            price = market_data.get(order.symbol, {}).get("price", 0)
            if price <= 0:
                continue
            
            order_value = order.quantity * price
            
            # Max position size
            if order_value > risk.max_position_size:
                # Reduce to max
                order.quantity = risk.max_position_size / price
                order_value = risk.max_position_size
            
            # Skip tiny orders
            if order_value < 1.0:
                continue
            
            approved_orders.append(order)
        
        return approved_orders
    
    def _execute_order(self, order: BotOrder) -> BotOrder:
        """Execute a single order.
        
        Args:
            order: Order to execute.
            
        Returns:
            Updated order with fill details.
        """
        if self.broker is None:
            # Paper/simulation mode
            return self._simulate_fill(order)
        
        try:
            result = self.broker.place_order(
                symbol=order.symbol,
                side=order.side.value,
                quantity=order.quantity,
                order_type=order.order_type.value,
                limit_price=order.limit_price,
            )
            
            order.filled_quantity = result.get("filled_qty", order.quantity)
            order.filled_price = result.get("filled_price", order.limit_price)
            order.status = result.get("status", "filled")
            order.filled_at = datetime.now(timezone.utc)
            
        except Exception as e:
            logger.error(f"Order execution error: {e}")
            order.status = "rejected"
            order.error_message = str(e)
        
        # Fire callback
        if self._on_order_filled and order.is_filled:
            self._on_order_filled(order)
        
        return order
    
    def _simulate_fill(self, order: BotOrder) -> BotOrder:
        """Simulate order fill for paper trading.
        
        Args:
            order: Order to simulate.
            
        Returns:
            Filled order.
        """
        # Assume market orders fill at limit or slightly worse
        if order.order_type == OrderType.MARKET:
            slippage = 0.001  # 0.1% slippage
            if order.side == TradeSide.BUY:
                order.filled_price = (order.limit_price or 100) * (1 + slippage)
            else:
                order.filled_price = (order.limit_price or 100) * (1 - slippage)
        else:
            order.filled_price = order.limit_price
        
        order.filled_quantity = order.quantity
        order.status = "filled"
        order.filled_at = datetime.now(timezone.utc)
        
        return order
    
    def _update_position(self, order: BotOrder) -> None:
        """Update position after fill.
        
        Args:
            order: Filled order.
        """
        symbol = order.symbol
        
        if symbol not in self._positions:
            self._positions[symbol] = BotPosition(
                bot_id=self.bot_id,
                symbol=symbol,
            )
        
        pos = self._positions[symbol]
        
        if order.side == TradeSide.BUY:
            # Add to position
            total_cost = (pos.quantity * pos.avg_cost) + order.fill_value
            pos.quantity += order.filled_quantity
            pos.avg_cost = total_cost / pos.quantity if pos.quantity > 0 else 0
        else:
            # Reduce position
            if order.filled_quantity >= pos.quantity:
                # Close position
                pos.quantity = 0
                pos.avg_cost = 0
            else:
                pos.quantity -= order.filled_quantity
        
        pos.current_price = order.filled_price or pos.current_price
        pos.last_updated = datetime.now(timezone.utc)
    
    def _fetch_market_data(self) -> dict[str, dict]:
        """Fetch market data for bot symbols.
        
        Returns:
            Dict of symbol -> price data.
        """
        market_data = {}
        
        if self.broker is None:
            # Return dummy data for paper mode
            for symbol in self.config.symbols:
                market_data[symbol] = {"price": 100.0, "volume": 1000000}
            return market_data
        
        for symbol in self.config.symbols:
            try:
                quote = self.broker.get_quote(symbol)
                market_data[symbol] = {
                    "price": quote.get("price", 0),
                    "bid": quote.get("bid", 0),
                    "ask": quote.get("ask", 0),
                    "volume": quote.get("volume", 0),
                }
            except Exception as e:
                logger.warning(f"Failed to fetch quote for {symbol}: {e}")
        
        return market_data
    
    def _reset_daily_counters(self) -> None:
        """Reset daily counters if new day."""
        now = datetime.now(timezone.utc)
        
        if (self._last_reset_date is None or 
            self._last_reset_date.date() != now.date()):
            self._daily_trades = 0
            self._daily_loss = 0.0
            self._last_reset_date = now
    
    def get_positions(self) -> list[BotPosition]:
        """Get all bot positions."""
        return list(self._positions.values())
    
    def get_position(self, symbol: str) -> Optional[BotPosition]:
        """Get position for a symbol."""
        return self._positions.get(symbol)
    
    def get_executions(self, limit: int = 50) -> list[BotExecution]:
        """Get recent executions."""
        return sorted(
            self._executions,
            key=lambda e: e.created_at,
            reverse=True
        )[:limit]
    
    def get_performance(self) -> BotPerformance:
        """Calculate bot performance metrics."""
        perf = BotPerformance(bot_id=self.bot_id)
        
        # Sum up from positions
        for pos in self._positions.values():
            perf.total_invested += pos.cost_basis
            perf.current_value += pos.market_value
            perf.unrealized_pnl += pos.unrealized_pnl
        
        # Sum up from executions
        perf.num_executions = len(self._executions)
        for ex in self._executions:
            perf.num_trades += ex.orders_placed
            if ex.status == ExecutionStatus.SUCCESS:
                perf.num_successful += 1
            elif ex.status == ExecutionStatus.FAILED:
                perf.num_failed += 1
            perf.realized_pnl += ex.realized_pnl
        
        return perf
    
    def pause(self) -> None:
        """Pause the bot."""
        self.status = BotStatus.PAUSED
        logger.info(f"Bot {self.name} paused")
    
    def resume(self) -> None:
        """Resume the bot."""
        self.status = BotStatus.ACTIVE
        logger.info(f"Bot {self.name} resumed")
    
    def stop(self) -> None:
        """Stop the bot."""
        self.status = BotStatus.STOPPED
        logger.info(f"Bot {self.name} stopped")
    
    def on_order_filled(self, callback: Callable[[BotOrder], None]) -> None:
        """Register order filled callback."""
        self._on_order_filled = callback
    
    def on_execution_complete(self, callback: Callable[[BotExecution], None]) -> None:
        """Register execution complete callback."""
        self._on_execution_complete = callback
