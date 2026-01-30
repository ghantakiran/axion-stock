"""Tests for the risk management system."""

import numpy as np
import pandas as pd
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from src.risk.config import RiskConfig, ValidationResult, CheckResult, RiskAlert
from src.risk.metrics import RiskMetricsCalculator, PortfolioRiskMetrics, ConcentrationMetrics
from src.risk.var import VaRCalculator, VaRResult
from src.risk.stress_test import StressTestEngine, HISTORICAL_SCENARIOS, HYPOTHETICAL_SCENARIOS
from src.risk.drawdown import DrawdownProtection, RecoveryProtocol
from src.risk.pre_trade import PreTradeRiskChecker, OrderContext, PortfolioContext
from src.risk.attribution import AttributionAnalyzer, BrinsonAttribution, FactorAttribution
from src.risk.monitor import RiskMonitor, RiskDashboardData, RiskStatus


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_returns():
    """Generate sample daily returns."""
    np.random.seed(42)
    dates = pd.date_range(start='2024-01-01', periods=252, freq='D')
    returns = pd.Series(np.random.normal(0.0005, 0.015, 252), index=dates)
    return returns


@pytest.fixture
def sample_benchmark_returns():
    """Generate sample benchmark returns."""
    np.random.seed(43)
    dates = pd.date_range(start='2024-01-01', periods=252, freq='D')
    returns = pd.Series(np.random.normal(0.0004, 0.012, 252), index=dates)
    return returns


@pytest.fixture
def sample_positions():
    """Generate sample portfolio positions."""
    return [
        {"symbol": "AAPL", "market_value": 15000, "qty": 100, "entry_price": 145, "current_price": 150, "sector": "Technology"},
        {"symbol": "MSFT", "market_value": 12000, "qty": 30, "entry_price": 380, "current_price": 400, "sector": "Technology"},
        {"symbol": "JPM", "market_value": 10000, "qty": 50, "entry_price": 190, "current_price": 200, "sector": "Financials"},
        {"symbol": "JNJ", "market_value": 8000, "qty": 50, "entry_price": 155, "current_price": 160, "sector": "Healthcare"},
        {"symbol": "XOM", "market_value": 5000, "qty": 45, "entry_price": 100, "current_price": 111, "sector": "Energy"},
    ]


@pytest.fixture
def config():
    """Default risk configuration."""
    return RiskConfig()


# =============================================================================
# Test RiskConfig
# =============================================================================

class TestRiskConfig:
    """Tests for RiskConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RiskConfig()
        assert config.max_position_pct == 0.15
        assert config.max_sector_pct == 0.35
        assert config.position_stop_loss == -0.15
        assert config.portfolio_drawdown_warning == -0.05

    def test_validate_valid_config(self):
        """Test validation passes for valid config."""
        config = RiskConfig()
        errors = config.validate()
        assert len(errors) == 0

    def test_validate_invalid_position_pct(self):
        """Test validation catches invalid position percentage."""
        config = RiskConfig(max_position_pct=1.5)
        errors = config.validate()
        assert len(errors) > 0
        assert "max_position_pct" in errors[0]

    def test_validate_invalid_drawdown_order(self):
        """Test validation catches incorrect drawdown threshold ordering."""
        config = RiskConfig(
            portfolio_drawdown_warning=-0.15,
            portfolio_drawdown_reduce=-0.10,
            portfolio_drawdown_emergency=-0.05
        )
        errors = config.validate()
        assert len(errors) > 0
        assert "Drawdown thresholds" in errors[0]


# =============================================================================
# Test RiskMetricsCalculator
# =============================================================================

class TestRiskMetricsCalculator:
    """Tests for RiskMetricsCalculator."""

    def test_calculate_portfolio_metrics(self, sample_returns, sample_benchmark_returns):
        """Test portfolio metrics calculation."""
        calc = RiskMetricsCalculator()
        metrics = calc.calculate_portfolio_metrics(
            returns=sample_returns,
            benchmark_returns=sample_benchmark_returns,
            portfolio_value=100_000
        )

        assert isinstance(metrics, PortfolioRiskMetrics)
        assert metrics.sharpe_ratio != 0
        assert metrics.portfolio_volatility > 0
        assert metrics.max_drawdown <= 0

    def test_calculate_sharpe_ratio(self, sample_returns):
        """Test Sharpe ratio calculation."""
        calc = RiskMetricsCalculator()
        sharpe = calc.calculate_sharpe_ratio(sample_returns, risk_free_rate=0.04)
        # Sharpe should be reasonable
        assert -5 < sharpe < 5

    def test_calculate_sortino_ratio(self, sample_returns):
        """Test Sortino ratio calculation."""
        calc = RiskMetricsCalculator()
        sortino = calc.calculate_sortino_ratio(sample_returns)
        assert sortino is not None
        # Should be finite (not inf) for typical data
        assert sortino > -100

    def test_calculate_max_drawdown(self, sample_returns):
        """Test max drawdown calculation."""
        calc = RiskMetricsCalculator()
        max_dd = calc.calculate_max_drawdown(sample_returns)
        assert max_dd <= 0
        assert max_dd >= -1

    def test_calculate_concentration(self, sample_positions):
        """Test concentration metrics calculation."""
        calc = RiskMetricsCalculator()
        total_value = sum(p["market_value"] for p in sample_positions)
        for p in sample_positions:
            p["weight"] = p["market_value"] / total_value

        concentration = calc.calculate_concentration(sample_positions)

        assert isinstance(concentration, ConcentrationMetrics)
        assert concentration.largest_position_symbol == "AAPL"
        assert 0 < concentration.largest_position_weight < 1
        assert concentration.largest_sector_name == "Technology"
        assert concentration.herfindahl_index > 0  # Should have some concentration


# =============================================================================
# Test VaRCalculator
# =============================================================================

class TestVaRCalculator:
    """Tests for VaRCalculator."""

    def test_historical_var(self, sample_returns):
        """Test historical VaR calculation."""
        calc = VaRCalculator()
        var_95 = calc.historical_var(sample_returns, confidence=0.95)
        var_99 = calc.historical_var(sample_returns, confidence=0.99)

        assert var_95 < 0  # VaR is a loss (returns percentage)
        assert var_99 < var_95  # 99% VaR worse than 95%

    def test_parametric_var(self, sample_returns):
        """Test parametric VaR calculation."""
        calc = VaRCalculator()
        var_95 = calc.parametric_var(sample_returns, confidence=0.95)

        assert var_95 < 0  # Negative return percentage

    def test_monte_carlo_var(self, sample_returns):
        """Test Monte Carlo VaR calculation."""
        calc = VaRCalculator()
        var_95 = calc.monte_carlo_var(
            sample_returns,
            confidence=0.95,
            num_simulations=1000
        )

        assert var_95 < 0  # Negative return percentage

    def test_historical_var_full(self, sample_returns):
        """Test full VaR result."""
        calc = VaRCalculator()
        result = calc.historical_var_full(
            returns=sample_returns,
            portfolio_value=100_000
        )

        assert isinstance(result, VaRResult)
        # VaR is returned as positive dollar amount (loss)
        assert result.var_95 > 0
        assert result.var_99 > result.var_95  # 99% VaR higher loss than 95%
        assert result.cvar_95 >= result.var_95  # CVaR (expected shortfall) >= VaR
        assert result.returns_distribution is not None


# =============================================================================
# Test StressTestEngine
# =============================================================================

class TestStressTestEngine:
    """Tests for StressTestEngine."""

    def test_historical_scenarios_exist(self):
        """Test that historical scenarios are defined."""
        assert len(HISTORICAL_SCENARIOS) >= 5
        scenario_names = [s.name for s in HISTORICAL_SCENARIOS]
        assert "COVID Crash" in scenario_names
        assert "GFC" in scenario_names

    def test_hypothetical_scenarios_exist(self):
        """Test that hypothetical scenarios are defined."""
        assert len(HYPOTHETICAL_SCENARIOS) >= 5
        scenario_names = [s.name for s in HYPOTHETICAL_SCENARIOS]
        assert "Rate Shock +200bps" in scenario_names

    def test_run_hypothetical_test(self, sample_positions):
        """Test hypothetical stress test."""
        engine = StressTestEngine()
        total_value = sum(p["market_value"] for p in sample_positions)

        results = engine.run_hypothetical_tests(
            positions=sample_positions,
            portfolio_value=total_value,
            sector_map={"AAPL": "Technology", "MSFT": "Technology", "JPM": "Financials"}
        )

        assert len(results) > 0
        for result in results:
            assert result.portfolio_impact_pct <= 0  # Stress = negative impact

    def test_scenario_worst_position(self, sample_positions):
        """Test that worst position is identified in stress tests."""
        engine = StressTestEngine()
        total_value = sum(p["market_value"] for p in sample_positions)

        results = engine.run_hypothetical_tests(
            positions=sample_positions,
            portfolio_value=total_value,
        )

        for result in results:
            if result.worst_position_symbol:
                assert result.worst_position_impact_pct <= 0


# =============================================================================
# Test DrawdownProtection
# =============================================================================

class TestDrawdownProtection:
    """Tests for DrawdownProtection."""

    def test_initial_state(self, config):
        """Test initial state is normal."""
        protection = DrawdownProtection(config=config)
        protection.update_portfolio(100_000)

        allowed, reason = protection.is_trading_allowed()
        assert allowed
        assert reason == ""

    def test_warning_threshold(self, config):
        """Test warning threshold detection."""
        alerts_received = []
        protection = DrawdownProtection(
            config=config,
            on_alert=lambda a: alerts_received.append(a)
        )

        protection.update_portfolio(100_000)  # Initial
        protection.update_portfolio(94_000)   # -6% drawdown

        # Should have triggered warning at -5%
        state = protection.get_drawdown_state()
        assert state["portfolio"]["current_drawdown"] <= -0.05

    def test_position_stop_loss(self, config):
        """Test position stop-loss detection."""
        protection = DrawdownProtection(config=config)

        # Entry at $100, current at $84 = -16% loss (past -15% stop)
        alert = protection.check_position_stop_loss(
            symbol="TEST",
            entry_price=100,
            current_price=84
        )

        assert alert is not None
        assert "stop" in alert.message.lower() or "TEST" in alert.message

    def test_recovery_state_after_drawdown(self, config):
        """Test recovery state is triggered after significant drawdown."""
        protection = DrawdownProtection(config=config)

        protection.update_portfolio(100_000)
        protection.update_portfolio(88_000)  # -12% drawdown (past reduce threshold)

        state = protection.get_drawdown_state()
        assert state["recovery_state"] in ["cooldown", "scaling_in", "reduced_size"]


# =============================================================================
# Test PreTradeRiskChecker
# =============================================================================

class TestPreTradeRiskChecker:
    """Tests for PreTradeRiskChecker."""

    def test_buying_power_check_passes(self, config):
        """Test buying power check passes with sufficient funds."""
        checker = PreTradeRiskChecker(config=config)

        order = OrderContext(
            symbol="AAPL",
            side="buy",
            quantity=10,
            price=150.0
        )
        portfolio = PortfolioContext(
            equity=100_000,
            cash=50_000,
            buying_power=50_000,
            positions=[]
        )

        result = checker._check_buying_power(order, portfolio)
        assert result.passed

    def test_buying_power_check_fails(self, config):
        """Test buying power check fails with insufficient funds."""
        checker = PreTradeRiskChecker(config=config)

        order = OrderContext(
            symbol="AAPL",
            side="buy",
            quantity=1000,
            price=150.0
        )
        portfolio = PortfolioContext(
            equity=100_000,
            cash=5_000,
            buying_power=5_000,
            positions=[]
        )

        result = checker._check_buying_power(order, portfolio)
        assert not result.passed

    def test_position_limit_check(self, config):
        """Test position limit check."""
        checker = PreTradeRiskChecker(config=config)

        order = OrderContext(
            symbol="AAPL",
            side="buy",
            quantity=100,
            price=150.0  # $15,000 order
        )
        portfolio = PortfolioContext(
            equity=100_000,
            cash=50_000,
            buying_power=50_000,
            positions=[{"symbol": "AAPL", "market_value": 5000}]  # Already $5k
        )

        # After purchase: $20k / $100k = 20% > 15% limit
        result = checker._check_position_limit(order, portfolio)
        assert not result.passed
        assert result.severity == "block"

    def test_sector_limit_check(self, config):
        """Test sector limit check."""
        checker = PreTradeRiskChecker(
            config=config,
            sector_map={"AAPL": "Technology", "MSFT": "Technology"}
        )

        order = OrderContext(
            symbol="AAPL",
            side="buy",
            quantity=100,
            price=150.0  # $15,000 order
        )
        portfolio = PortfolioContext(
            equity=100_000,
            cash=50_000,
            buying_power=50_000,
            positions=[
                {"symbol": "MSFT", "market_value": 25000, "weight": 0.25, "sector": "Technology"}
            ]
        )

        # After purchase: $40k Technology / $100k = 40% > 35% limit
        result = checker._check_sector_limit(order, portfolio)
        assert not result.passed

    def test_validate_sync_approved(self, config):
        """Test full validation passes for valid order."""
        checker = PreTradeRiskChecker(config=config)

        order = OrderContext(
            symbol="AAPL",
            side="buy",
            quantity=10,
            price=150.0  # $1,500 order
        )
        portfolio = PortfolioContext(
            equity=100_000,
            cash=50_000,
            buying_power=50_000,
            positions=[]
        )

        result = checker.validate_sync(order, portfolio)
        assert result.approved


# =============================================================================
# Test AttributionAnalyzer
# =============================================================================

class TestAttributionAnalyzer:
    """Tests for AttributionAnalyzer."""

    def test_brinson_attribution(self):
        """Test Brinson attribution calculation."""
        analyzer = AttributionAnalyzer()

        # Portfolio overweight tech, underweight financials
        portfolio_weights = {"Technology": 0.40, "Financials": 0.30, "Healthcare": 0.30}
        benchmark_weights = {"Technology": 0.30, "Financials": 0.40, "Healthcare": 0.30}

        # Tech outperformed
        portfolio_returns = {"Technology": 0.15, "Financials": 0.08, "Healthcare": 0.10}
        benchmark_returns = {"Technology": 0.12, "Financials": 0.06, "Healthcare": 0.09}

        result = analyzer.brinson_attribution(
            portfolio_weights=portfolio_weights,
            benchmark_weights=benchmark_weights,
            portfolio_returns=portfolio_returns,
            benchmark_returns=benchmark_returns
        )

        assert isinstance(result, BrinsonAttribution)
        assert result.active_return > 0  # Portfolio outperformed
        assert result.allocation_effect > 0  # Good sector bets
        assert result.selection_effect > 0  # Good stock picking

    def test_factor_attribution(self):
        """Test factor attribution calculation."""
        analyzer = AttributionAnalyzer()

        factor_exposures = {
            "market": 1.1,
            "value": 0.3,
            "momentum": 0.2,
            "quality": 0.4,
            "growth": -0.1
        }
        factor_returns = {
            "market": 0.10,
            "value": 0.02,
            "momentum": 0.03,
            "quality": 0.01,
            "growth": 0.04
        }

        result = analyzer.factor_attribution(
            portfolio_return=0.15,
            factor_exposures=factor_exposures,
            factor_returns=factor_returns
        )

        assert isinstance(result, FactorAttribution)
        assert result.total_return == 0.15
        assert result.market_contribution == 1.1 * 0.10  # 0.11
        assert result.residual != 0  # Alpha exists

    def test_calculate_factor_exposures(self):
        """Test portfolio factor exposure calculation."""
        analyzer = AttributionAnalyzer()

        positions = [
            {"weight": 0.4, "factor_scores": {"market": 0.7, "value": 0.8}},
            {"weight": 0.3, "factor_scores": {"market": 0.6, "value": 0.3}},
            {"weight": 0.3, "factor_scores": {"market": 0.5, "value": 0.5}},
        ]

        exposures = analyzer.calculate_factor_exposures(positions)

        assert "market" in exposures
        assert "value" in exposures


# =============================================================================
# Test RiskMonitor
# =============================================================================

class TestRiskMonitor:
    """Tests for RiskMonitor."""

    def test_initial_status(self, config):
        """Test initial monitor status."""
        monitor = RiskMonitor(config=config)
        assert monitor.get_status() == RiskStatus.NORMAL

    def test_update_returns_dashboard_data(self, config, sample_positions, sample_returns, sample_benchmark_returns):
        """Test update returns valid dashboard data."""
        monitor = RiskMonitor(config=config)
        total_value = sum(p["market_value"] for p in sample_positions)

        dashboard = monitor.update(
            positions=sample_positions,
            returns=sample_returns,
            benchmark_returns=sample_benchmark_returns,
            portfolio_value=total_value
        )

        assert isinstance(dashboard, RiskDashboardData)
        assert dashboard.portfolio_metrics is not None
        assert dashboard.concentration_metrics is not None
        assert dashboard.trading_allowed

    def test_check_order(self, config, sample_positions):
        """Test pre-trade order check."""
        monitor = RiskMonitor(config=config)

        order = OrderContext(
            symbol="AAPL",
            side="buy",
            quantity=10,
            price=150.0
        )
        portfolio = PortfolioContext(
            equity=100_000,
            cash=50_000,
            buying_power=50_000,
            positions=[]
        )

        result = monitor.check_order(order, portfolio)
        assert isinstance(result, ValidationResult)
        assert result.approved

    def test_alert_generation(self, config):
        """Test alert generation on limit breach."""
        alerts = []
        monitor = RiskMonitor(
            config=config,
            on_alert=lambda a: alerts.append(a)
        )

        # Create position that exceeds concentration limits
        positions = [
            {"symbol": "AAPL", "market_value": 50000, "sector": "Technology"},
        ]

        # This should generate concentration alert (50% > 15% limit)
        dashboard = monitor.update(
            positions=positions,
            portfolio_value=100_000
        )

        assert len(dashboard.active_alerts) > 0

    def test_generate_risk_report(self, config, sample_positions, sample_returns):
        """Test risk report generation."""
        monitor = RiskMonitor(config=config)
        total_value = sum(p["market_value"] for p in sample_positions)

        monitor.update(
            positions=sample_positions,
            returns=sample_returns,
            portfolio_value=total_value
        )

        report = monitor.generate_risk_report()

        assert "RISK REPORT" in report
        assert "STATUS" in report
        assert "PORTFOLIO METRICS" in report


# =============================================================================
# Integration Tests
# =============================================================================

class TestRiskSystemIntegration:
    """Integration tests for the risk system."""

    def test_full_risk_workflow(self, config, sample_positions, sample_returns, sample_benchmark_returns):
        """Test complete risk management workflow."""
        # 1. Create monitor
        alerts = []
        monitor = RiskMonitor(
            config=config,
            sector_map={"AAPL": "Technology", "MSFT": "Technology", "JPM": "Financials"},
            on_alert=lambda a: alerts.append(a)
        )

        total_value = sum(p["market_value"] for p in sample_positions)

        # 2. Update with current state
        dashboard = monitor.update(
            positions=sample_positions,
            returns=sample_returns,
            benchmark_returns=sample_benchmark_returns,
            portfolio_value=total_value
        )

        # 3. Verify dashboard populated
        assert dashboard.portfolio_metrics is not None
        assert dashboard.var_metrics is not None
        assert dashboard.concentration_metrics is not None

        # 4. Check trading is allowed
        allowed, reason = monitor.is_trading_allowed()
        assert allowed

        # 5. Pre-trade check
        order = OrderContext(
            symbol="GOOGL",
            side="buy",
            quantity=10,
            price=140.0
        )
        portfolio = PortfolioContext(
            equity=total_value,
            cash=20_000,
            buying_power=20_000,
            positions=sample_positions
        )

        result = monitor.check_order(order, portfolio)
        assert result.approved

        # 6. Generate report
        report = monitor.generate_risk_report()
        assert len(report) > 100

    def test_drawdown_protection_integration(self, config):
        """Test drawdown protection integrates with monitor."""
        monitor = RiskMonitor(config=config)

        # Initial state
        positions = [{"symbol": "AAPL", "market_value": 50000, "sector": "Technology"}]
        monitor.update(positions=positions, portfolio_value=100_000)

        # Simulate drawdown
        monitor.update(positions=positions, portfolio_value=92_000)  # -8%

        dashboard = monitor.get_dashboard_data()
        assert dashboard.current_drawdown <= -0.05


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
