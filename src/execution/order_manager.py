"""Order Management System - Pre-trade validation and smart order routing.

Features:
- Pre-trade validation (buying power, position limits, PDT rules)
- Smart order routing (TWAP, limit placement)
- Duplicate order detection
- Rate limiting
- Market hours awareness
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, time
from typing import Optional

from src.execution.interfaces import (
    BrokerInterface,
    BrokerError,
    InsufficientFundsError,
    OrderValidationError,
    PositionLimitError,
    MarketClosedError,
)
from src.execution.models import (
    AccountInfo,
    ExecutionResult,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    Trade,
)

logger = logging.getLogger(__name__)


@dataclass
class ValidationConfig:
    """Configuration for pre-trade validation."""
    max_position_pct: float = 0.25  # Max 25% of portfolio in single position
    max_sector_pct: float = 0.40  # Max 40% in single sector
    min_position_value: float = 500  # Minimum $500 position
    cash_buffer_pct: float = 0.02  # Keep 2% cash minimum
    max_orders_per_minute: int = 10  # Rate limit
    duplicate_window_seconds: int = 60  # Duplicate detection window
    require_market_hours: bool = True  # Warn on extended hours


class PreTradeValidator:
    """Validates orders before submission.
    
    Checks:
    1. Buying power sufficiency
    2. Position concentration limits
    3. Sector concentration limits (if sector map provided)
    4. PDT rule compliance
    5. Duplicate order detection
    6. Rate limiting
    7. Market hours
    """
    
    # US Market hours (Eastern Time)
    MARKET_OPEN = time(9, 30)
    MARKET_CLOSE = time(16, 0)
    
    def __init__(
        self,
        config: Optional[ValidationConfig] = None,
        sector_map: Optional[dict[str, str]] = None,
    ):
        """Initialize validator.
        
        Args:
            config: Validation configuration.
            sector_map: Optional mapping of symbol -> sector for sector checks.
        """
        self.config = config or ValidationConfig()
        self.sector_map = sector_map or {}
        
        # Order tracking for duplicate/rate limit detection
        self._recent_orders: list[tuple[datetime, OrderRequest]] = []
    
    async def validate(
        self,
        order: OrderRequest,
        broker: BrokerInterface,
    ) -> list[str]:
        """Validate an order before submission.
        
        Args:
            order: The order to validate.
            broker: Broker instance for account/position data.
            
        Returns:
            List of warning messages (empty if all good).
            
        Raises:
            OrderValidationError: If order fails critical validation.
            InsufficientFundsError: If insufficient buying power.
            PositionLimitError: If position limits exceeded.
        """
        warnings = []
        
        account = await broker.get_account()
        positions = await broker.get_positions()
        price = await broker.get_last_price(order.symbol)
        
        order_value = order.qty * price
        
        # 1. Buying power check (for buys)
        if order.side == OrderSide.BUY:
            self._check_buying_power(order_value, account)
        
        # 2. Position check (for sells)
        if order.side == OrderSide.SELL:
            self._check_sell_position(order, positions)
        
        # 3. Position concentration check
        warning = self._check_position_concentration(
            order, order_value, positions, account
        )
        if warning:
            warnings.append(warning)
        
        # 4. Sector concentration check
        warning = self._check_sector_concentration(
            order, order_value, positions, account
        )
        if warning:
            warnings.append(warning)
        
        # 5. PDT rule check
        warning = self._check_pdt_rule(order, account, positions)
        if warning:
            warnings.append(warning)
        
        # 6. Duplicate order check
        if self._is_duplicate_order(order):
            raise OrderValidationError(
                f"Duplicate order detected for {order.symbol} within "
                f"{self.config.duplicate_window_seconds} seconds"
            )
        
        # 7. Rate limit check
        if self._is_rate_limited():
            raise OrderValidationError(
                f"Rate limit exceeded: max {self.config.max_orders_per_minute} orders/minute"
            )
        
        # 8. Market hours check
        warning = self._check_market_hours(order)
        if warning:
            warnings.append(warning)
        
        # 9. Minimum position value check
        if order_value < self.config.min_position_value:
            warnings.append(
                f"Order value ${order_value:.2f} is below minimum "
                f"${self.config.min_position_value:.2f}"
            )
        
        # Record this order for duplicate/rate tracking
        self._recent_orders.append((datetime.now(), order))
        self._cleanup_recent_orders()
        
        return warnings
    
    def _check_buying_power(self, order_value: float, account: AccountInfo) -> None:
        """Check if sufficient buying power exists."""
        # Account for cash buffer
        available = account.buying_power * (1 - self.config.cash_buffer_pct)
        
        if order_value > available:
            raise InsufficientFundsError(
                f"Insufficient buying power. Required: ${order_value:,.2f}, "
                f"Available: ${available:,.2f}"
            )
    
    def _check_sell_position(self, order: OrderRequest, positions: list[Position]) -> None:
        """Check if we have enough shares to sell."""
        position = next((p for p in positions if p.symbol == order.symbol), None)
        
        if not position:
            raise OrderValidationError(
                f"No position in {order.symbol} to sell"
            )
        
        if position.qty < order.qty:
            raise OrderValidationError(
                f"Insufficient shares. Have: {position.qty}, Selling: {order.qty}"
            )
    
    def _check_position_concentration(
        self,
        order: OrderRequest,
        order_value: float,
        positions: list[Position],
        account: AccountInfo,
    ) -> Optional[str]:
        """Check position concentration limits."""
        if order.side != OrderSide.BUY:
            return None
        
        # Calculate resulting position value
        current_position = next(
            (p for p in positions if p.symbol == order.symbol), None
        )
        current_value = current_position.market_value if current_position else 0
        resulting_value = current_value + order_value
        
        max_allowed = account.equity * self.config.max_position_pct
        
        if resulting_value > max_allowed:
            return (
                f"Position in {order.symbol} would be {resulting_value/account.equity:.1%} "
                f"of portfolio, exceeding {self.config.max_position_pct:.0%} limit"
            )
        
        return None
    
    def _check_sector_concentration(
        self,
        order: OrderRequest,
        order_value: float,
        positions: list[Position],
        account: AccountInfo,
    ) -> Optional[str]:
        """Check sector concentration limits."""
        if order.side != OrderSide.BUY:
            return None
        
        if not self.sector_map:
            return None
        
        order_sector = self.sector_map.get(order.symbol)
        if not order_sector:
            return None
        
        # Calculate sector exposure
        sector_value = 0
        for pos in positions:
            pos_sector = self.sector_map.get(pos.symbol)
            if pos_sector == order_sector:
                sector_value += pos.market_value
        
        resulting_sector_value = sector_value + order_value
        max_allowed = account.equity * self.config.max_sector_pct
        
        if resulting_sector_value > max_allowed:
            return (
                f"Sector '{order_sector}' would be "
                f"{resulting_sector_value/account.equity:.1%} of portfolio, "
                f"exceeding {self.config.max_sector_pct:.0%} limit"
            )
        
        return None
    
    def _check_pdt_rule(
        self,
        order: OrderRequest,
        account: AccountInfo,
        positions: list[Position],
    ) -> Optional[str]:
        """Check Pattern Day Trader rule compliance."""
        # PDT only applies to accounts under $25k
        if account.equity >= 25000:
            return None
        
        # Only relevant for day trades (selling same-day buy)
        if order.side != OrderSide.SELL:
            return None
        
        if account.day_trades_remaining <= 0:
            return (
                "Warning: Account has no day trades remaining. "
                "Selling today could trigger PDT restriction."
            )
        
        return None
    
    def _is_duplicate_order(self, order: OrderRequest) -> bool:
        """Check if this appears to be a duplicate order."""
        cutoff = datetime.now() - timedelta(seconds=self.config.duplicate_window_seconds)
        
        for timestamp, prev_order in self._recent_orders:
            if timestamp < cutoff:
                continue
            
            if (prev_order.symbol == order.symbol and
                prev_order.side == order.side and
                prev_order.qty == order.qty):
                return True
        
        return False
    
    def _is_rate_limited(self) -> bool:
        """Check if we've exceeded the rate limit."""
        cutoff = datetime.now() - timedelta(minutes=1)
        recent_count = sum(1 for ts, _ in self._recent_orders if ts >= cutoff)
        return recent_count >= self.config.max_orders_per_minute
    
    def _check_market_hours(self, order: OrderRequest) -> Optional[str]:
        """Check if market is open."""
        if not self.config.require_market_hours:
            return None
        
        if order.extended_hours:
            return None
        
        now = datetime.now()
        current_time = now.time()
        
        # Simple weekday check (not accounting for holidays)
        if now.weekday() >= 5:  # Saturday or Sunday
            return "Warning: Market is closed on weekends"
        
        if current_time < self.MARKET_OPEN or current_time > self.MARKET_CLOSE:
            return (
                f"Warning: Order submitted outside market hours "
                f"({self.MARKET_OPEN} - {self.MARKET_CLOSE} ET)"
            )
        
        return None
    
    def _cleanup_recent_orders(self) -> None:
        """Clean up old order records."""
        cutoff = datetime.now() - timedelta(minutes=5)
        self._recent_orders = [
            (ts, order) for ts, order in self._recent_orders
            if ts >= cutoff
        ]


class SmartOrderRouter:
    """Smart order routing for minimizing market impact.
    
    Features:
    - TWAP (Time-Weighted Average Price) execution for large orders
    - Adaptive limit pricing
    - Order splitting based on ADV
    """
    
    # If order is > this % of ADV, use TWAP
    ADV_THRESHOLD_PCT = 0.01  # 1% of ADV
    
    # TWAP parameters
    TWAP_SLICES = 5
    TWAP_INTERVAL_SECONDS = 30
    
    def __init__(
        self,
        broker: BrokerInterface,
        adv_data: Optional[dict[str, float]] = None,
    ):
        """Initialize smart router.
        
        Args:
            broker: Broker instance for order submission.
            adv_data: Optional average daily volume data by symbol.
        """
        self.broker = broker
        self.adv_data = adv_data or {}
    
    async def execute(self, order: OrderRequest) -> ExecutionResult:
        """Execute an order with smart routing.
        
        Args:
            order: Order to execute.
            
        Returns:
            ExecutionResult with execution details.
        """
        start_time = datetime.now()
        expected_price = await self.broker.get_last_price(order.symbol)
        
        # Check if order needs TWAP execution
        adv = self.adv_data.get(order.symbol, 1_000_000)
        participation_rate = order.qty / adv
        
        if participation_rate > self.ADV_THRESHOLD_PCT:
            logger.info(
                "Large order (%.2f%% of ADV), using TWAP execution",
                participation_rate * 100
            )
            result = await self._twap_execution(order, expected_price)
        elif order.order_type == OrderType.MARKET:
            # For market orders, consider using limit with buffer
            result = await self._smart_market_execution(order, expected_price)
        else:
            # Direct submission for limit orders
            result = await self._direct_execution(order, expected_price)
        
        # Calculate execution time
        result.execution_time_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        return result
    
    async def _direct_execution(
        self,
        order: OrderRequest,
        expected_price: float,
    ) -> ExecutionResult:
        """Direct order submission."""
        try:
            executed_order = await self.broker.submit_order(order)
            
            return ExecutionResult(
                success=executed_order.status in [OrderStatus.FILLED, OrderStatus.ACCEPTED, OrderStatus.SUBMITTED],
                order=executed_order,
                expected_price=expected_price,
                actual_avg_price=executed_order.filled_avg_price,
                total_slippage=executed_order.slippage,
                total_commission=executed_order.commission,
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                error_message=str(e),
                expected_price=expected_price,
            )
    
    async def _smart_market_execution(
        self,
        order: OrderRequest,
        expected_price: float,
    ) -> ExecutionResult:
        """Convert market order to aggressive limit for better fills."""
        # Set limit at slight premium/discount to ensure fill
        buffer_pct = 0.001  # 10bps buffer
        
        if order.side == OrderSide.BUY:
            limit_price = expected_price * (1 + buffer_pct)
        else:
            limit_price = expected_price * (1 - buffer_pct)
        
        # Create limit order
        limit_order = OrderRequest(
            symbol=order.symbol,
            qty=order.qty,
            side=order.side,
            order_type=OrderType.LIMIT,
            limit_price=round(limit_price, 2),
            time_in_force=order.time_in_force,
            trigger=order.trigger,
            notes=order.notes,
        )
        
        return await self._direct_execution(limit_order, expected_price)
    
    async def _twap_execution(
        self,
        order: OrderRequest,
        expected_price: float,
    ) -> ExecutionResult:
        """Execute order using TWAP strategy."""
        slice_qty = order.qty / self.TWAP_SLICES
        
        executed_orders = []
        total_filled_qty = 0
        total_cost = 0
        total_commission = 0
        
        for i in range(self.TWAP_SLICES):
            # Adjust last slice for any rounding
            if i == self.TWAP_SLICES - 1:
                remaining = order.qty - total_filled_qty
                if remaining <= 0:
                    break
                slice_qty = remaining
            
            # Create slice order
            slice_order = OrderRequest(
                symbol=order.symbol,
                qty=slice_qty,
                side=order.side,
                order_type=OrderType.MARKET,
                trigger=f"twap_slice_{i+1}",
            )
            
            try:
                result = await self.broker.submit_order(slice_order)
                executed_orders.append(result)
                
                if result.is_filled and result.filled_avg_price:
                    total_filled_qty += result.filled_qty
                    total_cost += result.filled_qty * result.filled_avg_price
                    total_commission += result.commission
                
            except Exception as e:
                logger.error("TWAP slice %d failed: %s", i + 1, e)
            
            # Wait between slices (except for last)
            if i < self.TWAP_SLICES - 1:
                await asyncio.sleep(self.TWAP_INTERVAL_SECONDS)
        
        # Calculate aggregate results
        avg_price = total_cost / total_filled_qty if total_filled_qty > 0 else None
        
        return ExecutionResult(
            success=total_filled_qty > 0,
            order=executed_orders[-1] if executed_orders else None,
            trades=[],
            expected_price=expected_price,
            actual_avg_price=avg_price,
            total_slippage=abs(avg_price - expected_price) * total_filled_qty if avg_price else 0,
            total_commission=total_commission,
        )


class OrderManager:
    """High-level order management combining validation and routing.
    
    Example:
        manager = OrderManager(broker, validator, router)
        
        order = OrderRequest(symbol='AAPL', qty=100, side=OrderSide.BUY)
        result = await manager.submit_order(order)
        
        if result.success:
            print(f"Filled at ${result.actual_avg_price:.2f}")
        else:
            print(f"Failed: {result.error_message}")
    """
    
    def __init__(
        self,
        broker: BrokerInterface,
        validator: Optional[PreTradeValidator] = None,
        router: Optional[SmartOrderRouter] = None,
    ):
        """Initialize order manager.
        
        Args:
            broker: Broker instance for execution.
            validator: Pre-trade validator (created if not provided).
            router: Smart order router (created if not provided).
        """
        self.broker = broker
        self.validator = validator or PreTradeValidator()
        self.router = router or SmartOrderRouter(broker)
    
    async def submit_order(
        self,
        order: OrderRequest,
        skip_validation: bool = False,
        use_smart_routing: bool = True,
    ) -> ExecutionResult:
        """Submit an order with validation and smart routing.
        
        Args:
            order: Order to submit.
            skip_validation: Skip pre-trade validation (not recommended).
            use_smart_routing: Use smart order routing.
            
        Returns:
            ExecutionResult with full execution details.
        """
        warnings = []
        
        # Pre-trade validation
        if not skip_validation:
            try:
                warnings = await self.validator.validate(order, self.broker)
                for warning in warnings:
                    logger.warning("Order validation warning: %s", warning)
            except (OrderValidationError, InsufficientFundsError, PositionLimitError) as e:
                return ExecutionResult(
                    success=False,
                    error_message=str(e),
                )
        
        # Execute order
        if use_smart_routing:
            result = await self.router.execute(order)
        else:
            try:
                executed_order = await self.broker.submit_order(order)
                result = ExecutionResult(
                    success=executed_order.status != OrderStatus.REJECTED,
                    order=executed_order,
                )
            except Exception as e:
                result = ExecutionResult(
                    success=False,
                    error_message=str(e),
                )
        
        return result
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        return await self.broker.cancel_order(order_id)
    
    async def cancel_all_orders(self) -> int:
        """Cancel all pending orders."""
        return await self.broker.cancel_all_orders()
    
    async def get_order_status(self, order_id: str) -> Optional[Order]:
        """Get current status of an order."""
        return await self.broker.get_order(order_id)
