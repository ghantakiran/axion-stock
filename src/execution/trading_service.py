"""Trading Service - High-level trading operations integrating all components.

Provides:
- Unified trading interface combining broker, position sizing, rebalancing
- Factor Engine integration for signal-based trading
- Trade journaling and portfolio snapshots
- Paper/Live trading mode management
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.execution.interfaces import BrokerInterface, BrokerError
from src.execution.models import (
    AccountInfo,
    ExecutionResult,
    Order,
    OrderRequest,
    OrderSide,
    OrderType,
    Position,
)
from src.execution.paper_broker import PaperBroker
from src.execution.alpaca_broker import AlpacaBroker
from src.execution.order_manager import OrderManager, PreTradeValidator, ValidationConfig
from src.execution.position_sizer import PositionSizer, SizingConstraints
from src.execution.rebalancer import RebalanceEngine, RebalanceConfig, RebalanceProposal

logger = logging.getLogger(__name__)


@dataclass
class TradingConfig:
    """Configuration for the trading service."""
    # Mode
    paper_trading: bool = True
    initial_cash: float = 100_000

    # Alpaca credentials (for live/paper via Alpaca)
    alpaca_api_key: Optional[str] = None
    alpaca_secret_key: Optional[str] = None
    alpaca_paper: bool = True

    # Position sizing
    max_position_pct: float = 0.15
    max_sector_pct: float = 0.35
    min_position_value: float = 500
    cash_buffer_pct: float = 0.02

    # Rebalancing
    rebalance_frequency: str = "monthly"
    drift_threshold_pct: float = 0.05
    stop_loss_pct: float = 0.15

    # Execution
    use_smart_routing: bool = True
    require_confirmation: bool = True


class TradingService:
    """High-level trading service integrating all execution components.

    Provides a unified interface for:
    - Connecting to paper or live brokerage
    - Executing trades with validation and smart routing
    - Rebalancing based on target weights or factor scores
    - Portfolio management and trade journaling

    Example:
        # Initialize with paper trading
        service = TradingService(TradingConfig(paper_trading=True))
        await service.connect()

        # Get account info
        account = await service.get_account()

        # Execute a single trade
        result = await service.buy("AAPL", dollars=5000)

        # Rebalance to target weights
        proposal = await service.rebalance_to_weights({"AAPL": 0.3, "MSFT": 0.3, "GOOGL": 0.4})
        if proposal:
            results = await service.execute_rebalance(proposal)
    """

    def __init__(
        self,
        config: Optional[TradingConfig] = None,
        sector_map: Optional[dict[str, str]] = None,
    ):
        """Initialize trading service.

        Args:
            config: Trading configuration.
            sector_map: Mapping of symbol -> sector for concentration checks.
        """
        self.config = config or TradingConfig()
        self.sector_map = sector_map or {}

        self._broker: Optional[BrokerInterface] = None
        self._order_manager: Optional[OrderManager] = None
        self._position_sizer: Optional[PositionSizer] = None
        self._rebalance_engine: Optional[RebalanceEngine] = None
        self._journal = None  # Will be set if database session provided

        self._connected = False

    # =========================================================================
    # Connection Management
    # =========================================================================

    async def connect(self) -> bool:
        """Connect to the brokerage.

        Creates appropriate broker based on configuration and connects.

        Returns:
            True if connection successful.
        """
        try:
            # Create broker
            if self.config.paper_trading and not self.config.alpaca_api_key:
                # Pure paper trading (local simulation)
                self._broker = PaperBroker(
                    initial_cash=self.config.initial_cash,
                    commission_per_share=0,
                    simulate_slippage=True,
                )
            elif self.config.alpaca_api_key:
                # Alpaca (paper or live)
                self._broker = AlpacaBroker(
                    api_key=self.config.alpaca_api_key,
                    secret_key=self.config.alpaca_secret_key,
                    paper=self.config.alpaca_paper,
                )
            else:
                raise ValueError("No broker configured. Set paper_trading=True or provide Alpaca credentials.")

            # Connect to broker
            success = await self._broker.connect()
            if not success:
                raise BrokerError("Failed to connect to broker")

            # Initialize components
            self._init_components()

            self._connected = True
            logger.info(
                "Trading service connected. Mode: %s",
                "Paper (Local)" if self.config.paper_trading and not self.config.alpaca_api_key
                else "Alpaca Paper" if self.config.alpaca_paper else "Alpaca Live"
            )

            return True

        except Exception as e:
            logger.error("Failed to connect trading service: %s", e)
            self._connected = False
            return False

    def _init_components(self):
        """Initialize trading components after broker connection."""
        # Position sizer
        constraints = SizingConstraints(
            max_position_pct=self.config.max_position_pct,
            max_sector_pct=self.config.max_sector_pct,
            min_position_value=self.config.min_position_value,
            cash_buffer_pct=self.config.cash_buffer_pct,
        )
        self._position_sizer = PositionSizer(
            constraints=constraints,
            sector_map=self.sector_map,
        )

        # Pre-trade validator
        validation_config = ValidationConfig(
            max_position_pct=self.config.max_position_pct,
            max_sector_pct=self.config.max_sector_pct,
            min_position_value=self.config.min_position_value,
            cash_buffer_pct=self.config.cash_buffer_pct,
        )
        validator = PreTradeValidator(
            config=validation_config,
            sector_map=self.sector_map,
        )

        # Order manager
        self._order_manager = OrderManager(
            broker=self._broker,
            validator=validator,
        )

        # Rebalance engine
        rebalance_config = RebalanceConfig(
            calendar_frequency=self.config.rebalance_frequency,
            drift_threshold_pct=self.config.drift_threshold_pct,
            stop_loss_pct=self.config.stop_loss_pct,
        )
        self._rebalance_engine = RebalanceEngine(
            broker=self._broker,
            sizer=self._position_sizer,
            config=rebalance_config,
        )

    async def disconnect(self):
        """Disconnect from brokerage."""
        if self._broker:
            await self._broker.disconnect()
        self._connected = False
        logger.info("Trading service disconnected")

    def is_connected(self) -> bool:
        """Check if connected to brokerage."""
        return self._connected and self._broker is not None and self._broker.is_connected()

    def _ensure_connected(self):
        """Ensure service is connected."""
        if not self.is_connected():
            raise BrokerError("Trading service not connected. Call connect() first.")

    def set_journal(self, journal):
        """Set trade journal for persistence.

        Args:
            journal: TradeJournal instance.
        """
        self._journal = journal

    # =========================================================================
    # Account & Positions
    # =========================================================================

    async def get_account(self) -> AccountInfo:
        """Get current account information."""
        self._ensure_connected()
        return await self._broker.get_account()

    async def get_positions(self) -> list[Position]:
        """Get all current positions."""
        self._ensure_connected()
        return await self._broker.get_positions()

    async def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for a specific symbol."""
        self._ensure_connected()
        return await self._broker.get_position(symbol)

    async def get_portfolio_summary(self) -> dict:
        """Get comprehensive portfolio summary."""
        self._ensure_connected()

        account = await self.get_account()
        positions = await self.get_positions()

        total_unrealized_pnl = sum(p.unrealized_pnl for p in positions)
        total_cost = sum(p.cost_basis for p in positions)

        return {
            "equity": account.equity,
            "cash": account.cash,
            "buying_power": account.buying_power,
            "portfolio_value": account.portfolio_value,
            "total_unrealized_pnl": total_unrealized_pnl,
            "total_unrealized_pnl_pct": total_unrealized_pnl / total_cost if total_cost > 0 else 0,
            "num_positions": len(positions),
            "positions": [p.to_dict() for p in positions],
            "day_trades_remaining": account.day_trades_remaining,
        }

    # =========================================================================
    # Single Trade Execution
    # =========================================================================

    async def buy(
        self,
        symbol: str,
        shares: Optional[float] = None,
        dollars: Optional[float] = None,
        limit_price: Optional[float] = None,
        trigger: str = "manual",
    ) -> ExecutionResult:
        """Buy shares of a stock.

        Args:
            symbol: Stock symbol.
            shares: Number of shares to buy (mutually exclusive with dollars).
            dollars: Dollar amount to invest (mutually exclusive with shares).
            limit_price: Limit price (uses market order if not specified).
            trigger: What triggered this order.

        Returns:
            ExecutionResult with order details.
        """
        self._ensure_connected()

        if not shares and not dollars:
            raise ValueError("Must specify either shares or dollars")

        if shares and dollars:
            raise ValueError("Cannot specify both shares and dollars")

        # Calculate shares from dollars if needed
        if dollars:
            price = await self._broker.get_last_price(symbol)
            shares = dollars / price

        order = OrderRequest(
            symbol=symbol.upper(),
            qty=shares,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT if limit_price else OrderType.MARKET,
            limit_price=limit_price,
            trigger=trigger,
        )

        result = await self._order_manager.submit_order(
            order,
            use_smart_routing=self.config.use_smart_routing,
        )

        # Log to journal if available
        if self._journal and result.success and result.order:
            try:
                self._journal.log_order(result.order)
            except Exception as e:
                logger.error("Failed to log order to journal: %s", e)

        return result

    async def sell(
        self,
        symbol: str,
        shares: Optional[float] = None,
        percent: Optional[float] = None,
        limit_price: Optional[float] = None,
        trigger: str = "manual",
    ) -> ExecutionResult:
        """Sell shares of a stock.

        Args:
            symbol: Stock symbol.
            shares: Number of shares to sell (mutually exclusive with percent).
            percent: Percentage of position to sell (mutually exclusive with shares).
            limit_price: Limit price (uses market order if not specified).
            trigger: What triggered this order.

        Returns:
            ExecutionResult with order details.
        """
        self._ensure_connected()

        if not shares and not percent:
            raise ValueError("Must specify either shares or percent")

        if shares and percent:
            raise ValueError("Cannot specify both shares and percent")

        # Calculate shares from percent if needed
        if percent:
            position = await self._broker.get_position(symbol)
            if not position:
                return ExecutionResult(
                    success=False,
                    error_message=f"No position in {symbol} to sell",
                )
            shares = position.qty * (percent / 100)

        order = OrderRequest(
            symbol=symbol.upper(),
            qty=shares,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT if limit_price else OrderType.MARKET,
            limit_price=limit_price,
            trigger=trigger,
        )

        result = await self._order_manager.submit_order(
            order,
            use_smart_routing=self.config.use_smart_routing,
        )

        # Log to journal
        if self._journal and result.success and result.order:
            try:
                self._journal.log_order(result.order)
            except Exception as e:
                logger.error("Failed to log order to journal: %s", e)

        return result

    async def close_position(self, symbol: str, trigger: str = "manual") -> ExecutionResult:
        """Close entire position in a stock.

        Args:
            symbol: Stock symbol.
            trigger: What triggered this close.

        Returns:
            ExecutionResult with order details.
        """
        return await self.sell(symbol, percent=100, trigger=trigger)

    async def close_all_positions(self) -> list[ExecutionResult]:
        """Close all positions.

        Returns:
            List of ExecutionResult for each position.
        """
        self._ensure_connected()

        positions = await self.get_positions()
        results = []

        for position in positions:
            result = await self.close_position(position.symbol, trigger="close_all")
            results.append(result)

        return results

    # =========================================================================
    # Rebalancing
    # =========================================================================

    async def calculate_target_weights(
        self,
        factor_scores: dict[str, dict],
        top_n: int = 10,
        sizing_method: str = "score_weighted",
    ) -> dict[str, float]:
        """Calculate target portfolio weights from factor scores.

        Args:
            factor_scores: Dict mapping symbol to {composite: float, ...}.
            top_n: Number of top stocks to include.
            sizing_method: One of 'equal', 'score_weighted', 'volatility'.

        Returns:
            Dict mapping symbol to target weight.
        """
        # Get top N by composite score
        sorted_stocks = sorted(
            factor_scores.items(),
            key=lambda x: x[1].get("composite", 0),
            reverse=True,
        )[:top_n]

        if sizing_method == "equal":
            weight = 1.0 / len(sorted_stocks)
            return {symbol: weight for symbol, _ in sorted_stocks}

        elif sizing_method == "score_weighted":
            scores = {symbol: data.get("composite", 0) for symbol, data in sorted_stocks}
            total = sum(scores.values())
            return {s: score / total for s, score in scores.items()} if total > 0 else {}

        elif sizing_method == "volatility":
            # Would need volatility data - fall back to equal
            weight = 1.0 / len(sorted_stocks)
            return {symbol: weight for symbol, _ in sorted_stocks}

        else:
            raise ValueError(f"Unknown sizing method: {sizing_method}")

    async def preview_rebalance(
        self,
        target_weights: dict[str, float],
        factor_scores: Optional[dict[str, float]] = None,
    ) -> RebalanceProposal:
        """Generate rebalance proposal without executing.

        Args:
            target_weights: Target portfolio weights (sum to 1).
            factor_scores: Optional factor scores for signal filtering.

        Returns:
            RebalanceProposal with proposed trades.
        """
        self._ensure_connected()

        proposal = await self._rebalance_engine.generate_proposal(
            target_weights=target_weights,
            factor_scores=factor_scores,
        )

        return proposal

    async def execute_rebalance(
        self,
        proposal: RebalanceProposal,
    ) -> list[Order]:
        """Execute an approved rebalance proposal.

        Args:
            proposal: Approved RebalanceProposal.

        Returns:
            List of executed Orders.
        """
        self._ensure_connected()

        if not proposal.approved:
            raise ValueError("Proposal must be approved before execution")

        results = await self._rebalance_engine.execute_proposal(proposal)

        # Log all orders to journal
        if self._journal:
            for order in results:
                try:
                    self._journal.log_order(order)
                except Exception as e:
                    logger.error("Failed to log order: %s", e)

        return results

    async def rebalance_to_weights(
        self,
        target_weights: dict[str, float],
        factor_scores: Optional[dict[str, float]] = None,
        auto_approve: bool = False,
    ) -> Optional[RebalanceProposal]:
        """Rebalance portfolio to target weights.

        Args:
            target_weights: Target portfolio weights.
            factor_scores: Optional factor scores for filtering.
            auto_approve: Execute immediately without confirmation.

        Returns:
            RebalanceProposal (executed if auto_approve=True).
        """
        proposal = await self.preview_rebalance(target_weights, factor_scores)

        if auto_approve:
            proposal.approved = True
            await self.execute_rebalance(proposal)

        return proposal

    async def check_rebalance_needed(
        self,
        target_weights: dict[str, float],
    ) -> tuple[bool, str]:
        """Check if rebalancing is needed.

        Args:
            target_weights: Target portfolio weights.

        Returns:
            Tuple of (needs_rebalance, reason).
        """
        self._ensure_connected()

        should_rebal, trigger = await self._rebalance_engine.should_rebalance(target_weights)

        if should_rebal:
            return True, trigger.value
        return False, "no_trigger"

    # =========================================================================
    # Portfolio Snapshots
    # =========================================================================

    async def take_snapshot(self, regime: Optional[str] = None) -> dict:
        """Take a portfolio snapshot.

        Args:
            regime: Current market regime.

        Returns:
            Snapshot data dict.
        """
        self._ensure_connected()

        account = await self.get_account()
        positions = await self.get_positions()

        snapshot_data = {
            "timestamp": datetime.now().isoformat(),
            "cash": account.cash,
            "portfolio_value": account.portfolio_value,
            "equity": account.equity,
            "num_positions": len(positions),
            "regime": regime,
        }

        # Persist to journal if available
        if self._journal:
            try:
                self._journal.take_snapshot(account, positions, regime)
            except Exception as e:
                logger.error("Failed to persist snapshot: %s", e)

        return snapshot_data

    # =========================================================================
    # Order Management
    # =========================================================================

    async def get_orders(self, status: Optional[str] = None, limit: int = 100) -> list[Order]:
        """Get orders from broker.

        Args:
            status: Filter by status ('open', 'closed', 'all').
            limit: Maximum number of orders.

        Returns:
            List of Order objects.
        """
        self._ensure_connected()
        return await self._broker.get_orders(status=status, limit=limit)

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order.

        Args:
            order_id: Order ID to cancel.

        Returns:
            True if cancelled successfully.
        """
        self._ensure_connected()
        return await self._broker.cancel_order(order_id)

    async def cancel_all_orders(self) -> int:
        """Cancel all pending orders.

        Returns:
            Number of orders cancelled.
        """
        self._ensure_connected()
        return await self._broker.cancel_all_orders()
