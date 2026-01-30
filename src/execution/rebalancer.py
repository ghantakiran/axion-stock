"""Rebalancing Engine - Automated portfolio rebalancing.

Features:
- Calendar-based rebalancing (monthly, weekly)
- Drift-based rebalancing (threshold triggers)
- Signal-based rebalancing (factor score changes)
- Trade generation with sell-first logic
- Preview before execution
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from src.execution.interfaces import BrokerInterface
from src.execution.models import (
    Order,
    OrderRequest,
    OrderSide,
    OrderType,
    Position,
)
from src.execution.position_sizer import PositionSizer, SizingConstraints

logger = logging.getLogger(__name__)


class RebalanceTrigger(Enum):
    """Types of rebalance triggers."""
    CALENDAR = "calendar"       # Scheduled rebalance
    DRIFT = "drift"            # Position drift threshold exceeded
    SIGNAL = "signal"          # Factor score signal
    STOP_LOSS = "stop_loss"    # Position stop-loss triggered
    MANUAL = "manual"          # User-initiated


@dataclass
class RebalanceConfig:
    """Configuration for rebalancing."""
    # Calendar triggers
    calendar_frequency: str = "monthly"  # 'daily', 'weekly', 'monthly'
    
    # Drift triggers
    drift_threshold_pct: float = 0.05  # 5% drift triggers rebalance
    
    # Signal triggers
    min_score_threshold: float = 0.30  # Exit if score drops below 30th percentile
    entry_score_threshold: float = 0.90  # Enter if score rises above 90th percentile
    
    # Stop-loss
    stop_loss_pct: float = 0.15  # 15% stop-loss
    
    # Trade sizing
    min_trade_value: float = 100  # Minimum trade size
    limit_buffer_pct: float = 0.001  # 10bps buffer for limit orders
    
    # Execution
    use_limit_orders: bool = True
    max_trades_per_rebalance: int = 20


@dataclass
class RebalanceProposal:
    """Proposed rebalance before execution."""
    trigger: RebalanceTrigger
    timestamp: datetime
    current_positions: dict[str, Position]
    target_allocations: dict[str, float]
    proposed_trades: list[OrderRequest]
    
    # Analysis
    total_buy_value: float = 0.0
    total_sell_value: float = 0.0
    estimated_commission: float = 0.0
    estimated_slippage: float = 0.0
    
    # Status
    approved: bool = False
    executed: bool = False
    execution_results: list[Order] = field(default_factory=list)
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        buy_trades = [t for t in self.proposed_trades if t.side == OrderSide.BUY]
        sell_trades = [t for t in self.proposed_trades if t.side == OrderSide.SELL]
        
        return f"""
Rebalance Proposal ({self.trigger.value})
Generated: {self.timestamp.strftime('%Y-%m-%d %H:%M')}

Trades:
  Sells: {len(sell_trades)} orders, ${self.total_sell_value:,.2f}
  Buys:  {len(buy_trades)} orders, ${self.total_buy_value:,.2f}
  Net:   ${self.total_buy_value - self.total_sell_value:+,.2f}

Estimated Costs:
  Commission: ${self.estimated_commission:.2f}
  Slippage:   ${self.estimated_slippage:.2f}
  
Status: {'APPROVED' if self.approved else 'PENDING APPROVAL'}
        """.strip()


class RebalanceEngine:
    """Engine for automated portfolio rebalancing.
    
    Example:
        engine = RebalanceEngine(broker, sizer)
        
        # Check if rebalance needed
        if await engine.should_rebalance():
            # Generate proposal
            proposal = await engine.generate_proposal(target_weights)
            
            # Preview trades
            print(proposal.summary())
            
            # Execute if approved
            proposal.approved = True
            results = await engine.execute_proposal(proposal)
    """
    
    def __init__(
        self,
        broker: BrokerInterface,
        sizer: Optional[PositionSizer] = None,
        config: Optional[RebalanceConfig] = None,
    ):
        """Initialize rebalance engine.
        
        Args:
            broker: Broker for execution and position data.
            sizer: Position sizer for allocation calculations.
            config: Rebalancing configuration.
        """
        self.broker = broker
        self.sizer = sizer or PositionSizer()
        self.config = config or RebalanceConfig()
        
        self._last_rebalance: Optional[datetime] = None
        self._entry_prices: dict[str, float] = {}
    
    async def should_rebalance(
        self,
        target_weights: dict[str, float],
        trigger: Optional[RebalanceTrigger] = None,
    ) -> tuple[bool, RebalanceTrigger]:
        """Check if rebalancing is needed.
        
        Args:
            target_weights: Target portfolio weights.
            trigger: Specific trigger to check (or check all if None).
            
        Returns:
            Tuple of (should_rebalance, trigger_type).
        """
        # Check calendar trigger
        if trigger is None or trigger == RebalanceTrigger.CALENDAR:
            if self._check_calendar_trigger():
                return True, RebalanceTrigger.CALENDAR
        
        # Check drift trigger
        if trigger is None or trigger == RebalanceTrigger.DRIFT:
            if await self._check_drift_trigger(target_weights):
                return True, RebalanceTrigger.DRIFT
        
        # Check stop-loss trigger
        if trigger is None or trigger == RebalanceTrigger.STOP_LOSS:
            symbols = await self._check_stop_loss_trigger()
            if symbols:
                return True, RebalanceTrigger.STOP_LOSS
        
        return False, RebalanceTrigger.MANUAL
    
    def _check_calendar_trigger(self) -> bool:
        """Check if calendar-based rebalance is due."""
        if self._last_rebalance is None:
            return True
        
        now = datetime.now()
        
        if self.config.calendar_frequency == "daily":
            return now.date() > self._last_rebalance.date()
        elif self.config.calendar_frequency == "weekly":
            days_since = (now - self._last_rebalance).days
            return days_since >= 7
        elif self.config.calendar_frequency == "monthly":
            return (now.year > self._last_rebalance.year or
                    now.month > self._last_rebalance.month)
        
        return False
    
    async def _check_drift_trigger(self, target_weights: dict[str, float]) -> bool:
        """Check if any position has drifted beyond threshold."""
        account = await self.broker.get_account()
        positions = await self.broker.get_positions()
        
        portfolio_value = account.equity
        if portfolio_value <= 0:
            return False
        
        # Calculate current weights
        current_weights = {
            p.symbol: p.market_value / portfolio_value
            for p in positions
        }
        
        # Check for drift
        all_symbols = set(target_weights.keys()) | set(current_weights.keys())
        
        for symbol in all_symbols:
            current = current_weights.get(symbol, 0)
            target = target_weights.get(symbol, 0)
            drift = abs(current - target)
            
            if drift > self.config.drift_threshold_pct:
                logger.info(
                    "Drift detected for %s: current=%.2f%%, target=%.2f%%, drift=%.2f%%",
                    symbol, current * 100, target * 100, drift * 100
                )
                return True
        
        return False
    
    async def _check_stop_loss_trigger(self) -> list[str]:
        """Check if any positions have hit stop-loss."""
        positions = await self.broker.get_positions()
        triggered = []
        
        for position in positions:
            entry_price = self._entry_prices.get(position.symbol, position.avg_entry_price)
            loss_pct = (entry_price - position.current_price) / entry_price
            
            if loss_pct > self.config.stop_loss_pct:
                logger.warning(
                    "Stop-loss triggered for %s: entry=$%.2f, current=$%.2f, loss=%.1f%%",
                    position.symbol, entry_price, position.current_price, loss_pct * 100
                )
                triggered.append(position.symbol)
        
        return triggered
    
    async def generate_proposal(
        self,
        target_weights: dict[str, float],
        trigger: RebalanceTrigger = RebalanceTrigger.MANUAL,
        factor_scores: Optional[dict[str, float]] = None,
    ) -> RebalanceProposal:
        """Generate a rebalance proposal.
        
        Args:
            target_weights: Target portfolio weights (sum to 1).
            trigger: What triggered this rebalance.
            factor_scores: Optional factor scores for signal-based entries/exits.
            
        Returns:
            RebalanceProposal with proposed trades.
        """
        account = await self.broker.get_account()
        positions = await self.broker.get_positions()
        
        portfolio_value = account.equity
        
        # Get target allocations in dollars
        target_allocations = self.sizer.from_target_weights(
            portfolio_value, target_weights
        )
        
        # Get current prices
        all_symbols = list(set(target_weights.keys()) | {p.symbol for p in positions})
        prices = await self.broker.get_last_prices(all_symbols)
        
        # Build current positions dict
        current_positions = {p.symbol: p for p in positions}
        
        # Generate trades
        trades = await self._generate_trades(
            current_positions,
            target_allocations,
            prices,
            factor_scores,
        )
        
        # Calculate totals
        buy_value = sum(
            t.qty * prices.get(t.symbol, 0)
            for t in trades if t.side == OrderSide.BUY
        )
        sell_value = sum(
            t.qty * prices.get(t.symbol, 0)
            for t in trades if t.side == OrderSide.SELL
        )
        
        # Estimate costs (rough estimate)
        estimated_slippage = (buy_value + sell_value) * 0.0005  # 5bps
        
        return RebalanceProposal(
            trigger=trigger,
            timestamp=datetime.now(),
            current_positions=current_positions,
            target_allocations=target_allocations,
            proposed_trades=trades,
            total_buy_value=buy_value,
            total_sell_value=sell_value,
            estimated_commission=0,  # Commission-free with Alpaca
            estimated_slippage=estimated_slippage,
        )
    
    async def _generate_trades(
        self,
        current_positions: dict[str, Position],
        target_allocations: dict[str, float],
        prices: dict[str, float],
        factor_scores: Optional[dict[str, float]] = None,
    ) -> list[OrderRequest]:
        """Generate list of trades to move to target allocation.
        
        Args:
            current_positions: Current positions by symbol.
            target_allocations: Target dollar allocation by symbol.
            prices: Current prices by symbol.
            factor_scores: Optional factor scores for filtering.
            
        Returns:
            List of OrderRequest objects (sells first, then buys).
        """
        trades = []
        sells = []
        buys = []
        
        all_symbols = set(target_allocations.keys()) | set(current_positions.keys())
        
        for symbol in all_symbols:
            current_value = 0
            current_qty = 0
            
            if symbol in current_positions:
                pos = current_positions[symbol]
                current_value = pos.market_value
                current_qty = pos.qty
            
            target_value = target_allocations.get(symbol, 0)
            price = prices.get(symbol, 0)
            
            if price <= 0:
                continue
            
            delta_value = target_value - current_value
            
            # Skip small trades
            if abs(delta_value) < self.config.min_trade_value:
                continue
            
            # Check factor score for exits
            if factor_scores and symbol in factor_scores:
                score = factor_scores[symbol]
                if score < self.config.min_score_threshold and current_value > 0:
                    # Force exit - score too low
                    delta_value = -current_value
                    logger.info(
                        "Signal exit for %s: score=%.2f below threshold %.2f",
                        symbol, score, self.config.min_score_threshold
                    )
            
            # Calculate shares to trade
            qty = abs(delta_value) / price
            
            # Create order
            if delta_value < 0:
                # Sell
                qty = min(qty, current_qty)  # Can't sell more than we have
                if qty > 0:
                    order = self._create_order(symbol, qty, OrderSide.SELL, price)
                    sells.append(order)
            else:
                # Buy
                # Check score threshold for new entries
                if factor_scores and symbol not in current_positions:
                    score = factor_scores.get(symbol, 0)
                    if score < self.config.entry_score_threshold:
                        continue  # Don't enter if score not high enough
                
                order = self._create_order(symbol, qty, OrderSide.BUY, price)
                buys.append(order)
        
        # Sells first (free up cash), then buys
        trades = sells + buys
        
        # Limit number of trades
        if len(trades) > self.config.max_trades_per_rebalance:
            # Prioritize larger trades
            trades.sort(key=lambda t: t.qty * prices.get(t.symbol, 0), reverse=True)
            trades = trades[:self.config.max_trades_per_rebalance]
        
        return trades
    
    def _create_order(
        self,
        symbol: str,
        qty: float,
        side: OrderSide,
        price: float,
    ) -> OrderRequest:
        """Create an order request."""
        if self.config.use_limit_orders:
            # Set limit with buffer
            if side == OrderSide.BUY:
                limit_price = price * (1 + self.config.limit_buffer_pct)
            else:
                limit_price = price * (1 - self.config.limit_buffer_pct)
            
            return OrderRequest(
                symbol=symbol,
                qty=round(qty, 4),  # Allow fractional shares
                side=side,
                order_type=OrderType.LIMIT,
                limit_price=round(limit_price, 2),
                trigger="rebalance",
            )
        else:
            return OrderRequest(
                symbol=symbol,
                qty=round(qty, 4),
                side=side,
                order_type=OrderType.MARKET,
                trigger="rebalance",
            )
    
    async def execute_proposal(
        self,
        proposal: RebalanceProposal,
    ) -> list[Order]:
        """Execute an approved rebalance proposal.
        
        Args:
            proposal: Approved RebalanceProposal.
            
        Returns:
            List of executed Order objects.
        """
        if not proposal.approved:
            raise ValueError("Proposal must be approved before execution")
        
        if proposal.executed:
            raise ValueError("Proposal has already been executed")
        
        results = []
        
        for trade in proposal.proposed_trades:
            try:
                order = await self.broker.submit_order(trade)
                results.append(order)
                
                # Track entry prices for stop-loss
                if trade.side == OrderSide.BUY and order.filled_avg_price:
                    self._entry_prices[trade.symbol] = order.filled_avg_price
                
                logger.info(
                    "Rebalance trade executed: %s %s %.4f %s @ $%.2f",
                    trade.side.value.upper(),
                    trade.qty,
                    trade.symbol,
                    order.status.value,
                    order.filled_avg_price or trade.limit_price or 0,
                )
                
            except Exception as e:
                logger.error("Failed to execute trade for %s: %s", trade.symbol, e)
        
        proposal.executed = True
        proposal.execution_results = results
        self._last_rebalance = datetime.now()
        
        return results
    
    async def close_position(
        self,
        symbol: str,
        reason: str = "manual",
    ) -> Optional[Order]:
        """Close a specific position.
        
        Args:
            symbol: Symbol to close.
            reason: Reason for closing.
            
        Returns:
            Executed Order or None if no position.
        """
        position = await self.broker.get_position(symbol)
        if not position:
            return None
        
        order = OrderRequest(
            symbol=symbol,
            qty=position.qty,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
            trigger=reason,
        )
        
        result = await self.broker.submit_order(order)
        
        # Remove from entry prices
        self._entry_prices.pop(symbol, None)
        
        return result
    
    async def close_all_positions(self) -> list[Order]:
        """Close all positions.
        
        Returns:
            List of executed Orders.
        """
        positions = await self.broker.get_positions()
        results = []
        
        for position in positions:
            try:
                order = await self.close_position(position.symbol, "close_all")
                if order:
                    results.append(order)
            except Exception as e:
                logger.error("Failed to close %s: %s", position.symbol, e)
        
        return results
