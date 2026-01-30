"""Tests for the Execution System (PRD-03).

Tests cover:
- Paper broker functionality
- Order validation
- Position sizing algorithms
- Rebalancing engine
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from src.execution.models import (
    OrderSide,
    OrderType,
    OrderStatus,
    OrderRequest,
    Order,
    Position,
    AccountInfo,
)
from src.execution.paper_broker import PaperBroker
from src.execution.order_manager import (
    PreTradeValidator,
    ValidationConfig,
    SmartOrderRouter,
    OrderManager,
)
from src.execution.position_sizer import PositionSizer, SizingConstraints
from src.execution.rebalancer import RebalanceEngine, RebalanceConfig, RebalanceTrigger


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def paper_broker():
    """Create a paper broker for testing."""
    return PaperBroker(
        initial_cash=100_000,
        commission_per_share=0,
        simulate_slippage=False,
    )


@pytest.fixture
def mock_price_provider():
    """Mock price provider for testing."""
    prices = {
        'AAPL': 180.00,
        'MSFT': 380.00,
        'GOOGL': 140.00,
        'AMZN': 150.00,
        'NVDA': 500.00,
    }
    return lambda symbol: prices.get(symbol, 100.0)


@pytest.fixture
def paper_broker_with_prices(mock_price_provider):
    """Paper broker with mock price provider."""
    return PaperBroker(
        initial_cash=100_000,
        simulate_slippage=False,
        price_provider=mock_price_provider,
    )


# ============================================================================
# Order Model Tests
# ============================================================================

class TestOrderModels:
    """Tests for order data models."""
    
    def test_order_request_creation(self):
        """Test creating an order request."""
        order = OrderRequest(
            symbol='AAPL',
            qty=10,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
        )
        
        assert order.symbol == 'AAPL'
        assert order.qty == 10
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
    
    def test_order_request_string_enum_conversion(self):
        """Test that string enums are converted properly."""
        order = OrderRequest(
            symbol='AAPL',
            qty=10,
            side='buy',
            order_type='limit',
            limit_price=150.00,
        )
        
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.LIMIT
    
    def test_position_pnl_calculation(self):
        """Test position P&L calculations."""
        position = Position(
            symbol='AAPL',
            qty=100,
            avg_entry_price=150.00,
            current_price=180.00,
        )
        
        assert position.market_value == 18000.00
        assert position.cost_basis == 15000.00
        assert position.unrealized_pnl == 3000.00
        assert position.unrealized_pnl_pct == 0.20  # 20%


# ============================================================================
# Paper Broker Tests
# ============================================================================

class TestPaperBroker:
    """Tests for paper broker functionality."""
    
    @pytest.mark.asyncio
    async def test_connect(self, paper_broker):
        """Test broker connection."""
        result = await paper_broker.connect()
        assert result is True
        assert paper_broker.is_connected()
    
    @pytest.mark.asyncio
    async def test_get_account(self, paper_broker):
        """Test getting account information."""
        await paper_broker.connect()
        account = await paper_broker.get_account()
        
        assert account.cash == 100_000
        assert account.equity == 100_000
        assert account.buying_power == 100_000
    
    @pytest.mark.asyncio
    async def test_submit_market_order_buy(self, paper_broker_with_prices):
        """Test submitting a market buy order."""
        broker = paper_broker_with_prices
        await broker.connect()
        
        order = OrderRequest(
            symbol='AAPL',
            qty=10,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
        )
        
        result = await broker.submit_order(order)
        
        assert result.status == OrderStatus.FILLED
        assert result.filled_qty == 10
        assert result.filled_avg_price == 180.00
        
        # Check position was created
        position = await broker.get_position('AAPL')
        assert position is not None
        assert position.qty == 10
        
        # Check cash was reduced
        account = await broker.get_account()
        expected_cash = 100_000 - (10 * 180.00)
        assert account.cash == expected_cash
    
    @pytest.mark.asyncio
    async def test_submit_market_order_sell(self, paper_broker_with_prices):
        """Test submitting a market sell order."""
        broker = paper_broker_with_prices
        await broker.connect()
        
        # First buy some shares
        buy_order = OrderRequest(
            symbol='AAPL',
            qty=10,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
        )
        await broker.submit_order(buy_order)
        
        # Then sell half
        sell_order = OrderRequest(
            symbol='AAPL',
            qty=5,
            side=OrderSide.SELL,
            order_type=OrderType.MARKET,
        )
        result = await broker.submit_order(sell_order)
        
        assert result.status == OrderStatus.FILLED
        assert result.filled_qty == 5
        
        # Check position was reduced
        position = await broker.get_position('AAPL')
        assert position.qty == 5
    
    @pytest.mark.asyncio
    async def test_insufficient_funds(self, paper_broker_with_prices):
        """Test order rejection due to insufficient funds."""
        broker = paper_broker_with_prices
        await broker.connect()
        
        # Try to buy more than we can afford
        order = OrderRequest(
            symbol='NVDA',  # $500 each
            qty=1000,  # $500,000 total
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
        )
        
        from src.execution.interfaces import InsufficientFundsError
        
        with pytest.raises(InsufficientFundsError):
            await broker.submit_order(order)
    
    @pytest.mark.asyncio
    async def test_cancel_order(self, paper_broker_with_prices):
        """Test cancelling a pending order."""
        broker = paper_broker_with_prices
        await broker.connect()
        
        # Submit a limit order that won't fill immediately
        order = OrderRequest(
            symbol='AAPL',
            qty=10,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            limit_price=100.00,  # Below current price of $180
        )
        
        result = await broker.submit_order(order)
        
        # Cancel the order
        cancelled = await broker.cancel_order(result.id)
        assert cancelled is True
        
        # Verify status
        updated_order = await broker.get_order(result.id)
        assert updated_order.status == OrderStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_reset(self, paper_broker_with_prices):
        """Test resetting paper broker to initial state."""
        broker = paper_broker_with_prices
        await broker.connect()
        
        # Make some trades
        order = OrderRequest(
            symbol='AAPL',
            qty=10,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
        )
        await broker.submit_order(order)
        
        # Reset
        broker.reset()
        
        # Verify reset
        account = await broker.get_account()
        assert account.cash == 100_000
        
        positions = await broker.get_positions()
        assert len(positions) == 0


# ============================================================================
# Pre-Trade Validation Tests
# ============================================================================

class TestPreTradeValidator:
    """Tests for pre-trade validation."""
    
    @pytest.mark.asyncio
    async def test_validation_passes(self, paper_broker_with_prices):
        """Test that valid orders pass validation."""
        broker = paper_broker_with_prices
        await broker.connect()
        
        validator = PreTradeValidator()
        
        order = OrderRequest(
            symbol='AAPL',
            qty=10,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
        )
        
        warnings = await validator.validate(order, broker)
        assert isinstance(warnings, list)
    
    @pytest.mark.asyncio
    async def test_insufficient_funds_validation(self, paper_broker_with_prices):
        """Test that insufficient funds are caught."""
        broker = paper_broker_with_prices
        await broker.connect()
        
        validator = PreTradeValidator()
        
        order = OrderRequest(
            symbol='NVDA',
            qty=1000,  # Way more than we can afford
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
        )
        
        from src.execution.interfaces import InsufficientFundsError
        
        with pytest.raises(InsufficientFundsError):
            await validator.validate(order, broker)
    
    @pytest.mark.asyncio
    async def test_position_concentration_warning(self, paper_broker_with_prices):
        """Test warning for position concentration."""
        broker = paper_broker_with_prices
        await broker.connect()
        
        config = ValidationConfig(max_position_pct=0.10)  # 10% max
        validator = PreTradeValidator(config=config)
        
        # Order for 15% of portfolio (15,000 / 100,000)
        order = OrderRequest(
            symbol='AAPL',
            qty=83,  # ~83 * $180 = $14,940 = 15% of $100k
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
        )
        
        warnings = await validator.validate(order, broker)
        assert any('exceeding' in w.lower() for w in warnings)
    
    @pytest.mark.asyncio
    async def test_duplicate_order_detection(self, paper_broker_with_prices):
        """Test detection of duplicate orders."""
        broker = paper_broker_with_prices
        await broker.connect()
        
        validator = PreTradeValidator()
        
        order = OrderRequest(
            symbol='AAPL',
            qty=10,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
        )
        
        # First order should pass
        await validator.validate(order, broker)
        
        # Duplicate should fail
        from src.execution.interfaces import OrderValidationError
        
        with pytest.raises(OrderValidationError, match="Duplicate"):
            await validator.validate(order, broker)


# ============================================================================
# Position Sizer Tests
# ============================================================================

class TestPositionSizer:
    """Tests for position sizing algorithms."""
    
    def test_equal_weight(self):
        """Test equal weight allocation."""
        sizer = PositionSizer()
        result = sizer.equal_weight(100_000, 10)
        
        # 10 positions with 2% cash buffer = 9,800 each
        expected = 100_000 * 0.98 / 10
        assert result['per_position'] == expected
    
    def test_score_weighted(self):
        """Test score-weighted allocation."""
        # Use larger portfolio to avoid hitting max position constraint
        constraints = SizingConstraints(max_position_pct=0.50)
        sizer = PositionSizer(constraints=constraints)
        scores = {
            'AAPL': 0.8,
            'MSFT': 0.6,
            'GOOGL': 0.4,
        }
        
        allocations = sizer.score_weighted(100_000, scores)
        
        # Higher score should get higher allocation
        assert allocations['AAPL'] > allocations['MSFT']
        assert allocations['MSFT'] > allocations['GOOGL']
        
        # Total should not exceed portfolio (minus cash buffer)
        total = sum(allocations.values())
        assert total <= 100_000 * 0.98
    
    def test_volatility_targeted(self):
        """Test volatility-targeted allocation."""
        # Use larger max position to see differences
        constraints = SizingConstraints(max_position_pct=0.50)
        sizer = PositionSizer(constraints=constraints)
        vols = {
            'AAPL': 0.25,  # Higher vol
            'MSFT': 0.20,  # Medium vol
            'GOOGL': 0.30,  # Highest vol
        }
        
        allocations = sizer.volatility_targeted(100_000, 0.15, vols)
        
        # Lower vol should get higher allocation
        assert allocations['MSFT'] > allocations['AAPL']
        assert allocations['AAPL'] > allocations['GOOGL']
    
    def test_kelly_criterion(self):
        """Test Kelly Criterion calculation."""
        sizer = PositionSizer()
        
        # 60% win rate, 2:1 reward:risk
        kelly = sizer.kelly_criterion(
            win_rate=0.60,
            avg_win_pct=0.10,  # 10% average win
            avg_loss_pct=0.05,  # 5% average loss
            kelly_fraction=0.25,  # Quarter Kelly
        )
        
        # Should return a reasonable fraction
        assert 0 < kelly < 0.15
    
    def test_max_position_constraint(self):
        """Test that max position constraint is enforced."""
        constraints = SizingConstraints(max_position_pct=0.10)
        sizer = PositionSizer(constraints=constraints)
        
        # One score much higher than others
        scores = {
            'AAPL': 0.9,
            'MSFT': 0.1,
        }
        
        allocations = sizer.score_weighted(100_000, scores)
        
        # AAPL allocation should be capped at 10%
        assert allocations['AAPL'] <= 100_000 * 0.10 + 1  # Small tolerance
    
    def test_calculate_shares(self):
        """Test converting allocations to share counts."""
        sizer = PositionSizer()
        
        allocations = {
            'AAPL': 18000,  # $18k
            'MSFT': 9500,   # $9.5k
        }
        prices = {
            'AAPL': 180.00,
            'MSFT': 380.00,
        }
        
        shares = sizer.calculate_shares(allocations, prices, allow_fractional=False)
        
        assert shares['AAPL'] == 100  # $18k / $180 = 100 shares
        assert shares['MSFT'] == 25   # $9.5k / $380 = 25 shares


# ============================================================================
# Rebalancing Engine Tests
# ============================================================================

class TestRebalanceEngine:
    """Tests for rebalancing engine."""
    
    @pytest.mark.asyncio
    async def test_generate_proposal(self, paper_broker_with_prices):
        """Test generating a rebalance proposal."""
        broker = paper_broker_with_prices
        await broker.connect()
        
        # First buy some positions
        for symbol in ['AAPL', 'MSFT']:
            order = OrderRequest(
                symbol=symbol,
                qty=10,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
            )
            await broker.submit_order(order)
        
        engine = RebalanceEngine(broker)
        
        # Generate proposal for new target weights
        target_weights = {
            'AAPL': 0.30,  # 30%
            'MSFT': 0.30,  # 30%
            'GOOGL': 0.30, # 30% - new position
        }
        
        proposal = await engine.generate_proposal(target_weights)
        
        assert proposal is not None
        assert len(proposal.proposed_trades) > 0
        assert proposal.trigger == RebalanceTrigger.MANUAL
    
    @pytest.mark.asyncio
    async def test_drift_detection(self, paper_broker_with_prices):
        """Test drift-based rebalance trigger."""
        broker = paper_broker_with_prices
        await broker.connect()
        
        # Buy position
        order = OrderRequest(
            symbol='AAPL',
            qty=100,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
        )
        await broker.submit_order(order)
        
        config = RebalanceConfig(drift_threshold_pct=0.05)  # 5% drift
        engine = RebalanceEngine(broker, config=config)
        
        # Set last rebalance to avoid calendar trigger
        engine._last_rebalance = datetime.now()
        
        # Check drift with different target
        target_weights = {'AAPL': 0.10}  # Only 10% target
        
        should_rebal, trigger = await engine.should_rebalance(target_weights)
        
        # Current is ~18% (18k/100k), target is 10%, drift is 8%
        assert should_rebal is True
        assert trigger == RebalanceTrigger.DRIFT
    
    @pytest.mark.asyncio
    async def test_execute_proposal(self, paper_broker_with_prices):
        """Test executing a rebalance proposal."""
        broker = paper_broker_with_prices
        await broker.connect()
        
        engine = RebalanceEngine(broker)
        
        target_weights = {
            'AAPL': 0.50,
            'MSFT': 0.40,
        }
        
        proposal = await engine.generate_proposal(target_weights)
        proposal.approved = True
        
        results = await engine.execute_proposal(proposal)
        
        assert len(results) > 0
        assert proposal.executed is True
    
    @pytest.mark.asyncio
    async def test_close_position(self, paper_broker_with_prices):
        """Test closing a specific position."""
        broker = paper_broker_with_prices
        await broker.connect()
        
        # Buy position
        order = OrderRequest(
            symbol='AAPL',
            qty=10,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
        )
        await broker.submit_order(order)
        
        engine = RebalanceEngine(broker)
        
        # Close the position
        result = await engine.close_position('AAPL', 'test_close')
        
        assert result is not None
        assert result.status == OrderStatus.FILLED
        
        # Verify position is closed
        position = await broker.get_position('AAPL')
        assert position is None


# ============================================================================
# Order Manager Integration Tests
# ============================================================================

class TestOrderManager:
    """Integration tests for order manager."""
    
    @pytest.mark.asyncio
    async def test_submit_with_validation(self, paper_broker_with_prices):
        """Test submitting order through manager with validation."""
        broker = paper_broker_with_prices
        await broker.connect()
        
        manager = OrderManager(broker)
        
        order = OrderRequest(
            symbol='AAPL',
            qty=10,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
        )
        
        result = await manager.submit_order(order)
        
        assert result.success is True
        assert result.order is not None
        assert result.order.status == OrderStatus.FILLED
    
    @pytest.mark.asyncio
    async def test_submit_fails_validation(self, paper_broker_with_prices):
        """Test that orders failing validation return error."""
        broker = paper_broker_with_prices
        await broker.connect()
        
        manager = OrderManager(broker)
        
        # Order that exceeds buying power
        order = OrderRequest(
            symbol='NVDA',
            qty=1000,
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
        )
        
        result = await manager.submit_order(order)
        
        assert result.success is False
        assert result.error_message is not None
        assert 'insufficient' in result.error_message.lower()


# ============================================================================
# Trading Service Tests
# ============================================================================

class TestTradingService:
    """Tests for the high-level trading service."""

    @pytest.mark.asyncio
    async def test_connect_paper_trading(self):
        """Test connecting to paper trading."""
        from src.execution import TradingService, TradingConfig

        config = TradingConfig(paper_trading=True, initial_cash=50_000)
        service = TradingService(config)

        result = await service.connect()

        assert result is True
        assert service.is_connected()

        await service.disconnect()
        assert not service.is_connected()

    @pytest.mark.asyncio
    async def test_buy_by_dollars(self, mock_price_provider):
        """Test buying by dollar amount."""
        from src.execution import TradingService, TradingConfig

        config = TradingConfig(paper_trading=True, initial_cash=100_000)
        service = TradingService(config)
        await service.connect()

        # Override price provider
        service._broker._price_provider = mock_price_provider

        result = await service.buy("AAPL", dollars=5000)

        assert result.success is True
        assert result.order is not None

        # Check position was created
        position = await service.get_position("AAPL")
        assert position is not None
        assert position.market_value > 0

        await service.disconnect()

    @pytest.mark.asyncio
    async def test_sell_by_percent(self, mock_price_provider):
        """Test selling by percentage."""
        from src.execution import TradingService, TradingConfig

        config = TradingConfig(paper_trading=True, initial_cash=100_000)
        service = TradingService(config)
        await service.connect()

        service._broker._price_provider = mock_price_provider

        # First buy some shares
        await service.buy("MSFT", shares=10)

        # Sell half
        result = await service.sell("MSFT", percent=50)

        assert result.success is True

        # Check position was reduced
        position = await service.get_position("MSFT")
        assert position.qty == 5

        await service.disconnect()

    @pytest.mark.asyncio
    async def test_close_position(self, mock_price_provider):
        """Test closing a position."""
        from src.execution import TradingService, TradingConfig

        config = TradingConfig(paper_trading=True, initial_cash=100_000)
        service = TradingService(config)
        await service.connect()

        service._broker._price_provider = mock_price_provider

        # Buy then close
        await service.buy("GOOGL", shares=20)
        result = await service.close_position("GOOGL")

        assert result.success is True

        # Position should be gone
        position = await service.get_position("GOOGL")
        assert position is None

        await service.disconnect()

    @pytest.mark.asyncio
    async def test_calculate_target_weights(self):
        """Test calculating target weights from factor scores."""
        from src.execution import TradingService, TradingConfig

        config = TradingConfig(paper_trading=True)
        service = TradingService(config)

        factor_scores = {
            "AAPL": {"composite": 0.9},
            "MSFT": {"composite": 0.8},
            "GOOGL": {"composite": 0.7},
            "AMZN": {"composite": 0.6},
            "NVDA": {"composite": 0.5},
        }

        # Equal weight
        weights = await service.calculate_target_weights(factor_scores, top_n=3, sizing_method="equal")
        assert len(weights) == 3
        assert abs(sum(weights.values()) - 1.0) < 0.01

        # Score weighted
        weights = await service.calculate_target_weights(factor_scores, top_n=3, sizing_method="score_weighted")
        assert len(weights) == 3
        assert weights["AAPL"] > weights["MSFT"]  # Higher score = higher weight

    @pytest.mark.asyncio
    async def test_preview_rebalance(self, mock_price_provider):
        """Test generating rebalance preview."""
        from src.execution import TradingService, TradingConfig

        config = TradingConfig(paper_trading=True, initial_cash=100_000)
        service = TradingService(config)
        await service.connect()

        service._broker._price_provider = mock_price_provider

        # Create initial position
        await service.buy("AAPL", dollars=20000)

        # Preview rebalance to new weights
        target_weights = {
            "AAPL": 0.30,
            "MSFT": 0.40,
            "GOOGL": 0.30,
        }

        proposal = await service.preview_rebalance(target_weights)

        assert proposal is not None
        assert len(proposal.proposed_trades) > 0
        assert not proposal.approved
        assert not proposal.executed

        await service.disconnect()

    @pytest.mark.asyncio
    async def test_portfolio_summary(self, mock_price_provider):
        """Test getting portfolio summary."""
        from src.execution import TradingService, TradingConfig

        config = TradingConfig(paper_trading=True, initial_cash=100_000)
        service = TradingService(config)
        await service.connect()

        service._broker._price_provider = mock_price_provider

        # Buy some positions
        await service.buy("AAPL", dollars=10000)
        await service.buy("MSFT", dollars=15000)

        summary = await service.get_portfolio_summary()

        assert "equity" in summary
        assert "cash" in summary
        assert "positions" in summary
        assert summary["num_positions"] == 2

        await service.disconnect()


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
