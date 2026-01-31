"""Tests for Dividend Tracker."""

import pytest
from datetime import date, timedelta

from src.dividends import (
    # Config
    DividendFrequency, DividendType, SafetyRating, DividendStatus,
    # Models
    DividendEvent, DividendRecord, DividendHolding, PortfolioIncome,
    # Calendar
    DividendCalendar, generate_sample_calendar,
    # Income
    IncomeProjector,
    # Safety
    SafetyAnalyzer, FinancialMetrics,
    # Growth
    GrowthAnalyzer, generate_sample_growth_data,
    # DRIP
    DRIPSimulator,
    # Tax
    TaxAnalyzer,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_event():
    """Sample dividend event."""
    return DividendEvent(
        symbol="AAPL",
        company_name="Apple Inc.",
        ex_dividend_date=date.today() + timedelta(days=5),
        payment_date=date.today() + timedelta(days=12),
        amount=0.24,
        previous_amount=0.23,
        frequency=DividendFrequency.QUARTERLY,
    )


@pytest.fixture
def sample_holding():
    """Sample dividend holding."""
    return DividendHolding(
        symbol="AAPL",
        company_name="Apple Inc.",
        shares=100,
        cost_basis=15000,  # $150/share
        current_price=185,
        sector="Technology",
        annual_dividend=0.96,
        frequency=DividendFrequency.QUARTERLY,
    )


@pytest.fixture
def sample_holdings():
    """Sample list of holdings."""
    return [
        DividendHolding(
            symbol="AAPL", shares=100, cost_basis=15000,
            current_price=185, annual_dividend=0.96,
            frequency=DividendFrequency.QUARTERLY, sector="Technology",
        ),
        DividendHolding(
            symbol="JNJ", shares=50, cost_basis=7500,
            current_price=155, annual_dividend=4.96,
            frequency=DividendFrequency.QUARTERLY, sector="Healthcare",
        ),
        DividendHolding(
            symbol="O", shares=200, cost_basis=10000,
            current_price=55, annual_dividend=3.08,
            frequency=DividendFrequency.MONTHLY, sector="Real Estate",
        ),
    ]


# =============================================================================
# Test Dividend Event
# =============================================================================

class TestDividendEvent:
    """Tests for DividendEvent model."""
    
    def test_change_pct(self, sample_event):
        """Test dividend change percentage."""
        # (0.24 - 0.23) / 0.23 = 4.35%
        assert sample_event.change_pct == pytest.approx(0.0435, rel=0.01)
    
    def test_annual_amount(self, sample_event):
        """Test annualized dividend."""
        # Quarterly: 0.24 * 4 = 0.96
        assert sample_event.annual_amount == pytest.approx(0.96, rel=0.01)


# =============================================================================
# Test Dividend Holding
# =============================================================================

class TestDividendHolding:
    """Tests for DividendHolding model."""
    
    def test_market_value(self, sample_holding):
        """Test market value calculation."""
        assert sample_holding.market_value == 18500  # 100 * 185
    
    def test_annual_income(self, sample_holding):
        """Test annual income calculation."""
        assert sample_holding.annual_income == 96  # 100 * 0.96
    
    def test_current_yield(self, sample_holding):
        """Test current yield calculation."""
        # 0.96 / 185 = 0.52%
        assert sample_holding.current_yield == pytest.approx(0.0052, rel=0.01)
    
    def test_yield_on_cost(self, sample_holding):
        """Test yield on cost calculation."""
        # 0.96 / 150 = 0.64%
        assert sample_holding.yield_on_cost == pytest.approx(0.0064, rel=0.01)


# =============================================================================
# Test Dividend Calendar
# =============================================================================

class TestDividendCalendar:
    """Tests for DividendCalendar."""
    
    def test_add_event(self, sample_event):
        """Test adding an event."""
        calendar = DividendCalendar()
        calendar.add_event(sample_event)
        
        retrieved = calendar.get_event(sample_event.event_id)
        assert retrieved is not None
        assert retrieved.symbol == "AAPL"
    
    def test_get_upcoming_ex_dates(self, sample_event):
        """Test getting upcoming ex-dates."""
        calendar = DividendCalendar()
        calendar.add_event(sample_event)
        
        upcoming = calendar.get_upcoming_ex_dates(days=30)
        assert len(upcoming) == 1
    
    def test_get_next_ex_date(self, sample_event):
        """Test getting next ex-date for symbol."""
        calendar = DividendCalendar()
        calendar.add_event(sample_event)
        
        next_event = calendar.get_next_ex_date("AAPL")
        assert next_event is not None
        assert next_event.symbol == "AAPL"
    
    def test_generate_sample_calendar(self):
        """Test sample calendar generation."""
        calendar = generate_sample_calendar()
        
        upcoming = calendar.get_upcoming_ex_dates(days=30)
        assert len(upcoming) >= 5


# =============================================================================
# Test Income Projector
# =============================================================================

class TestIncomeProjector:
    """Tests for IncomeProjector."""
    
    def test_project_holding(self, sample_holding):
        """Test projecting single holding income."""
        projector = IncomeProjector()
        
        income = projector.project_holding(sample_holding)
        
        assert income.annual_income == 96
        assert len(income.monthly_income) == 12
    
    def test_project_portfolio(self, sample_holdings):
        """Test projecting portfolio income."""
        projector = IncomeProjector()
        
        portfolio_income = projector.project_portfolio(sample_holdings)
        
        # AAPL: 100 * 0.96 = 96
        # JNJ: 50 * 4.96 = 248
        # O: 200 * 3.08 = 616
        # Total: 960
        assert portfolio_income.annual_income == pytest.approx(960, rel=0.01)
        assert len(portfolio_income.income_by_symbol) == 3
    
    def test_identify_income_gaps(self, sample_holdings):
        """Test identifying low-income months."""
        projector = IncomeProjector()
        
        portfolio_income = projector.project_portfolio(sample_holdings)
        gaps = projector.identify_income_gaps(portfolio_income)
        
        # Should identify months with low income
        assert isinstance(gaps, list)


# =============================================================================
# Test Safety Analyzer
# =============================================================================

class TestSafetyAnalyzer:
    """Tests for SafetyAnalyzer."""
    
    def test_analyze_safety(self):
        """Test safety analysis."""
        analyzer = SafetyAnalyzer()
        
        metrics = FinancialMetrics(
            eps=5.0,
            dividend_per_share=2.0,
            free_cash_flow=10e9,
            total_dividends_paid=4e9,
            shares_outstanding=2e9,
            total_debt=20e9,
            ebitda=15e9,
            interest_expense=1e9,
            current_assets=30e9,
            current_liabilities=15e9,
        )
        
        safety = analyzer.analyze("TEST", metrics)
        
        assert safety.payout_ratio == 0.4  # 2/5
        assert safety.coverage_ratio == 2.5  # 5/2
        assert safety.safety_score > 0
    
    def test_safety_rating(self):
        """Test safety rating determination."""
        analyzer = SafetyAnalyzer()
        
        # Very safe company
        metrics = FinancialMetrics(
            eps=10.0,
            dividend_per_share=2.0,  # 20% payout
            free_cash_flow=20e9,
            shares_outstanding=1e9,
            total_debt=10e9,
            ebitda=20e9,
            interest_expense=0.5e9,
        )
        
        safety = analyzer.analyze("SAFE", metrics)
        
        assert safety.safety_rating in [SafetyRating.VERY_SAFE, SafetyRating.SAFE]


# =============================================================================
# Test Growth Analyzer
# =============================================================================

class TestGrowthAnalyzer:
    """Tests for GrowthAnalyzer."""
    
    def test_analyze_growth(self):
        """Test growth analysis."""
        analyzer = GrowthAnalyzer()
        
        history = [
            DividendRecord(symbol="TEST", year=2020, amount=1.00),
            DividendRecord(symbol="TEST", year=2021, amount=1.05),
            DividendRecord(symbol="TEST", year=2022, amount=1.10),
            DividendRecord(symbol="TEST", year=2023, amount=1.16),
            DividendRecord(symbol="TEST", year=2024, amount=1.22),
        ]
        
        growth = analyzer.analyze("TEST", history, 1.22)
        
        assert growth.consecutive_increases >= 4
        assert growth.cagr_1y > 0
    
    def test_dividend_status(self):
        """Test dividend aristocrat/king status."""
        analyzer = GrowthAnalyzer()
        
        # Mock 30-year history for aristocrat
        growth = analyzer.analyze("TEST", [], 2.0)
        growth.consecutive_increases = 30
        growth.status = analyzer._determine_status(30)
        
        assert growth.status == DividendStatus.ARISTOCRAT
    
    def test_generate_sample_growth(self):
        """Test sample growth data generation."""
        analyzer = generate_sample_growth_data()
        
        jnj = analyzer.get_growth("JNJ")
        assert jnj is not None
        assert jnj.status == DividendStatus.KING


# =============================================================================
# Test DRIP Simulator
# =============================================================================

class TestDRIPSimulator:
    """Tests for DRIPSimulator."""
    
    def test_simulate_drip(self):
        """Test DRIP simulation."""
        simulator = DRIPSimulator()
        
        result = simulator.simulate(
            symbol="KO",
            initial_shares=100,
            initial_price=60.0,
            initial_dividend=1.84,
            years=10,
            dividend_growth_rate=0.05,
            price_growth_rate=0.07,
        )
        
        assert result.final_shares > 100
        assert result.final_value > result.initial_investment
        assert len(result.yearly_projections) == 10
    
    def test_compare_scenarios(self):
        """Test DRIP vs no-DRIP comparison."""
        simulator = DRIPSimulator()
        
        comparison = simulator.compare_scenarios(
            symbol="KO",
            initial_shares=100,
            initial_price=60.0,
            initial_dividend=1.84,
            years=10,
        )
        
        assert "with_drip" in comparison
        assert "without_drip" in comparison
        assert comparison["with_drip"]["final_shares"] > comparison["without_drip"]["final_shares"]
    
    def test_doubling_time(self):
        """Test income doubling time calculation."""
        simulator = DRIPSimulator()
        
        result = simulator.calculate_doubling_time(
            dividend_growth_rate=0.07,
            current_yield=0.03,
        )
        
        assert result["combined_growth_rate"] == 0.10
        assert result["rule_72_years"] == pytest.approx(7.2, rel=0.1)


# =============================================================================
# Test Tax Analyzer
# =============================================================================

class TestTaxAnalyzer:
    """Tests for TaxAnalyzer."""
    
    def test_analyze_portfolio(self, sample_holdings):
        """Test portfolio tax analysis."""
        analyzer = TaxAnalyzer()
        
        analysis = analyzer.analyze_portfolio(
            sample_holdings,
            tax_year=2024,
            taxable_income=100000,
        )
        
        assert analysis.total_dividend_income > 0
        assert analysis.total_estimated_tax > 0
        assert analysis.after_tax_income < analysis.total_dividend_income
    
    def test_compare_qualified_vs_ordinary(self):
        """Test qualified vs ordinary comparison."""
        analyzer = TaxAnalyzer()
        
        comparison = analyzer.compare_qualified_vs_ordinary(
            dividend_income=10000,
            taxable_income=100000,
        )
        
        assert comparison["tax_if_qualified"] < comparison["tax_if_ordinary"]
        assert comparison["tax_savings"] > 0
    
    def test_estimate_annual_tax(self):
        """Test quick tax estimate."""
        analyzer = TaxAnalyzer()
        
        estimate = analyzer.estimate_annual_tax(
            annual_dividend_income=5000,
            pct_qualified=0.90,
            taxable_income=100000,
        )
        
        assert estimate["gross_income"] == 5000
        assert estimate["after_tax_income"] < 5000
        assert estimate["effective_rate"] > 0
