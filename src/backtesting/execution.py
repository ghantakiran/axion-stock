"""Realistic Execution Modeling.

Implements cost models and fill simulation for realistic backtesting
including commissions, spreads, market impact, and regulatory fees.
"""

import logging
from typing import Optional
import numpy as np

from src.backtesting.config import CostModelConfig, ExecutionConfig, FillModel
from src.backtesting.models import Order, Fill, BarData, OrderSide

logger = logging.getLogger(__name__)


class CostModel:
    """Model real-world trading costs.

    Includes:
    - Commissions (per-share, per-trade, percentage)
    - Spread costs (half-spread)
    - Market impact (linear in participation rate)
    - Regulatory fees (SEC, FINRA TAF)
    """

    def __init__(self, config: Optional[CostModelConfig] = None):
        self.config = config or CostModelConfig()

    def estimate_cost(
        self,
        order: Order,
        bar: BarData,
        fill_price: float,
    ) -> tuple[float, float, float]:
        """Estimate total trading costs.

        Args:
            order: Order being executed.
            bar: Current bar data.
            fill_price: Execution price.

        Returns:
            Tuple of (commission, slippage, fees).
        """
        notional = order.qty * fill_price

        # Commission
        commission = self._calc_commission(order.qty, notional)

        # Spread cost (slippage from mid to execution)
        spread_cost = self._calc_spread_cost(notional)

        # Market impact
        impact_cost = self._calc_market_impact(notional, bar)

        # Regulatory fees (sells only)
        reg_fees = self._calc_regulatory_fees(order.qty, notional, order.side)

        # Total slippage = spread + impact
        slippage = spread_cost + impact_cost

        return commission, slippage, reg_fees

    def _calc_commission(self, qty: int, notional: float) -> float:
        """Calculate commission costs."""
        per_share = qty * self.config.commission_per_share
        per_trade = self.config.commission_per_trade
        pct = notional * self.config.commission_pct

        return per_share + per_trade + pct

    def _calc_spread_cost(self, notional: float) -> float:
        """Calculate half-spread cost."""
        return notional * self.config.min_spread_bps / 10_000

    def _calc_market_impact(self, notional: float, bar: BarData) -> float:
        """Calculate market impact cost.

        Impact is linear in participation rate:
        impact_bps = base_impact * (order_notional / ADV)
        """
        if bar.volume <= 0:
            return 0.0

        adv = bar.volume * bar.close
        participation_rate = notional / adv

        impact_bps = participation_rate * self.config.market_impact_bps_per_pct_adv
        return notional * impact_bps / 10_000

    def _calc_regulatory_fees(
        self,
        qty: int,
        notional: float,
        side: OrderSide,
    ) -> float:
        """Calculate SEC and FINRA fees (sells only)."""
        if side != OrderSide.SELL:
            return 0.0

        sec_fee = notional * self.config.sec_fee_rate
        taf_fee = qty * self.config.taf_fee_per_share

        return sec_fee + taf_fee


class ExecutionSimulator:
    """Simulate order execution with realistic fills.

    Supports multiple fill models:
    - Immediate: Fill at bar close
    - VWAP: Fill at volume-weighted average price
    - Volume participation: Proportional to volume
    - Slippage: Close + random spread
    - Limit: Fill only if price touches limit
    """

    def __init__(
        self,
        execution_config: Optional[ExecutionConfig] = None,
        cost_model: Optional[CostModel] = None,
        seed: int = 42,
    ):
        self.config = execution_config or ExecutionConfig()
        self.cost_model = cost_model or CostModel()
        self.rng = np.random.default_rng(seed)
        self._order_counter = 0

    def generate_order_id(self) -> str:
        """Generate unique order ID."""
        self._order_counter += 1
        return f"BT-{self._order_counter:08d}"

    def simulate_fill(
        self,
        order: Order,
        bar: BarData,
    ) -> Optional[Fill]:
        """Simulate order fill based on fill model.

        Args:
            order: Order to fill.
            bar: Current bar data.

        Returns:
            Fill if order can be executed, None otherwise.
        """
        if order.remaining_qty <= 0:
            return None

        # Check volume constraints
        fill_qty = self._determine_fill_quantity(order, bar)
        if fill_qty <= 0:
            return None

        # Determine fill price based on model
        fill_price = self._determine_fill_price(order, bar)
        if fill_price is None:
            return None

        # Apply random slippage if configured
        fill_price = self._apply_slippage(fill_price, order.side, bar)

        # Calculate costs
        temp_order = Order(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            qty=fill_qty,
            order_type=order.order_type,
        )
        commission, slippage_cost, fees = self.cost_model.estimate_cost(
            temp_order, bar, fill_price
        )

        return Fill(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            qty=fill_qty,
            price=fill_price,
            timestamp=bar.timestamp,
            commission=commission,
            slippage=slippage_cost,
            fees=fees,
        )

    def _determine_fill_quantity(self, order: Order, bar: BarData) -> int:
        """Determine how many shares can be filled."""
        if not self.config.partial_fills:
            # All or nothing
            max_qty = int(bar.volume * self.config.max_participation_rate)
            return order.remaining_qty if order.remaining_qty <= max_qty else 0

        # Allow partial fills up to participation limit
        max_qty = int(bar.volume * self.config.max_participation_rate)
        return min(order.remaining_qty, max_qty)

    def _determine_fill_price(self, order: Order, bar: BarData) -> Optional[float]:
        """Determine fill price based on fill model."""
        model = self.config.fill_model

        if model == FillModel.IMMEDIATE:
            return bar.close

        elif model == FillModel.VWAP:
            return bar.vwap if bar.vwap else bar.typical_price

        elif model == FillModel.VOLUME_PARTICIPATION:
            # Weighted average of bar prices
            return (bar.open + bar.high + bar.low + bar.close) / 4

        elif model == FillModel.SLIPPAGE:
            return bar.close

        elif model == FillModel.LIMIT:
            if order.limit_price is None:
                return bar.close

            # Check if limit was touched
            if order.side == OrderSide.BUY:
                if bar.low <= order.limit_price:
                    return min(order.limit_price, bar.close)
            else:
                if bar.high >= order.limit_price:
                    return max(order.limit_price, bar.close)
            return None  # Limit not touched

        return bar.close

    def _apply_slippage(
        self,
        price: float,
        side: OrderSide,
        bar: BarData,
    ) -> float:
        """Apply random slippage to fill price."""
        if self.config.fill_model != FillModel.SLIPPAGE:
            return price

        # Random slippage within spread
        slippage_pct = self.rng.uniform(0, self.cost_model.config.slippage_bps / 10_000)

        if side == OrderSide.BUY:
            # Buys get filled at higher price
            return price * (1 + slippage_pct)
        else:
            # Sells get filled at lower price
            return price * (1 - slippage_pct)


class SimulatedBroker:
    """Simulated broker for backtesting.

    Manages orders, executions, and position tracking.
    """

    def __init__(
        self,
        execution_config: Optional[ExecutionConfig] = None,
        cost_config: Optional[CostModelConfig] = None,
        seed: int = 42,
    ):
        self.cost_model = CostModel(cost_config)
        self.executor = ExecutionSimulator(execution_config, self.cost_model, seed)

        self.pending_orders: list[Order] = []
        self.filled_orders: list[Order] = []
        self.fills: list[Fill] = []

    def submit_order(self, order: Order) -> str:
        """Submit order for execution."""
        if not order.order_id:
            order.order_id = self.executor.generate_order_id()

        self.pending_orders.append(order)
        logger.debug(f"Order submitted: {order.order_id} {order.side.value} {order.qty} {order.symbol}")

        return order.order_id

    def process_bar(self, bar: BarData) -> list[Fill]:
        """Process pending orders against new bar data.

        Args:
            bar: New bar data.

        Returns:
            List of fills from this bar.
        """
        new_fills = []
        still_pending = []

        for order in self.pending_orders:
            if order.symbol != bar.symbol:
                still_pending.append(order)
                continue

            fill = self.executor.simulate_fill(order, bar)

            if fill:
                # Update order state
                order.filled_qty += fill.qty
                order.avg_fill_price = (
                    (order.avg_fill_price * (order.filled_qty - fill.qty) + fill.price * fill.qty)
                    / order.filled_qty
                )

                if order.remaining_qty == 0:
                    order.status = order.status.FILLED
                    self.filled_orders.append(order)
                else:
                    order.status = order.status.PARTIALLY_FILLED
                    still_pending.append(order)

                self.fills.append(fill)
                new_fills.append(fill)

                logger.debug(
                    f"Fill: {fill.order_id} {fill.qty} {fill.symbol} @ {fill.price:.2f}"
                )
            else:
                still_pending.append(order)

        self.pending_orders = still_pending
        return new_fills

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        for i, order in enumerate(self.pending_orders):
            if order.order_id == order_id:
                order.status = order.status.CANCELLED
                self.pending_orders.pop(i)
                return True
        return False

    def cancel_all_orders(self, symbol: Optional[str] = None):
        """Cancel all pending orders, optionally for a specific symbol."""
        to_cancel = []
        to_keep = []

        for order in self.pending_orders:
            if symbol is None or order.symbol == symbol:
                order.status = order.status.CANCELLED
                to_cancel.append(order)
            else:
                to_keep.append(order)

        self.pending_orders = to_keep
        return len(to_cancel)

    def get_pending_orders(self, symbol: Optional[str] = None) -> list[Order]:
        """Get pending orders."""
        if symbol:
            return [o for o in self.pending_orders if o.symbol == symbol]
        return self.pending_orders.copy()

    def get_total_costs(self) -> dict[str, float]:
        """Get total execution costs."""
        total_commission = sum(f.commission for f in self.fills)
        total_slippage = sum(f.slippage for f in self.fills)
        total_fees = sum(f.fees for f in self.fills)

        return {
            "commission": total_commission,
            "slippage": total_slippage,
            "fees": total_fees,
            "total": total_commission + total_slippage + total_fees,
        }
