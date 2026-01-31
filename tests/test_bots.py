"""Tests for Automated Trading Bots."""

import pytest
from datetime import date, datetime, timedelta, timezone

from src.bots import (
    # Config
    BotType, BotStatus, ExecutionStatus, ScheduleFrequency,
    TradeSide, SignalType, SignalCondition, RebalanceMethod, GridType,
    BotConfig, DCAConfig, RebalanceConfig, SignalBotConfig, GridConfig,
    ScheduleConfig, RiskConfig,
    # Models
    BotOrder, BotExecution, BotPosition, Signal,
    # Bots
    DCABot, RebalanceBot, SignalBot, GridBot,
    # Scheduler & Engine
    BotScheduler, BotEngine,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def dca_config():
    """Create a DCA bot config."""
    return BotConfig(
        bot_id="dca_test",
        name="Test DCA Bot",
        bot_type=BotType.DCA,
        symbols=["SPY", "BND"],
        dca_config=DCAConfig(
            amount_per_period=1000,
            allocations={"SPY": 0.6, "BND": 0.4},
        ),
    )


@pytest.fixture
def rebalance_config():
    """Create a rebalance bot config."""
    return BotConfig(
        bot_id="rebal_test",
        name="Test Rebalance Bot",
        bot_type=BotType.REBALANCE,
        symbols=["SPY", "BND", "GLD"],
        rebalance_config=RebalanceConfig(
            target_allocations={"SPY": 0.5, "BND": 0.3, "GLD": 0.2},
            drift_threshold_pct=5.0,
        ),
    )


@pytest.fixture
def signal_config():
    """Create a signal bot config."""
    return BotConfig(
        bot_id="sig_test",
        name="Test Signal Bot",
        bot_type=BotType.SIGNAL,
        symbols=["AAPL"],
        signal_config=SignalBotConfig(
            signals=[
                {
                    "type": "rsi",
                    "condition": "below",
                    "threshold": 30,
                    "action": "buy",
                },
            ],
            fixed_amount=1000,
        ),
    )


@pytest.fixture
def grid_config():
    """Create a grid bot config."""
    return BotConfig(
        bot_id="grid_test",
        name="Test Grid Bot",
        bot_type=BotType.GRID,
        symbols=["ETH"],
        grid_config=GridConfig(
            symbol="ETH",
            upper_price=2500,
            lower_price=2000,
            num_grids=6,
            total_investment=6000,
        ),
    )


@pytest.fixture
def market_data():
    """Sample market data."""
    return {
        "SPY": {"price": 450.0, "volume": 50000000},
        "BND": {"price": 72.0, "volume": 5000000},
        "GLD": {"price": 180.0, "volume": 2000000},
        "AAPL": {"price": 175.0, "rsi": 25, "volume": 30000000},
        "ETH": {"price": 2200.0, "volume": 1000000},
    }


# =============================================================================
# Test DCA Bot
# =============================================================================

class TestDCABot:
    """Tests for DCA bot."""
    
    def test_create_dca_bot(self, dca_config):
        """Test creating a DCA bot."""
        bot = DCABot(dca_config)
        
        assert bot.bot_id == "dca_test"
        assert bot.name == "Test DCA Bot"
        assert bot.is_active is True
    
    def test_generate_orders(self, dca_config, market_data):
        """Test DCA order generation."""
        bot = DCABot(dca_config)
        orders = bot.generate_orders(market_data)
        
        assert len(orders) == 2
        
        # Check SPY order (60% of $1000)
        spy_order = next(o for o in orders if o.symbol == "SPY")
        assert spy_order.side == TradeSide.BUY
        expected_qty = (1000 * 0.6) / 450
        assert abs(spy_order.quantity - expected_qty) < 0.01
        
        # Check BND order (40% of $1000)
        bnd_order = next(o for o in orders if o.symbol == "BND")
        expected_qty = (1000 * 0.4) / 72
        assert abs(bnd_order.quantity - expected_qty) < 0.1
    
    def test_execute_dca(self, dca_config, market_data):
        """Test DCA execution."""
        bot = DCABot(dca_config)
        execution = bot.execute(market_data)
        
        assert execution.status == ExecutionStatus.SUCCESS
        assert execution.orders_placed == 2
        assert execution.orders_filled == 2
    
    def test_dip_buying(self, dca_config, market_data):
        """Test dip buying enhancement."""
        dca_config.dca_config.increase_on_dip = True
        dca_config.dca_config.dip_threshold_pct = 5.0
        dca_config.dca_config.dip_increase_pct = 50.0
        
        bot = DCABot(dca_config)
        
        # First execution to establish price history
        bot.execute(market_data)
        
        # Simulate price drop
        market_data["SPY"]["price"] = 400.0  # >10% drop
        
        # Check if investment amount increases
        amount = bot.get_next_investment_amount(market_data)
        assert amount >= 1000  # Should increase on dip
    
    def test_allocation_preview(self, dca_config, market_data):
        """Test allocation preview."""
        bot = DCABot(dca_config)
        preview = bot.get_allocation_preview(market_data)
        
        assert len(preview) == 2
        assert preview[0]["symbol"] in ["SPY", "BND"]


# =============================================================================
# Test Rebalance Bot
# =============================================================================

class TestRebalanceBot:
    """Tests for rebalancing bot."""
    
    def test_create_rebalance_bot(self, rebalance_config):
        """Test creating a rebalance bot."""
        bot = RebalanceBot(rebalance_config)
        
        assert bot.bot_id == "rebal_test"
        assert len(bot.rebalance_config.target_allocations) == 3
    
    def test_drift_analysis(self, rebalance_config, market_data):
        """Test drift analysis."""
        bot = RebalanceBot(rebalance_config)
        
        # Set up positions
        positions = [
            BotPosition(bot_id="rebal_test", symbol="SPY", quantity=10, avg_cost=440, current_price=450),
            BotPosition(bot_id="rebal_test", symbol="BND", quantity=50, avg_cost=70, current_price=72),
            BotPosition(bot_id="rebal_test", symbol="GLD", quantity=5, avg_cost=175, current_price=180),
        ]
        bot.set_positions(positions)
        
        drift = bot.get_drift_analysis(market_data)
        
        assert len(drift) == 3
        assert all("drift_pct" in d for d in drift)
    
    def test_no_rebalance_below_threshold(self, rebalance_config, market_data):
        """Test that no orders generated when drift is small."""
        bot = RebalanceBot(rebalance_config)
        
        # Set up positions close to target
        # Total value = ~$10000
        # Target: SPY 50%, BND 30%, GLD 20%
        positions = [
            BotPosition(symbol="SPY", quantity=11.1, avg_cost=450, current_price=450),  # $5000 = 50%
            BotPosition(symbol="BND", quantity=41.7, avg_cost=72, current_price=72),    # $3000 = 30%
            BotPosition(symbol="GLD", quantity=11.1, avg_cost=180, current_price=180),  # $2000 = 20%
        ]
        bot.set_positions(positions)
        
        orders = bot.generate_orders(market_data)
        
        # Drift should be small, no orders needed
        assert len(orders) == 0
    
    def test_rebalance_orders(self, rebalance_config, market_data):
        """Test rebalance order generation."""
        bot = RebalanceBot(rebalance_config)
        
        # Set up imbalanced positions
        positions = [
            BotPosition(symbol="SPY", quantity=20, avg_cost=450, current_price=450),   # $9000 = 60%
            BotPosition(symbol="BND", quantity=30, avg_cost=72, current_price=72),     # $2160 = 14%
            BotPosition(symbol="GLD", quantity=20, avg_cost=180, current_price=180),   # $3600 = 24%
        ]
        bot.set_positions(positions)
        
        orders = bot.generate_orders(market_data)
        
        # Should generate orders due to drift
        assert len(orders) > 0


# =============================================================================
# Test Signal Bot
# =============================================================================

class TestSignalBot:
    """Tests for signal-based bot."""
    
    def test_create_signal_bot(self, signal_config):
        """Test creating a signal bot."""
        bot = SignalBot(signal_config)
        
        assert bot.bot_id == "sig_test"
        assert len(bot._rules) == 1
    
    def test_rsi_signal(self, signal_config, market_data):
        """Test RSI signal detection."""
        bot = SignalBot(signal_config)
        
        # AAPL has RSI=25, which is below threshold of 30
        orders = bot.generate_orders(market_data)
        
        assert len(orders) == 1
        assert orders[0].symbol == "AAPL"
        assert orders[0].side == TradeSide.BUY
    
    def test_no_signal(self, signal_config, market_data):
        """Test no signal when condition not met."""
        bot = SignalBot(signal_config)
        
        # Set RSI above threshold
        market_data["AAPL"]["rsi"] = 50
        
        orders = bot.generate_orders(market_data)
        
        assert len(orders) == 0
    
    def test_signal_history(self, signal_config, market_data):
        """Test signal history tracking."""
        bot = SignalBot(signal_config)
        
        # Generate a signal
        bot.generate_orders(market_data)
        
        history = bot.get_signal_history()
        assert len(history) >= 1


# =============================================================================
# Test Grid Bot
# =============================================================================

class TestGridBot:
    """Tests for grid trading bot."""
    
    def test_create_grid_bot(self, grid_config):
        """Test creating a grid bot."""
        bot = GridBot(grid_config)
        
        assert bot.bot_id == "grid_test"
        assert len(bot._levels) == 6
    
    def test_grid_levels(self, grid_config):
        """Test grid level calculation."""
        bot = GridBot(grid_config)
        levels = bot.get_levels()
        
        assert len(levels) == 6
        assert levels[0]["price"] == 2000
        assert levels[-1]["price"] == 2500
    
    def test_grid_buy_signal(self, grid_config, market_data):
        """Test grid buy at lower levels."""
        bot = GridBot(grid_config)
        
        # Price is 2200, should trigger buys at levels below
        orders = bot.generate_orders(market_data)
        
        # Should have some buy orders at levels below 2200
        buy_orders = [o for o in orders if o.side == TradeSide.BUY]
        assert len(buy_orders) >= 1
    
    def test_grid_status(self, grid_config):
        """Test grid status."""
        bot = GridBot(grid_config)
        status = bot.get_grid_status()
        
        assert status["num_levels"] == 6
        assert status["symbol"] == "ETH"


# =============================================================================
# Test Scheduler
# =============================================================================

class TestBotScheduler:
    """Tests for bot scheduler."""
    
    def test_schedule_bot(self, dca_config):
        """Test scheduling a bot."""
        scheduler = BotScheduler()
        run = scheduler.schedule_bot(dca_config)
        
        assert run is not None
        assert run.bot_id == "dca_test"
        assert run.scheduled_time > datetime.now(timezone.utc)
    
    def test_next_run_calculation(self, dca_config):
        """Test next run calculation."""
        scheduler = BotScheduler()
        
        # Daily schedule
        dca_config.schedule.frequency = ScheduleFrequency.DAILY
        next_run = scheduler.calculate_next_run(dca_config)
        
        assert next_run is not None
        assert next_run > datetime.now(timezone.utc)
    
    def test_weekly_schedule(self, dca_config):
        """Test weekly scheduling."""
        scheduler = BotScheduler()
        
        dca_config.schedule.frequency = ScheduleFrequency.WEEKLY
        dca_config.schedule.day_of_week = 0  # Monday
        
        next_run = scheduler.calculate_next_run(dca_config)
        assert next_run.weekday() == 0  # Monday
    
    def test_get_due_runs(self, dca_config):
        """Test getting due runs."""
        scheduler = BotScheduler()
        scheduler.schedule_bot(dca_config)
        
        # Check for runs due now
        due = scheduler.get_due_runs()
        
        # Probably none due immediately
        assert isinstance(due, list)
    
    def test_trading_hours(self):
        """Test trading hours check."""
        scheduler = BotScheduler()
        
        # This tests the method runs without error
        is_hours = scheduler.is_trading_hours()
        assert isinstance(is_hours, bool)


# =============================================================================
# Test Bot Engine
# =============================================================================

class TestBotEngine:
    """Tests for bot engine."""
    
    def test_create_engine(self):
        """Test creating bot engine."""
        engine = BotEngine()
        
        assert engine is not None
        assert engine.settings.paper_mode is True
    
    def test_create_bot_via_engine(self, dca_config):
        """Test creating a bot through engine."""
        engine = BotEngine()
        bot = engine.create_bot(dca_config)
        
        assert bot is not None
        assert bot.bot_id == "dca_test"
        assert engine.get_bot("dca_test") is not None
    
    def test_run_bot_manually(self, dca_config, market_data):
        """Test manually running a bot."""
        engine = BotEngine()
        bot = engine.create_bot(dca_config)
        
        execution = engine.run_bot(bot.bot_id, market_data)
        
        assert execution is not None
        assert execution.status == ExecutionStatus.SUCCESS
    
    def test_get_summaries(self, dca_config, market_data):
        """Test getting bot summaries."""
        engine = BotEngine()
        engine.create_bot(dca_config)
        engine.run_bot("dca_test", market_data)
        
        summaries = engine.get_summaries()
        
        assert len(summaries) == 1
        assert summaries[0].name == "Test DCA Bot"
        assert summaries[0].total_executions == 1
    
    def test_delete_bot(self, dca_config):
        """Test deleting a bot."""
        engine = BotEngine()
        engine.create_bot(dca_config)
        
        assert engine.delete_bot("dca_test") is True
        assert engine.get_bot("dca_test") is None
    
    def test_emergency_stop(self, dca_config, market_data):
        """Test emergency stop functionality."""
        engine = BotEngine()
        bot = engine.create_bot(dca_config)
        
        engine.emergency_stop()
        
        assert engine.settings.emergency_stop_all is True
        
        # Should not run after emergency stop
        execution = engine.run_bot(bot.bot_id, market_data)
        assert execution is None
        
        # Resume
        engine.resume_all()
        assert engine.settings.emergency_stop_all is False


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests."""
    
    def test_full_dca_workflow(self):
        """Test complete DCA workflow."""
        engine = BotEngine()
        
        # Create bot
        config = BotConfig(
            name="Integration Test DCA",
            bot_type=BotType.DCA,
            symbols=["SPY"],
            dca_config=DCAConfig(
                amount_per_period=500,
                allocations={"SPY": 1.0},
            ),
        )
        bot = engine.create_bot(config)
        
        # Execute
        market_data = {"SPY": {"price": 450.0}}
        execution = engine.run_bot(bot.bot_id, market_data)
        
        assert execution.status == ExecutionStatus.SUCCESS
        assert execution.orders_filled == 1
        
        # Check performance
        perf = engine.get_performance(bot.bot_id)
        assert perf.num_executions == 1
    
    def test_multiple_bots(self):
        """Test running multiple bots."""
        engine = BotEngine()
        
        # Create DCA bot
        dca = BotConfig(
            name="DCA Bot",
            bot_type=BotType.DCA,
            symbols=["SPY"],
            dca_config=DCAConfig(amount_per_period=100),
        )
        engine.create_bot(dca)
        
        # Create signal bot
        signal = BotConfig(
            name="Signal Bot",
            bot_type=BotType.SIGNAL,
            symbols=["AAPL"],
            signal_config=SignalBotConfig(
                signals=[{"type": "rsi", "condition": "below", "threshold": 30, "action": "buy"}],
            ),
        )
        engine.create_bot(signal)
        
        assert len(engine.get_all_bots()) == 2
        
        summaries = engine.get_summaries()
        assert len(summaries) == 2
