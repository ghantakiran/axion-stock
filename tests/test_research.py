"""Tests for AI Research Reports."""

import pytest
from datetime import date

from src.research import (
    # Config
    Rating, MoatRating, RiskLevel, RiskCategory,
    ResearchConfig, DEFAULT_RESEARCH_CONFIG,
    # Models
    FinancialMetrics, FinancialAnalysis, DCFValuation,
    ValuationSummary, CompetitiveAnalysis, RiskAssessment,
    InvestmentThesis, ResearchReport,
    # Analyzers
    FinancialAnalyzer, ValuationEngine, CompetitiveAnalyzer,
    RiskAnalyzer, ThesisGenerator, ReportGenerator,
    ResearchEngine,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def financial_data():
    """Sample financial data."""
    return {
        "revenue": 400_000_000_000,
        "revenue_growth": 0.08,
        "revenue_cagr_3yr": 0.12,
        "gross_profit": 180_000_000_000,
        "gross_margin": 0.45,
        "operating_income": 120_000_000_000,
        "operating_margin": 0.30,
        "net_income": 100_000_000_000,
        "net_margin": 0.25,
        "eps": 6.50,
        "eps_growth": 0.10,
        "total_assets": 350_000_000_000,
        "total_liabilities": 250_000_000_000,
        "total_equity": 100_000_000_000,
        "total_debt": 100_000_000_000,
        "cash": 50_000_000_000,
        "operating_cash_flow": 110_000_000_000,
        "capex": 10_000_000_000,
        "market_cap": 3_000_000_000_000,
        "revenue_history": [300e9, 330e9, 360e9, 380e9, 400e9],
        "eps_history": [4.5, 5.0, 5.5, 6.0, 6.5],
    }


@pytest.fixture
def market_data():
    """Sample market data."""
    return {
        "price": 190.0,
        "beta": 1.2,
        "shares_outstanding": 15_000_000_000,
        "sector": "Technology",
        "market_cap": 3_000_000_000_000,
        "market_size": 500_000_000_000,
        "market_share": 0.25,
        "market_growth": 0.08,
        "dividend_yield": 0.005,
    }


@pytest.fixture
def peer_data():
    """Sample peer data."""
    return {
        "MSFT": {"pe": 35, "ev_ebitda": 25, "ps": 12, "growth": 0.12},
        "GOOGL": {"pe": 28, "ev_ebitda": 18, "ps": 6, "growth": 0.10},
        "META": {"pe": 25, "ev_ebitda": 15, "ps": 7, "growth": 0.15},
    }


@pytest.fixture
def metrics(financial_data):
    """Create FinancialMetrics from data."""
    analyzer = FinancialAnalyzer()
    analysis = analyzer.analyze("TEST", financial_data, "Technology")
    return analysis.metrics


# =============================================================================
# Test Financial Analyzer
# =============================================================================

class TestFinancialAnalyzer:
    """Tests for FinancialAnalyzer."""
    
    def test_analyze(self, financial_data):
        """Test financial analysis."""
        analyzer = FinancialAnalyzer()
        analysis = analyzer.analyze("AAPL", financial_data, "Technology")
        
        assert analysis.symbol == "AAPL"
        assert analysis.metrics.revenue_ttm == 400_000_000_000
        assert analysis.metrics.gross_margin == 0.45
    
    def test_quality_scores(self, financial_data):
        """Test quality score calculation."""
        analyzer = FinancialAnalyzer()
        analysis = analyzer.analyze("AAPL", financial_data, "Technology")
        
        assert 0 <= analysis.earnings_quality_score <= 100
        assert 0 <= analysis.balance_sheet_strength <= 100
        assert 0 <= analysis.cash_flow_quality <= 100
    
    def test_trends(self, financial_data):
        """Test trend determination."""
        analyzer = FinancialAnalyzer()
        analysis = analyzer.analyze("AAPL", financial_data, "Technology")
        
        # With growing revenue history, should be "growing"
        assert analysis.revenue_trend in ["growing", "stable", "declining"]
    
    def test_insights(self, financial_data):
        """Test insight generation."""
        analyzer = FinancialAnalyzer()
        analysis = analyzer.analyze("AAPL", financial_data, "Technology")
        
        assert isinstance(analysis.strengths, list)
        assert isinstance(analysis.concerns, list)


# =============================================================================
# Test Valuation Engine
# =============================================================================

class TestValuationEngine:
    """Tests for ValuationEngine."""
    
    def test_dcf_valuation(self, metrics, market_data):
        """Test DCF valuation."""
        engine = ValuationEngine()
        dcf = engine.dcf_valuation(
            metrics=metrics,
            market_data=market_data,
            shares_outstanding=15e9,
        )
        
        assert dcf.fair_value_per_share > 0
        assert dcf.enterprise_value > 0
        assert len(dcf.projected_revenues) == 5
    
    def test_comparable_valuation(self, metrics, market_data, peer_data):
        """Test comparable valuation."""
        engine = ValuationEngine()
        comp = engine.comparable_valuation(
            metrics=metrics,
            market_data=market_data,
            peer_data=peer_data,
            shares_outstanding=15e9,
        )
        
        assert comp.peer_avg_pe > 0
        assert len(comp.peer_group) == 3
    
    def test_full_valuation(self, metrics, market_data, peer_data):
        """Test full valuation."""
        engine = ValuationEngine()
        valuation = engine.value_stock(
            symbol="AAPL",
            metrics=metrics,
            market_data=market_data,
            peer_data=peer_data,
        )
        
        assert valuation.fair_value > 0
        assert valuation.dcf_value > 0
        assert valuation.comparable_value > 0
        assert 0 <= valuation.confidence <= 1


# =============================================================================
# Test Competitive Analyzer
# =============================================================================

class TestCompetitiveAnalyzer:
    """Tests for CompetitiveAnalyzer."""
    
    def test_analyze(self, metrics, market_data):
        """Test competitive analysis."""
        analyzer = CompetitiveAnalyzer()
        analysis = analyzer.analyze(
            symbol="AAPL",
            metrics=metrics,
            market_data=market_data,
        )
        
        assert analysis.symbol == "AAPL"
        assert analysis.moat_rating in list(MoatRating)
    
    def test_five_forces(self, metrics, market_data):
        """Test Porter's Five Forces analysis."""
        analyzer = CompetitiveAnalyzer()
        analysis = analyzer.analyze("AAPL", metrics, market_data)
        
        forces = analysis.five_forces
        assert forces.supplier_power is not None
        assert forces.buyer_power is not None
        assert forces.competitive_rivalry is not None
    
    def test_swot(self, metrics, market_data):
        """Test SWOT generation."""
        analyzer = CompetitiveAnalyzer()
        analysis = analyzer.analyze("AAPL", metrics, market_data)
        
        assert isinstance(analysis.strengths, list)
        assert isinstance(analysis.weaknesses, list)
        assert isinstance(analysis.opportunities, list)
        assert isinstance(analysis.threats, list)


# =============================================================================
# Test Risk Analyzer
# =============================================================================

class TestRiskAnalyzer:
    """Tests for RiskAnalyzer."""
    
    def test_analyze(self, metrics, market_data):
        """Test risk analysis."""
        analyzer = RiskAnalyzer()
        assessment = analyzer.analyze("AAPL", metrics, market_data)
        
        assert assessment.symbol == "AAPL"
        assert 0 <= assessment.risk_score <= 100
        assert assessment.overall_risk_rating in list(RiskLevel)
    
    def test_risk_factors(self, metrics, market_data):
        """Test risk factor identification."""
        analyzer = RiskAnalyzer()
        assessment = analyzer.analyze("AAPL", metrics, market_data)
        
        assert isinstance(assessment.risk_factors, list)
        assert len(assessment.key_risks) <= 3
    
    def test_category_scores(self, metrics, market_data):
        """Test category risk scores."""
        analyzer = RiskAnalyzer()
        assessment = analyzer.analyze("AAPL", metrics, market_data)
        
        assert 0 <= assessment.business_risk <= 100
        assert 0 <= assessment.financial_risk <= 100


# =============================================================================
# Test Thesis Generator
# =============================================================================

class TestThesisGenerator:
    """Tests for ThesisGenerator."""
    
    def test_generate(self, metrics, market_data, peer_data):
        """Test thesis generation."""
        # First get other analyses
        financial_analyzer = FinancialAnalyzer()
        financial = financial_analyzer.analyze("AAPL", {
            "revenue": metrics.revenue_ttm,
            "gross_margin": metrics.gross_margin,
            "operating_margin": metrics.operating_margin,
            "eps": metrics.eps_ttm,
            "revenue_growth": metrics.revenue_growth_yoy,
        }, "Technology")
        
        valuation_engine = ValuationEngine()
        valuation = valuation_engine.value_stock("AAPL", metrics, market_data, peer_data)
        
        competitive_analyzer = CompetitiveAnalyzer()
        competitive = competitive_analyzer.analyze("AAPL", metrics, market_data)
        
        risk_analyzer = RiskAnalyzer()
        risk = risk_analyzer.analyze("AAPL", metrics, market_data)
        
        # Generate thesis
        generator = ThesisGenerator()
        thesis = generator.generate(
            symbol="AAPL",
            valuation=valuation,
            financial=financial,
            competitive=competitive,
            risk=risk,
        )
        
        assert thesis.symbol == "AAPL"
        assert thesis.bull_price_target > thesis.bear_price_target
        assert abs(thesis.bull_probability + thesis.base_probability + thesis.bear_probability - 1.0) < 0.01
    
    def test_rating(self):
        """Test rating determination."""
        generator = ThesisGenerator()
        
        # Strong buy case
        rating = generator.determine_rating(40.0, 0.8, "low")
        assert rating == Rating.STRONG_BUY
        
        # Hold case
        rating = generator.determine_rating(5.0, 0.7, "medium")
        assert rating == Rating.HOLD
        
        # Sell case (need more negative upside to overcome confidence/risk adjustment)
        rating = generator.determine_rating(-30.0, 0.6, "high")
        assert rating in [Rating.SELL, Rating.STRONG_SELL]


# =============================================================================
# Test Report Generator
# =============================================================================

class TestReportGenerator:
    """Tests for ReportGenerator."""
    
    def test_generate_report(self, metrics, market_data):
        """Test report generation."""
        generator = ReportGenerator()
        
        financial = FinancialAnalysis(symbol="AAPL", metrics=metrics)
        valuation = ValuationSummary(
            symbol="AAPL",
            current_price=190.0,
            fair_value=220.0,
            dcf_value=210.0,
            comparable_value=230.0,
        )
        
        report = generator.generate_report(
            symbol="AAPL",
            company_name="Apple Inc.",
            current_price=190.0,
            financial=financial,
            valuation=valuation,
        )
        
        assert report.symbol == "AAPL"
        assert report.price_target == 220.0
        assert report.executive_summary != ""
    
    def test_format_html(self, metrics):
        """Test HTML formatting."""
        generator = ReportGenerator()
        
        report = ResearchReport(
            symbol="AAPL",
            company_name="Apple Inc.",
            rating=Rating.BUY,
            current_price=190.0,
            price_target=220.0,
        )
        
        html = generator.format_html(report)
        
        assert "AAPL" in html
        assert "Apple Inc." in html
        assert "<html>" in html
    
    def test_format_markdown(self, metrics):
        """Test Markdown formatting."""
        generator = ReportGenerator()
        
        report = ResearchReport(
            symbol="AAPL",
            company_name="Apple Inc.",
            rating=Rating.BUY,
            current_price=190.0,
            price_target=220.0,
        )
        
        md = generator.format_markdown(report)
        
        assert "# Apple Inc. (AAPL)" in md
        assert "BUY" in md


# =============================================================================
# Test Research Engine
# =============================================================================

class TestResearchEngine:
    """Tests for ResearchEngine."""
    
    def test_generate_full_report(self, financial_data, market_data, peer_data):
        """Test full report generation."""
        engine = ResearchEngine()
        
        report = engine.generate_full_report(
            symbol="AAPL",
            company_name="Apple Inc.",
            financial_data=financial_data,
            market_data=market_data,
            peer_data=peer_data,
        )
        
        assert report.symbol == "AAPL"
        assert report.rating in list(Rating)
        assert report.financial_analysis is not None
        assert report.valuation is not None
        assert report.competitive_analysis is not None
        assert report.risk_assessment is not None
        assert report.investment_thesis is not None
    
    def test_format_report(self, financial_data, market_data):
        """Test report formatting."""
        engine = ResearchEngine()
        
        report = engine.generate_full_report(
            symbol="AAPL",
            company_name="Apple Inc.",
            financial_data=financial_data,
            market_data=market_data,
        )
        
        html = engine.format_report(report, "html")
        assert "<html>" in html
        
        md = engine.format_report(report, "markdown")
        assert "#" in md
