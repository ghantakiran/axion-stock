"""Tests for Professional Backtesting Engine.

Comprehensive test suite covering:
- Configuration
- Cost and execution models
- Portfolio management
- Backtest engine
- Walk-forward optimization
- Monte Carlo analysis
- Reporting
"""

import pytest
import numpy as np
import pandas as pd
from datetime import date, datetime, timedelta

from src.backtesting.config import (
    BacktestConfig,
    CostModelConfig,
    ExecutionConfig,
    RiskConfig,
    WalkForwardConfig,
    MonteCarloConfig,
    BarType,
    RebalanceFrequency,
    FillModel,
)
from src.backtesting.models import (
    BarData,
    MarketEvent,
    Signal,
    Order,
    Fill,
    Position,
    Trade,
    OrderSide,
    OrderType,
    OrderStatus,
    BacktestMetrics,
    BacktestResult,
)
from src.backtesting.execution import (
    CostModel,
    ExecutionSimulator,
    SimulatedBroker,
)
from src.backtesting.portfolio import SimulatedPortfolio
from src.backtesting.engine import (
    BacktestEngine,
    BacktestRiskManager,
    HistoricalDataHandler,
)
from src.backtesting.optimization import (
    WalkForwardOptimizer,
    MonteCarloAnalyzer,
)
from src.backtesting.reporting import (
    TearSheetGenerator,
    StrategyComparator,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_bar():
    """Create sample bar data."""
    return BarData(
        symbol="AAPL",
        timestamp=datetime(2024, 1, 15, 16, 0),
        open=185.0,
        high=187.5,
        low=184.0,
        close=186.5,
        volume=50_000_000,
    )


@pytest.fixture
def sample_order():
    """Create sample order."""
    return Order(
        order_id="TEST-001",
        symbol="AAPL",
        side=OrderSide.BUY,
        qty=100,
        order_type=OrderType.MARKET,
    )


@pytest.fixture
def sample_trades():
    """Create sample trades for testing."""
    trades = []
    base_date = datetime(2024, 1, 1)
    
    for i in range(100):
        # Mix of winning and losing trades
        is_win = i % 3 != 0  # 66% win rate
        pnl = np.random.uniform(100, 500) if is_win else np.random.uniform(-300, -50)
        
        trades.append(Trade(
            symbol=f"STOCK{i % 10}",
            entry_date=base_date + timedelta(days=i * 3),
            exit_date=base_date + timedelta(days=i * 3 + np.random.randint(5, 30)),
            side=OrderSide.BUY,
            entry_price=100.0,
            exit_price=100.0 + pnl / 100,
            qty=100,
            pnl=pnl,
            pnl_pct=pnl / 10000,
            hold_days=np.random.randint(5, 30),
        ))
    
    return trades


@pytest.fixture
def price_data():
    """Create sample price data."""
    dates = pd.date_range("2020-01-01", "2024-12-31", freq="B")
    np.random.seed(42)
    
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    data = {}
    
    for symbol in symbols:
        # Generate random walk prices
        returns = np.random.normal(0.0005, 0.02, len(dates))
        prices = 100 * np.cumprod(1 + returns)
        data[symbol] = prices
    
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def backtest_config():
    """Create sample backtest config."""
    return BacktestConfig(
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        initial_capital=100_000,
        rebalance_frequency=RebalanceFrequency.MONTHLY,
    )


# =============================================================================
# Configuration Tests
# =============================================================================


class TestBacktestConfig:
    """Test backtest configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = BacktestConfig()
        
        assert config.initial_capital == 100_000
        assert config.bar_type == BarType.DAILY
        assert config.currency == "USD"
        assert config.rebalance_frequency == RebalanceFrequency.MONTHLY
        assert config.adjust_for_splits is True
        assert config.benchmark == "SPY"
    
    def test_cost_model_config(self):
        """Test cost model configuration."""
        config = CostModelConfig(
            commission_per_share=0.005,
            min_spread_bps=2.0,
            market_impact_bps_per_pct_adv=15.0,
        )
        
        assert config.commission_per_share == 0.005
        assert config.min_spread_bps == 2.0
        
        # Test fixed cost calculation
        fixed = config.total_fixed_cost(100)
        assert fixed == 0.5  # 100 * 0.005
    
    def test_risk_config(self):
        """Test risk configuration."""
        config = RiskConfig(
            max_position_pct=0.10,
            max_drawdown_halt=-0.20,
        )
        
        assert config.max_position_pct == 0.10
        assert config.max_drawdown_halt == -0.20


# =============================================================================
# Cost Model Tests
# =============================================================================


class TestCostModel:
    """Test cost model calculations."""
    
    def test_commission_calculation(self):
        """Test commission calculation."""
        config = CostModelConfig(commission_per_share=0.005)
        model = CostModel(config)
        
        bar = BarData(
            symbol="AAPL",
            timestamp=datetime.now(),
            open=100, high=101, low=99, close=100,
            volume=1_000_000,
        )
        
        order = Order(
            order_id="TEST",
            symbol="AAPL",
            side=OrderSide.BUY,
            qty=100,
        )
        
        commission, slippage, fees = model.estimate_cost(order, bar, 100.0)
        
        assert commission == 0.5  # 100 * 0.005
        assert slippage > 0  # Spread + impact
        assert fees == 0  # No fees for buys
    
    def test_sell_fees(self):
        """Test regulatory fees on sells."""
        config = CostModelConfig(
            sec_fee_rate=0.0000278,
            taf_fee_per_share=0.000166,
        )
        model = CostModel(config)
        
        bar = BarData(
            symbol="AAPL",
            timestamp=datetime.now(),
            open=100, high=101, low=99, close=100,
            volume=1_000_000,
        )
        
        order = Order(
            order_id="TEST",
            symbol="AAPL",
            side=OrderSide.SELL,
            qty=1000,
        )
        
        _, _, fees = model.estimate_cost(order, bar, 100.0)
        
        # SEC fee + TAF fee
        expected_sec = 100_000 * 0.0000278
        expected_taf = 1000 * 0.000166
        assert abs(fees - (expected_sec + expected_taf)) < 0.01
    
    def test_market_impact(self):
        """Test market impact increases with order size."""
        config = CostModelConfig(market_impact_bps_per_pct_adv=10.0)
        model = CostModel(config)
        
        bar = BarData(
            symbol="AAPL",
            timestamp=datetime.now(),
            open=100, high=101, low=99, close=100,
            volume=1_000_000,
        )
        
        # Small order
        small_order = Order(order_id="SMALL", symbol="AAPL", side=OrderSide.BUY, qty=100)
        _, small_slippage, _ = model.estimate_cost(small_order, bar, 100.0)
        
        # Large order
        large_order = Order(order_id="LARGE", symbol="AAPL", side=OrderSide.BUY, qty=10000)
        _, large_slippage, _ = model.estimate_cost(large_order, bar, 100.0)
        
        # Large order should have higher slippage per share
        assert large_slippage / 10000 > small_slippage / 100


# =============================================================================
# Execution Tests
# =============================================================================


class TestExecutionSimulator:
    """Test order execution simulation."""
    
    def test_immediate_fill(self, sample_bar, sample_order):
        """Test immediate fill at close price."""
        config = ExecutionConfig(fill_model=FillModel.IMMEDIATE)
        executor = ExecutionSimulator(config)
        
        fill = executor.simulate_fill(sample_order, sample_bar)
        
        assert fill is not None
        assert fill.price == sample_bar.close
        assert fill.qty == sample_order.qty
    
    def test_limit_order_fill(self, sample_bar):
        """Test limit order fills only when price touches limit."""
        config = ExecutionConfig(fill_model=FillModel.LIMIT)
        executor = ExecutionSimulator(config)

        # Buy limit at 180, bar low=184 - price never reached limit, no fill
        order_no_fill = Order(
            order_id="TEST",
            symbol="AAPL",
            side=OrderSide.BUY,
            qty=100,
            order_type=OrderType.LIMIT,
            limit_price=180.0,  # Below bar low (184)
        )

        fill = executor.simulate_fill(order_no_fill, sample_bar)
        assert fill is None  # Price never dropped to 180

        # Buy limit at 185, bar low=184 - price touched limit, should fill
        order_fill = Order(
            order_id="TEST2",
            symbol="AAPL",
            side=OrderSide.BUY,
            qty=100,
            order_type=OrderType.LIMIT,
            limit_price=185.0,  # Within bar range (low=184 <= 185)
        )

        fill = executor.simulate_fill(order_fill, sample_bar)
        assert fill is not None
    
    def test_volume_participation_limit(self, sample_bar, sample_order):
        """Test order size limited by volume participation."""
        config = ExecutionConfig(
            fill_model=FillModel.IMMEDIATE,
            max_participation_rate=0.01,  # 1% of volume
            partial_fills=True,
        )
        executor = ExecutionSimulator(config)
        
        # Large order
        large_order = Order(
            order_id="LARGE",
            symbol="AAPL",
            side=OrderSide.BUY,
            qty=1_000_000,  # More than 1% of volume
        )
        
        fill = executor.simulate_fill(large_order, sample_bar)
        
        assert fill is not None
        assert fill.qty <= sample_bar.volume * 0.01


class TestSimulatedBroker:
    """Test simulated broker."""
    
    def test_order_submission(self, sample_order):
        """Test order submission."""
        broker = SimulatedBroker()
        
        order_id = broker.submit_order(sample_order)
        
        assert order_id == sample_order.order_id
        assert len(broker.pending_orders) == 1
    
    def test_order_processing(self, sample_bar, sample_order):
        """Test order processing on bar."""
        broker = SimulatedBroker()
        broker.submit_order(sample_order)
        
        fills = broker.process_bar(sample_bar)
        
        assert len(fills) == 1
        assert fills[0].symbol == sample_order.symbol
        assert len(broker.pending_orders) == 0
    
    def test_order_cancellation(self, sample_order):
        """Test order cancellation."""
        broker = SimulatedBroker()
        broker.submit_order(sample_order)
        
        assert len(broker.pending_orders) == 1
        
        result = broker.cancel_order(sample_order.order_id)
        
        assert result is True
        assert len(broker.pending_orders) == 0


# =============================================================================
# Portfolio Tests
# =============================================================================


class TestSimulatedPortfolio:
    """Test simulated portfolio."""
    
    def test_initial_state(self):
        """Test initial portfolio state."""
        portfolio = SimulatedPortfolio(100_000)
        
        assert portfolio.cash == 100_000
        assert portfolio.equity == 100_000
        assert portfolio.positions_value == 0
        assert len(portfolio.positions) == 0
    
    def test_buy_fill_processing(self):
        """Test processing buy fill."""
        portfolio = SimulatedPortfolio(100_000)
        
        fill = Fill(
            order_id="TEST",
            symbol="AAPL",
            side=OrderSide.BUY,
            qty=100,
            price=150.0,
            timestamp=datetime.now(),
            commission=1.0,
            slippage=0.5,
            fees=0.0,
        )
        
        portfolio.process_fill(fill)
        
        # Check position created
        assert "AAPL" in portfolio.positions
        assert portfolio.positions["AAPL"].qty == 100
        assert portfolio.positions["AAPL"].avg_cost == 150.0
        
        # Check cash reduced
        expected_cash = 100_000 - (100 * 150.0 + 1.5)  # notional + costs
        assert abs(portfolio.cash - expected_cash) < 0.01
    
    def test_sell_fill_processing(self):
        """Test processing sell fill creates trade."""
        portfolio = SimulatedPortfolio(100_000)
        
        # First buy
        buy_fill = Fill(
            order_id="BUY",
            symbol="AAPL",
            side=OrderSide.BUY,
            qty=100,
            price=150.0,
            timestamp=datetime(2024, 1, 1),
            commission=0, slippage=0, fees=0,
        )
        portfolio.process_fill(buy_fill)
        
        # Then sell
        sell_fill = Fill(
            order_id="SELL",
            symbol="AAPL",
            side=OrderSide.SELL,
            qty=100,
            price=160.0,
            timestamp=datetime(2024, 1, 15),
            commission=0, slippage=0, fees=0,
        )
        portfolio.process_fill(sell_fill)
        
        # Position should be closed
        assert "AAPL" not in portfolio.positions
        
        # Trade should be recorded
        assert len(portfolio.trades) == 1
        trade = portfolio.trades[0]
        assert trade.pnl == 1000  # (160 - 150) * 100
    
    def test_drawdown_calculation(self):
        """Test drawdown calculation."""
        portfolio = SimulatedPortfolio(100_000)
        
        # Record at peak
        portfolio.record_snapshot(datetime(2024, 1, 1))
        
        # Lose 10%
        portfolio.cash = 90_000
        portfolio.record_snapshot(datetime(2024, 1, 15))
        
        assert abs(portfolio.drawdown - (-0.10)) < 0.001


# =============================================================================
# Engine Tests
# =============================================================================


class TestBacktestEngine:
    """Test backtest engine."""
    
    def test_engine_initialization(self, backtest_config):
        """Test engine initialization."""
        engine = BacktestEngine(backtest_config)
        
        assert engine.config == backtest_config
        assert engine.portfolio.cash == 100_000
    
    def test_data_loading(self, backtest_config, price_data):
        """Test data loading."""
        engine = BacktestEngine(backtest_config)
        engine.load_data(price_data)
        
        # Data handler should have data
        assert engine.data_handler._data is not None
    
    def test_simple_backtest(self, backtest_config, price_data):
        """Test simple backtest with dummy strategy."""
        engine = BacktestEngine(backtest_config)
        engine.load_data(price_data)
        
        # Simple buy-and-hold strategy
        class BuyAndHoldStrategy:
            def __init__(self):
                self.bought = False
            
            def on_bar(self, event, portfolio):
                if not self.bought:
                    self.bought = True
                    return [
                        Signal(
                            symbol="AAPL",
                            timestamp=event.timestamp,
                            side=OrderSide.BUY,
                            target_weight=0.20,
                        )
                    ]
                return []
        
        result = engine.run(BuyAndHoldStrategy())
        
        assert result is not None
        assert len(result.snapshots) > 0
        assert not result.equity_curve.empty


class TestBacktestRiskManager:
    """Test backtest risk manager."""
    
    def test_drawdown_halt(self, backtest_config):
        """Test trading halts at max drawdown."""
        backtest_config.risk_rules.max_drawdown_halt = -0.10
        risk_manager = BacktestRiskManager(backtest_config)
        
        portfolio = SimulatedPortfolio(100_000)
        portfolio.cash = 85_000  # 15% loss
        portfolio._peak_equity = 100_000
        portfolio.record_snapshot(datetime.now())
        
        signals = [Signal(
            symbol="AAPL",
            timestamp=datetime.now(),
            side=OrderSide.BUY,
            target_weight=0.10,
        )]
        
        approved = risk_manager.validate(signals, portfolio)
        
        # Should reject all signals due to drawdown
        assert len(approved) == 0
    
    def test_position_limit(self, backtest_config):
        """Test position size limit."""
        backtest_config.risk_rules.max_position_pct = 0.10
        risk_manager = BacktestRiskManager(backtest_config)
        
        portfolio = SimulatedPortfolio(100_000)
        
        # Signal exceeds position limit
        signals = [Signal(
            symbol="AAPL",
            timestamp=datetime.now(),
            side=OrderSide.BUY,
            target_weight=0.20,  # > 10% limit
        )]
        
        approved = risk_manager.validate(signals, portfolio)
        
        assert len(approved) == 0


# =============================================================================
# Optimization Tests
# =============================================================================


class TestMonteCarloAnalyzer:
    """Test Monte Carlo analysis."""
    
    def test_bootstrap_analysis(self, sample_trades):
        """Test bootstrap analysis."""
        analyzer = MonteCarloAnalyzer(MonteCarloConfig(n_simulations=1000))
        
        result = analyzer.bootstrap_analysis(sample_trades)
        
        assert result.n_simulations == 1000
        assert result.sharpe_95ci[0] < result.sharpe_mean < result.sharpe_95ci[1]
        assert 0 <= result.pct_profitable <= 1
    
    def test_significance_testing(self, price_data):
        """Test strategy significance testing."""
        analyzer = MonteCarloAnalyzer(MonteCarloConfig(random_strategy_tests=100))
        
        # Test with a moderate Sharpe
        is_sig, p_value = analyzer.test_significance(1.0, price_data, n_random=100)
        
        assert isinstance(is_sig, (bool, np.bool_))
        assert 0 <= p_value <= 1


class TestWalkForwardOptimizer:
    """Test walk-forward optimization."""
    
    def test_window_generation(self, price_data):
        """Test walk-forward window generation."""
        config = WalkForwardConfig(n_windows=3, in_sample_pct=0.70)
        optimizer = WalkForwardOptimizer(config)
        
        windows = optimizer._generate_windows(price_data.index)
        
        assert len(windows) == 3
        
        for w in windows:
            assert w.in_sample_start < w.in_sample_end
            assert w.in_sample_end < w.out_of_sample_start
            assert w.out_of_sample_start < w.out_of_sample_end


# =============================================================================
# Reporting Tests
# =============================================================================


class TestTearSheetGenerator:
    """Test tear sheet generation."""
    
    def test_generate_tearsheet(self, sample_trades):
        """Test tear sheet generation."""
        # Create mock result
        equity = pd.Series(
            100_000 * np.cumprod(1 + np.random.normal(0.001, 0.01, 252)),
            index=pd.date_range("2024-01-01", periods=252, freq="B"),
        )
        
        metrics = BacktestMetrics(
            total_return=0.15,
            cagr=0.12,
            volatility=0.18,
            max_drawdown=-0.15,
            sharpe_ratio=0.85,
            sortino_ratio=1.2,
            total_trades=100,
            win_rate=0.60,
        )
        
        result = BacktestResult(
            metrics=metrics,
            equity_curve=equity,
            trades=sample_trades,
            monthly_returns=(1 + equity.pct_change()).resample("ME").prod() - 1,
        )
        
        generator = TearSheetGenerator()
        tearsheet = generator.generate(result, "Test Strategy")
        
        assert "STRATEGY TEAR SHEET" in tearsheet
        assert "Test Strategy" in tearsheet
        assert "Sharpe Ratio" in tearsheet
    
    def test_generate_dict(self, sample_trades):
        """Test dictionary output."""
        equity = pd.Series(
            100_000 * np.cumprod(1 + np.random.normal(0.001, 0.01, 100)),
            index=pd.date_range("2024-01-01", periods=100, freq="B"),
        )
        
        result = BacktestResult(
            metrics=BacktestMetrics(sharpe_ratio=0.85),
            equity_curve=equity,
            trades=sample_trades,
        )
        
        generator = TearSheetGenerator()
        data = generator.generate_dict(result)
        
        assert "metrics" in data
        assert "returns" in data
        assert "risk_adjusted" in data


class TestStrategyComparator:
    """Test strategy comparison."""
    
    def test_compare_strategies(self):
        """Test strategy comparison."""
        # Create mock results
        dates = pd.date_range("2024-01-01", periods=252, freq="B")
        
        result1 = BacktestResult(
            metrics=BacktestMetrics(
                sharpe_ratio=0.8,
                cagr=0.10,
                max_drawdown=-0.15,
                win_rate=0.55,
                profit_factor=1.4,
            ),
            daily_returns=pd.Series(np.random.normal(0.0004, 0.01, 252), index=dates),
            drawdown_curve=pd.Series(np.random.uniform(-0.15, 0, 252), index=dates),
        )
        
        result2 = BacktestResult(
            metrics=BacktestMetrics(
                sharpe_ratio=1.0,
                cagr=0.12,
                max_drawdown=-0.12,
                win_rate=0.60,
                profit_factor=1.6,
            ),
            daily_returns=pd.Series(np.random.normal(0.0005, 0.01, 252), index=dates),
            drawdown_curve=pd.Series(np.random.uniform(-0.12, 0, 252), index=dates),
        )
        
        comparator = StrategyComparator()
        comparison = comparator.compare({
            "Strategy A": result1,
            "Strategy B": result2,
        })
        
        assert "returns_table" in comparison
        assert "risk_table" in comparison
        assert "winner_by_metric" in comparison
        assert comparison["winner_by_metric"]["sharpe"] == "Strategy B"
    
    def test_format_comparison(self):
        """Test comparison formatting."""
        comparator = StrategyComparator()
        
        comparison = {
            "returns_table": pd.DataFrame({
                "Total Return": [0.15, 0.18],
                "CAGR": [0.12, 0.14],
            }, index=["A", "B"]),
            "winner_by_metric": {"sharpe": "B", "cagr": "B"},
            "ranking": [
                {"strategy": "B", "composite_score": 1.2, "sharpe": 1.0, "cagr": 0.14},
                {"strategy": "A", "composite_score": 1.0, "sharpe": 0.8, "cagr": 0.12},
            ],
        }
        
        formatted = comparator.format_comparison(comparison)
        
        assert "STRATEGY COMPARISON REPORT" in formatted
        assert "BEST BY METRIC" in formatted


# =============================================================================
# Integration Tests
# =============================================================================


class TestBacktestIntegration:
    """Integration tests for full backtest workflow."""
    
    def test_full_backtest_workflow(self, price_data):
        """Test complete backtest workflow."""
        # 1. Configure
        config = BacktestConfig(
            start_date=date(2021, 1, 1),
            end_date=date(2023, 12, 31),
            initial_capital=100_000,
            rebalance_frequency=RebalanceFrequency.MONTHLY,
            risk_rules=RiskConfig(max_position_pct=0.35),
        )
        
        # 2. Create strategy
        class SimpleStrategy:
            def on_bar(self, event, portfolio):
                signals = []
                # Equal weight top 3 stocks
                for symbol in ["AAPL", "MSFT", "GOOGL"]:
                    if symbol in event.bars:
                        current_weight = portfolio.get_position_weight(symbol)
                        if abs(current_weight - 0.30) > 0.05:
                            signals.append(Signal(
                                symbol=symbol,
                                timestamp=event.timestamp,
                                side=OrderSide.BUY,
                                target_weight=0.30,
                            ))
                return signals
        
        # 3. Run backtest
        engine = BacktestEngine(config)
        engine.load_data(price_data)
        result = engine.run(SimpleStrategy())
        
        # 4. Generate tearsheet
        generator = TearSheetGenerator()
        tearsheet = generator.generate(result, "Simple Equal Weight")
        
        # Assertions
        assert result.metrics.total_trades > 0
        assert not result.equity_curve.empty
        assert "Simple Equal Weight" in tearsheet
    
    def test_monte_carlo_integration(self, sample_trades):
        """Test Monte Carlo integration with backtest results."""
        analyzer = MonteCarloAnalyzer(MonteCarloConfig(n_simulations=500))
        
        mc_result = analyzer.bootstrap_analysis(sample_trades)
        
        # Create result and add MC data
        result = BacktestResult(
            metrics=BacktestMetrics(sharpe_ratio=0.85),
            trades=sample_trades,
        )
        
        generator = TearSheetGenerator()
        tearsheet = generator.generate(result, "Test", mc_result=mc_result)
        
        assert "Monte Carlo" in tearsheet


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
