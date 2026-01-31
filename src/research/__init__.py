"""AI Research Reports.

Comprehensive stock research report generation including:
- Automated stock analysis
- Financial statement analysis
- DCF and comparable valuations
- Competitive/moat analysis
- Risk assessment
- Investment thesis generation
- Professional report formatting

Example:
    from src.research import ResearchEngine
    
    engine = ResearchEngine()
    report = engine.generate_full_report("AAPL", financial_data, market_data)
    html = engine.format_report(report, format="html")
"""

from src.research.config import (
    Rating,
    MoatRating,
    MoatTrend,
    RiskLevel,
    RiskCategory,
    ValuationMethod,
    ReportType,
    OutputFormat,
    ForceRating,
    RATING_THRESHOLDS,
    SECTOR_MARGINS,
    DCFConfig,
    ComparableConfig,
    RiskConfig,
    ReportConfig,
    ResearchConfig,
    DEFAULT_RESEARCH_CONFIG,
)

from src.research.models import (
    BusinessSegment,
    CompanyOverview,
    FinancialMetrics,
    FinancialAnalysis,
    DCFValuation,
    ComparableValuation,
    ValuationSummary,
    CompetitorProfile,
    PortersFiveForces,
    CompetitiveAnalysis,
    RiskFactor,
    RiskAssessment,
    Catalyst,
    InvestmentThesis,
    ResearchReport,
    PeerMetrics,
    PeerComparison,
)

from src.research.financial import FinancialAnalyzer
from src.research.valuation import ValuationEngine
from src.research.competitive import CompetitiveAnalyzer
from src.research.risk import RiskAnalyzer
from src.research.thesis import ThesisGenerator
from src.research.report_generator import ReportGenerator


class ResearchEngine:
    """Main research engine combining all analysis modules.
    
    Example:
        engine = ResearchEngine()
        report = engine.generate_full_report("AAPL", data, market_data)
    """
    
    def __init__(self, config: ResearchConfig = None):
        self.config = config or DEFAULT_RESEARCH_CONFIG
        self.financial_analyzer = FinancialAnalyzer(self.config)
        self.valuation_engine = ValuationEngine(self.config)
        self.competitive_analyzer = CompetitiveAnalyzer(self.config)
        self.risk_analyzer = RiskAnalyzer(self.config)
        self.thesis_generator = ThesisGenerator(self.config)
        self.report_generator = ReportGenerator(self.config)
    
    def generate_full_report(
        self,
        symbol: str,
        company_name: str,
        financial_data: dict,
        market_data: dict,
        peer_data: dict = None,
        competitor_data: dict = None,
    ) -> ResearchReport:
        """Generate a complete research report.
        
        Args:
            symbol: Stock symbol.
            company_name: Company name.
            financial_data: Financial statement data.
            market_data: Market data (price, beta, etc.).
            peer_data: Peer company data for comparables.
            competitor_data: Competitor information.
            
        Returns:
            Complete ResearchReport.
        """
        # Financial analysis
        financial = self.financial_analyzer.analyze(
            symbol=symbol,
            data=financial_data,
            sector=market_data.get("sector", "Technology"),
        )
        
        # Valuation
        valuation = self.valuation_engine.value_stock(
            symbol=symbol,
            metrics=financial.metrics,
            market_data=market_data,
            peer_data=peer_data,
        )
        
        # Competitive analysis
        competitive = self.competitive_analyzer.analyze(
            symbol=symbol,
            metrics=financial.metrics,
            market_data=market_data,
            competitor_data=competitor_data,
        )
        
        # Risk assessment
        risk = self.risk_analyzer.analyze(
            symbol=symbol,
            metrics=financial.metrics,
            market_data=market_data,
        )
        
        # Investment thesis
        thesis = self.thesis_generator.generate(
            symbol=symbol,
            valuation=valuation,
            financial=financial,
            competitive=competitive,
            risk=risk,
            market_data=market_data,
        )
        
        # Generate report
        report = self.report_generator.generate_report(
            symbol=symbol,
            company_name=company_name,
            current_price=market_data.get("price", 0),
            financial=financial,
            valuation=valuation,
            competitive=competitive,
            risk=risk,
            thesis=thesis,
        )
        
        return report
    
    def format_report(self, report: ResearchReport, format: str = "html") -> str:
        """Format report to desired output format.
        
        Args:
            report: Research report.
            format: Output format ("html" or "markdown").
            
        Returns:
            Formatted string.
        """
        if format == "markdown":
            return self.report_generator.format_markdown(report)
        return self.report_generator.format_html(report)


__all__ = [
    # Config
    "Rating",
    "MoatRating",
    "MoatTrend",
    "RiskLevel",
    "RiskCategory",
    "ValuationMethod",
    "ReportType",
    "OutputFormat",
    "ForceRating",
    "RATING_THRESHOLDS",
    "SECTOR_MARGINS",
    "DCFConfig",
    "ComparableConfig",
    "RiskConfig",
    "ReportConfig",
    "ResearchConfig",
    "DEFAULT_RESEARCH_CONFIG",
    # Models
    "BusinessSegment",
    "CompanyOverview",
    "FinancialMetrics",
    "FinancialAnalysis",
    "DCFValuation",
    "ComparableValuation",
    "ValuationSummary",
    "CompetitorProfile",
    "PortersFiveForces",
    "CompetitiveAnalysis",
    "RiskFactor",
    "RiskAssessment",
    "Catalyst",
    "InvestmentThesis",
    "ResearchReport",
    "PeerMetrics",
    "PeerComparison",
    # Analyzers
    "FinancialAnalyzer",
    "ValuationEngine",
    "CompetitiveAnalyzer",
    "RiskAnalyzer",
    "ThesisGenerator",
    "ReportGenerator",
    # Main Engine
    "ResearchEngine",
]
