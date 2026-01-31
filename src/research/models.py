"""AI Research Reports Data Models.

Dataclasses for research reports, analysis components, and valuations.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Any, Optional
import uuid

from src.research.config import (
    Rating,
    MoatRating,
    MoatTrend,
    RiskLevel,
    RiskCategory,
    ValuationMethod,
    ReportType,
    ForceRating,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


# =============================================================================
# Company Overview Models
# =============================================================================

@dataclass
class BusinessSegment:
    """Business segment information."""
    name: str
    description: str
    revenue: float
    revenue_pct: float
    growth_rate: float
    margin: Optional[float] = None


@dataclass
class CompanyOverview:
    """Company overview and business description."""
    symbol: str
    name: str
    description: str
    
    # Classification
    sector: str = ""
    industry: str = ""
    sub_industry: str = ""
    
    # Business segments
    segments: list[BusinessSegment] = field(default_factory=list)
    revenue_by_geography: dict[str, float] = field(default_factory=dict)
    
    # Key facts
    founded: Optional[int] = None
    headquarters: str = ""
    employees: int = 0
    website: str = ""
    
    # Management
    ceo: str = ""
    cfo: str = ""
    management_tenure_years: float = 0.0
    insider_ownership_pct: float = 0.0


# =============================================================================
# Financial Analysis Models
# =============================================================================

@dataclass
class FinancialMetrics:
    """Core financial metrics."""
    # Income Statement
    revenue_ttm: float = 0.0
    revenue_growth_yoy: float = 0.0
    revenue_growth_3yr_cagr: float = 0.0
    gross_profit: float = 0.0
    gross_margin: float = 0.0
    operating_income: float = 0.0
    operating_margin: float = 0.0
    net_income: float = 0.0
    net_margin: float = 0.0
    eps_ttm: float = 0.0
    eps_growth_yoy: float = 0.0
    
    # Balance Sheet
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    total_equity: float = 0.0
    total_debt: float = 0.0
    cash_and_equivalents: float = 0.0
    net_debt: float = 0.0
    debt_to_equity: float = 0.0
    debt_to_ebitda: float = 0.0
    current_ratio: float = 0.0
    quick_ratio: float = 0.0
    
    # Cash Flow
    operating_cash_flow: float = 0.0
    capital_expenditures: float = 0.0
    free_cash_flow: float = 0.0
    fcf_margin: float = 0.0
    fcf_yield: float = 0.0
    
    # Returns
    roe: float = 0.0
    roa: float = 0.0
    roic: float = 0.0
    roce: float = 0.0


@dataclass
class FinancialAnalysis:
    """Complete financial analysis."""
    symbol: str
    metrics: FinancialMetrics = field(default_factory=FinancialMetrics)
    
    # Historical data
    revenue_history: list[float] = field(default_factory=list)
    eps_history: list[float] = field(default_factory=list)
    margin_history: dict[str, list[float]] = field(default_factory=dict)
    
    # Quality scores (0-100)
    earnings_quality_score: float = 50.0
    balance_sheet_strength: float = 50.0
    cash_flow_quality: float = 50.0
    overall_financial_health: float = 50.0
    
    # Trends
    revenue_trend: str = "stable"  # growing, stable, declining
    margin_trend: str = "stable"
    debt_trend: str = "stable"
    
    # Commentary
    strengths: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)


# =============================================================================
# Valuation Models
# =============================================================================

@dataclass
class DCFValuation:
    """Discounted Cash Flow valuation."""
    # Assumptions
    projection_years: int = 5
    revenue_growth_rates: list[float] = field(default_factory=list)
    terminal_growth_rate: float = 0.025
    operating_margin_target: float = 0.15
    tax_rate: float = 0.21
    wacc: float = 0.10
    
    # Projections
    projected_revenues: list[float] = field(default_factory=list)
    projected_ebit: list[float] = field(default_factory=list)
    projected_fcf: list[float] = field(default_factory=list)
    
    # Valuation
    pv_fcf: float = 0.0
    terminal_value: float = 0.0
    pv_terminal_value: float = 0.0
    enterprise_value: float = 0.0
    equity_value: float = 0.0
    fair_value_per_share: float = 0.0
    
    # Sensitivity (WACC vs terminal growth)
    sensitivity_matrix: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class ComparableValuation:
    """Comparable company analysis."""
    peer_group: list[str] = field(default_factory=list)
    
    # Target multiples
    pe_ratio: float = 0.0
    ev_ebitda: float = 0.0
    ev_revenue: float = 0.0
    pb_ratio: float = 0.0
    ps_ratio: float = 0.0
    
    # Peer averages
    peer_avg_pe: float = 0.0
    peer_avg_ev_ebitda: float = 0.0
    peer_avg_ev_revenue: float = 0.0
    peer_avg_pb: float = 0.0
    peer_avg_ps: float = 0.0
    
    # Implied values
    implied_value_pe: float = 0.0
    implied_value_ev_ebitda: float = 0.0
    implied_value_ev_revenue: float = 0.0
    implied_value_pb: float = 0.0
    implied_value_ps: float = 0.0
    
    # Premium/discount
    premium_to_peers_pct: float = 0.0
    
    # Peer data
    peer_data: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class ValuationSummary:
    """Combined valuation summary."""
    symbol: str
    current_price: float = 0.0
    
    # Method results
    dcf_value: float = 0.0
    comparable_value: float = 0.0
    ddm_value: Optional[float] = None
    
    # Weighted fair value
    fair_value: float = 0.0
    upside_pct: float = 0.0
    
    # Confidence
    confidence: float = 0.5  # 0-1
    valuation_range_low: float = 0.0
    valuation_range_high: float = 0.0
    
    # Details
    dcf: Optional[DCFValuation] = None
    comparable: Optional[ComparableValuation] = None


# =============================================================================
# Competitive Analysis Models
# =============================================================================

@dataclass
class CompetitorProfile:
    """Competitor profile."""
    symbol: str
    name: str
    market_cap: float
    revenue: float
    market_share: float
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)


@dataclass
class PortersFiveForces:
    """Porter's Five Forces analysis."""
    supplier_power: ForceRating = ForceRating.MODERATE
    supplier_power_factors: list[str] = field(default_factory=list)
    
    buyer_power: ForceRating = ForceRating.MODERATE
    buyer_power_factors: list[str] = field(default_factory=list)
    
    competitive_rivalry: ForceRating = ForceRating.MODERATE
    rivalry_factors: list[str] = field(default_factory=list)
    
    threat_of_substitutes: ForceRating = ForceRating.MODERATE
    substitute_factors: list[str] = field(default_factory=list)
    
    threat_of_new_entrants: ForceRating = ForceRating.MODERATE
    entry_barrier_factors: list[str] = field(default_factory=list)


@dataclass
class CompetitiveAnalysis:
    """Complete competitive analysis."""
    symbol: str
    
    # Market position
    market_size: float = 0.0
    market_share: float = 0.0
    market_growth_rate: float = 0.0
    market_position: str = ""  # leader, challenger, follower, niche
    
    # Competitors
    competitors: list[CompetitorProfile] = field(default_factory=list)
    
    # Moat analysis
    moat_rating: MoatRating = MoatRating.NONE
    moat_sources: list[str] = field(default_factory=list)
    moat_trend: MoatTrend = MoatTrend.STABLE
    
    # Porter's Five Forces
    five_forces: PortersFiveForces = field(default_factory=PortersFiveForces)
    
    # SWOT
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)
    threats: list[str] = field(default_factory=list)


# =============================================================================
# Risk Assessment Models
# =============================================================================

@dataclass
class RiskFactor:
    """Individual risk factor."""
    risk_id: str = field(default_factory=_new_id)
    category: RiskCategory = RiskCategory.BUSINESS
    title: str = ""
    description: str = ""
    probability: RiskLevel = RiskLevel.MEDIUM
    impact: RiskLevel = RiskLevel.MEDIUM
    risk_score: float = 5.0  # 1-10
    mitigants: list[str] = field(default_factory=list)
    monitoring_indicators: list[str] = field(default_factory=list)


@dataclass
class RiskAssessment:
    """Complete risk assessment."""
    symbol: str
    
    # Overall rating
    overall_risk_rating: RiskLevel = RiskLevel.MEDIUM
    risk_score: float = 50.0  # 1-100
    
    # Risk factors
    risk_factors: list[RiskFactor] = field(default_factory=list)
    key_risks: list[str] = field(default_factory=list)  # Top 3
    
    # Category scores
    business_risk: float = 50.0
    financial_risk: float = 50.0
    operational_risk: float = 50.0
    regulatory_risk: float = 50.0
    
    # ESG risks
    esg_risk_score: float = 50.0
    environmental_risks: list[str] = field(default_factory=list)
    social_risks: list[str] = field(default_factory=list)
    governance_risks: list[str] = field(default_factory=list)


# =============================================================================
# Investment Thesis Models
# =============================================================================

@dataclass
class Catalyst:
    """Potential catalyst event."""
    catalyst_id: str = field(default_factory=_new_id)
    title: str = ""
    description: str = ""
    expected_date: Optional[date] = None
    timeframe: str = ""  # 'near_term', 'medium_term', 'long_term'
    impact: str = ""  # 'positive', 'negative', 'uncertain'
    probability: float = 0.5


@dataclass
class InvestmentThesis:
    """Investment thesis with bull/bear cases."""
    symbol: str
    
    # Bull case
    bull_case: str = ""
    bull_price_target: float = 0.0
    bull_probability: float = 0.25
    bull_catalysts: list[str] = field(default_factory=list)
    
    # Base case
    base_case: str = ""
    base_price_target: float = 0.0
    base_probability: float = 0.50
    
    # Bear case
    bear_case: str = ""
    bear_price_target: float = 0.0
    bear_probability: float = 0.25
    bear_risks: list[str] = field(default_factory=list)
    
    # Expected value
    expected_price: float = 0.0
    
    # Catalysts
    catalysts: list[Catalyst] = field(default_factory=list)
    
    # Key investment points
    reasons_to_buy: list[str] = field(default_factory=list)
    reasons_to_sell: list[str] = field(default_factory=list)


# =============================================================================
# Research Report Model
# =============================================================================

@dataclass
class ResearchReport:
    """Complete research report."""
    report_id: str = field(default_factory=_new_id)
    symbol: str = ""
    company_name: str = ""
    report_type: ReportType = ReportType.FULL
    generated_at: datetime = field(default_factory=_utc_now)
    
    # Rating and target
    rating: Rating = Rating.HOLD
    price_target: float = 0.0
    current_price: float = 0.0
    confidence: float = 0.5
    
    # Executive summary
    executive_summary: str = ""
    key_takeaways: list[str] = field(default_factory=list)
    
    # Sections
    company_overview: Optional[CompanyOverview] = None
    financial_analysis: Optional[FinancialAnalysis] = None
    valuation: Optional[ValuationSummary] = None
    competitive_analysis: Optional[CompetitiveAnalysis] = None
    risk_assessment: Optional[RiskAssessment] = None
    investment_thesis: Optional[InvestmentThesis] = None
    
    # Metadata
    analyst: str = "AI Research System"
    version: str = "1.0"
    
    @property
    def upside_pct(self) -> float:
        if self.current_price > 0:
            return (self.price_target - self.current_price) / self.current_price * 100
        return 0.0


# =============================================================================
# Peer Comparison Models
# =============================================================================

@dataclass
class PeerMetrics:
    """Metrics for peer comparison."""
    symbol: str
    name: str
    market_cap: float = 0.0
    
    # Valuation
    pe_ratio: float = 0.0
    ev_ebitda: float = 0.0
    ps_ratio: float = 0.0
    pb_ratio: float = 0.0
    
    # Growth
    revenue_growth: float = 0.0
    eps_growth: float = 0.0
    
    # Profitability
    gross_margin: float = 0.0
    operating_margin: float = 0.0
    net_margin: float = 0.0
    roe: float = 0.0
    roic: float = 0.0
    
    # Quality
    debt_to_equity: float = 0.0
    current_ratio: float = 0.0
    fcf_yield: float = 0.0


@dataclass
class PeerComparison:
    """Peer comparison analysis."""
    target_symbol: str
    peer_symbols: list[str] = field(default_factory=list)
    
    # All metrics
    metrics: dict[str, PeerMetrics] = field(default_factory=dict)
    
    # Rankings (1 = best)
    rankings: dict[str, dict[str, int]] = field(default_factory=dict)
    
    # Overall scores
    overall_scores: dict[str, float] = field(default_factory=dict)
    
    # Summary
    target_rank: int = 0
    target_percentile: float = 0.0
    
    generated_at: datetime = field(default_factory=_utc_now)
