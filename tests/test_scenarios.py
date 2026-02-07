"""Tests for Portfolio Scenarios."""

import pytest
from datetime import date
from dateutil.relativedelta import relativedelta

from src.scenarios import (
    # Config
    TradeAction, RebalanceStrategy, ScenarioType, GoalType,
    # Models
    Holding, Portfolio, ProposedTrade, TargetAllocation, InvestmentGoal,
    # Analyzers
    WhatIfAnalyzer, RebalanceSimulator, ScenarioAnalyzer,
    PortfolioComparer, GoalPlanner, PREDEFINED_SCENARIOS,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_portfolio():
    """Sample portfolio for testing."""
    return Portfolio(
        name="Test Portfolio",
        holdings=[
            Holding(symbol="AAPL", shares=100, cost_basis=15000, current_price=185, sector="Technology"),
            Holding(symbol="MSFT", shares=50, cost_basis=17500, current_price=378, sector="Technology"),
            Holding(symbol="JNJ", shares=75, cost_basis=11000, current_price=155, sector="Healthcare"),
        ],
        cash=10000,
    )


@pytest.fixture
def target_allocation():
    """Sample target allocation."""
    return TargetAllocation(
        name="Balanced",
        targets={
            "AAPL": 0.25,
            "MSFT": 0.25,
            "JNJ": 0.25,
            "GOOGL": 0.25,
        },
    )


# =============================================================================
# Test Portfolio Model
# =============================================================================

class TestPortfolio:
    """Tests for Portfolio model."""
    
    def test_total_value(self, sample_portfolio):
        """Test total value calculation."""
        # AAPL: 100 * 185 = 18500
        # MSFT: 50 * 378 = 18900
        # JNJ: 75 * 155 = 11625
        # Cash: 10000
        # Total: 59025
        assert sample_portfolio.total_value == 59025
    
    def test_get_weights(self, sample_portfolio):
        """Test weight calculation."""
        weights = sample_portfolio.get_weights()
        
        assert "AAPL" in weights
        assert "MSFT" in weights
        assert "JNJ" in weights
        
        # Weights should sum to less than 1 (due to cash)
        assert sum(weights.values()) < 1.0
    
    def test_get_holding(self, sample_portfolio):
        """Test getting a specific holding."""
        holding = sample_portfolio.get_holding("AAPL")
        assert holding is not None
        assert holding.shares == 100
        
        holding = sample_portfolio.get_holding("INVALID")
        assert holding is None


# =============================================================================
# Test What-If Analyzer
# =============================================================================

class TestWhatIfAnalyzer:
    """Tests for WhatIfAnalyzer."""
    
    def test_buy_simulation(self, sample_portfolio):
        """Test simulating a buy order."""
        analyzer = WhatIfAnalyzer()
        
        trade = ProposedTrade(
            symbol="GOOGL",
            action=TradeAction.BUY,
            dollar_amount=5000,
            assumed_price=141,
        )
        
        result = analyzer.simulate(sample_portfolio, [trade])
        
        assert result.resulting_portfolio is not None
        assert result.resulting_portfolio.get_holding("GOOGL") is not None
        assert result.resulting_portfolio.cash < sample_portfolio.cash
    
    def test_sell_simulation(self, sample_portfolio):
        """Test simulating a sell order."""
        analyzer = WhatIfAnalyzer()
        
        trade = ProposedTrade(
            symbol="AAPL",
            action=TradeAction.SELL,
            shares=50,
        )
        
        result = analyzer.simulate(sample_portfolio, [trade])
        
        aapl_holding = result.resulting_portfolio.get_holding("AAPL")
        assert aapl_holding.shares == 50  # Started with 100, sold 50
        assert result.resulting_portfolio.cash > sample_portfolio.cash
    
    def test_sell_all(self, sample_portfolio):
        """Test selling entire position."""
        analyzer = WhatIfAnalyzer()
        
        trade = ProposedTrade(
            symbol="JNJ",
            action=TradeAction.SELL_ALL,
        )
        
        result = analyzer.simulate(sample_portfolio, [trade])
        
        assert result.resulting_portfolio.get_holding("JNJ") is None
    
    def test_risk_impact(self, sample_portfolio):
        """Test risk impact calculation."""
        analyzer = WhatIfAnalyzer()
        
        trade = ProposedTrade(
            symbol="XOM",
            action=TradeAction.BUY,
            dollar_amount=10000,
            assumed_price=105,
        )
        
        result = analyzer.simulate(sample_portfolio, [trade])
        
        assert result.risk_impact is not None
        # Adding energy stock should change beta
        assert "sector_exposure_changes" in dir(result.risk_impact)
    
    def test_tax_impact(self, sample_portfolio):
        """Test tax impact calculation."""
        analyzer = WhatIfAnalyzer()
        
        # Sell AAPL (has gain)
        trade = ProposedTrade(
            symbol="AAPL",
            action=TradeAction.SELL,
            shares=50,
        )
        
        result = analyzer.simulate(sample_portfolio, [trade])
        
        assert result.tax_impact is not None


# =============================================================================
# Test Rebalance Simulator
# =============================================================================

class TestRebalanceSimulator:
    """Tests for RebalanceSimulator."""
    
    def test_rebalance_to_target(self, sample_portfolio, target_allocation):
        """Test rebalancing to target allocation."""
        simulator = RebalanceSimulator()
        
        result = simulator.simulate(
            sample_portfolio,
            target_allocation,
            strategy=RebalanceStrategy.TARGET_WEIGHT,
        )
        
        assert result.required_trades is not None
        assert len(result.required_trades) > 0  # Should need trades to rebalance
    
    def test_threshold_rebalance(self, sample_portfolio, target_allocation):
        """Test threshold-based rebalancing."""
        simulator = RebalanceSimulator()
        
        result = simulator.simulate(
            sample_portfolio,
            target_allocation,
            strategy=RebalanceStrategy.THRESHOLD,
            threshold_pct=5.0,
        )
        
        # Should still rebalance since drift is significant
        assert result is not None
    
    def test_current_drift_calculation(self, sample_portfolio, target_allocation):
        """Test drift calculation."""
        simulator = RebalanceSimulator()
        
        result = simulator.simulate(sample_portfolio, target_allocation)
        
        assert result.current_drift is not None
        assert len(result.current_drift) > 0


# =============================================================================
# Test Scenario Analyzer
# =============================================================================

class TestScenarioAnalyzer:
    """Tests for ScenarioAnalyzer."""
    
    def test_predefined_scenarios(self):
        """Test predefined scenarios exist."""
        assert ScenarioType.MARKET_CRASH in PREDEFINED_SCENARIOS
        assert ScenarioType.BEAR_MARKET in PREDEFINED_SCENARIOS
        assert ScenarioType.RECESSION in PREDEFINED_SCENARIOS
    
    def test_apply_crash_scenario(self, sample_portfolio):
        """Test applying market crash scenario."""
        analyzer = ScenarioAnalyzer()
        
        result = analyzer.apply_scenario(
            sample_portfolio,
            ScenarioType.MARKET_CRASH,
        )
        
        assert result.ending_value < result.starting_value
        assert result.pct_change < 0
        assert len(result.position_impacts) == 3
    
    def test_apply_bull_market(self, sample_portfolio):
        """Test applying bull market scenario."""
        analyzer = ScenarioAnalyzer()
        
        result = analyzer.apply_scenario(
            sample_portfolio,
            ScenarioType.BULL_MARKET,
        )
        
        assert result.ending_value > result.starting_value
        assert result.pct_change > 0
    
    def test_custom_scenario(self, sample_portfolio):
        """Test custom scenario."""
        analyzer = ScenarioAnalyzer()
        
        scenario = analyzer.create_custom_scenario(
            name="Tech Crash",
            market_change=-0.10,
            sector_impacts={"Technology": -0.30},
        )
        
        result = analyzer.apply_scenario(sample_portfolio, scenario)
        
        # Tech stocks should be hit harder
        assert result.pct_change < 0
    
    def test_run_all_scenarios(self, sample_portfolio):
        """Test running all scenarios."""
        analyzer = ScenarioAnalyzer()
        
        results = analyzer.run_all_scenarios(sample_portfolio)
        
        assert len(results) == len(PREDEFINED_SCENARIOS)


# =============================================================================
# Test Portfolio Comparer
# =============================================================================

class TestPortfolioComparer:
    """Tests for PortfolioComparer."""
    
    def test_compare_portfolios(self, sample_portfolio):
        """Test comparing two portfolios."""
        # Create a second portfolio
        portfolio2 = Portfolio(
            name="Conservative",
            holdings=[
                Holding(symbol="JNJ", shares=150, current_price=155, sector="Healthcare"),
                Holding(symbol="PG", shares=100, current_price=165, sector="Consumer Defensive"),
            ],
            cash=20000,
        )
        
        comparer = PortfolioComparer()
        comparison = comparer.compare(
            [sample_portfolio, portfolio2],
            names=["Growth", "Conservative"],
        )
        
        assert len(comparison.metrics) == 2
        assert comparison.recommended_index is not None
    
    def test_calculate_metrics(self, sample_portfolio):
        """Test metrics calculation."""
        comparer = PortfolioComparer()
        metrics = comparer.calculate_metrics(sample_portfolio)
        
        assert metrics.total_value == sample_portfolio.total_value
        assert metrics.num_holdings == 3
        assert metrics.beta > 0


# =============================================================================
# Test Goal Planner
# =============================================================================

class TestGoalPlanner:
    """Tests for GoalPlanner."""
    
    def test_project_goal(self):
        """Test goal projection."""
        planner = GoalPlanner()
        
        goal = InvestmentGoal(
            name="Retirement",
            target_amount=1_000_000,
            target_date=date.today() + relativedelta(years=20),
            current_amount=100_000,
            monthly_contribution=2000,
        )
        
        projection = planner.project_goal(goal, monte_carlo=False)
        
        assert goal.projected_value > goal.current_amount
        assert len(projection.projected_values) > 0
    
    def test_required_contribution(self):
        """Test required contribution calculation."""
        planner = GoalPlanner()
        
        required = planner.required_contribution(
            current_amount=50000,
            target_amount=100000,
            months=60,
            annual_return=0.07,
        )
        
        assert required > 0
        assert required < 1000  # Should be reasonable
    
    def test_time_to_goal(self):
        """Test time to goal calculation."""
        planner = GoalPlanner()
        
        months = planner.time_to_goal(
            current_amount=50000,
            target_amount=100000,
            monthly_contribution=500,
            annual_return=0.07,
        )
        
        assert months > 0
        assert months < 200  # Should be achievable
    
    def test_monte_carlo_probability(self):
        """Test Monte Carlo probability calculation."""
        planner = GoalPlanner()
        
        goal = InvestmentGoal(
            name="Test Goal",
            target_amount=200_000,
            target_date=date.today() + relativedelta(years=10),
            current_amount=100_000,
            monthly_contribution=500,
        )
        
        planner.project_goal(goal, monte_carlo=True)
        
        assert 0 <= goal.probability_of_success <= 1
    
    def test_create_retirement_goal(self):
        """Test retirement goal creation."""
        planner = GoalPlanner()
        
        goal = planner.create_retirement_goal(
            current_age=35,
            retirement_age=65,
            current_savings=200000,
            monthly_contribution=1500,
            annual_expenses=60000,
        )
        
        assert goal.goal_type == GoalType.RETIREMENT
        assert goal.target_amount > 0
        assert goal.target_date is not None
