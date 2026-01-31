"""Competitive Analysis Module.

Analyzes competitive position, moat, and market dynamics.
"""

from typing import Optional
import logging

from src.research.config import (
    ResearchConfig,
    DEFAULT_RESEARCH_CONFIG,
    MoatRating,
    MoatTrend,
    ForceRating,
)
from src.research.models import (
    CompetitiveAnalysis,
    CompetitorProfile,
    PortersFiveForces,
    FinancialMetrics,
)

logger = logging.getLogger(__name__)


class CompetitiveAnalyzer:
    """Analyzes competitive position and moat.
    
    Features:
    - Moat assessment
    - Porter's Five Forces
    - SWOT analysis
    - Competitor profiling
    
    Example:
        analyzer = CompetitiveAnalyzer()
        analysis = analyzer.analyze(symbol, metrics, market_data, competitors)
    """
    
    def __init__(self, config: Optional[ResearchConfig] = None):
        self.config = config or DEFAULT_RESEARCH_CONFIG
    
    def analyze(
        self,
        symbol: str,
        metrics: FinancialMetrics,
        market_data: dict,
        competitor_data: Optional[dict] = None,
    ) -> CompetitiveAnalysis:
        """Perform competitive analysis.
        
        Args:
            symbol: Stock symbol.
            metrics: Financial metrics.
            market_data: Market and industry data.
            competitor_data: Competitor information.
            
        Returns:
            CompetitiveAnalysis object.
        """
        analysis = CompetitiveAnalysis(symbol=symbol)
        
        # Market position
        analysis.market_size = market_data.get("market_size", 0)
        analysis.market_share = market_data.get("market_share", 0)
        analysis.market_growth_rate = market_data.get("market_growth", 0)
        analysis.market_position = self._determine_market_position(
            market_data.get("market_share", 0),
            market_data.get("market_cap_rank", 5),
        )
        
        # Competitor profiles
        if competitor_data:
            analysis.competitors = self._build_competitor_profiles(competitor_data)
        
        # Moat analysis
        moat_rating, moat_sources = self._assess_moat(metrics, market_data)
        analysis.moat_rating = moat_rating
        analysis.moat_sources = moat_sources
        analysis.moat_trend = self._assess_moat_trend(metrics, market_data)
        
        # Porter's Five Forces
        analysis.five_forces = self._analyze_five_forces(market_data)
        
        # SWOT
        swot = self._generate_swot(metrics, market_data, analysis)
        analysis.strengths = swot["strengths"]
        analysis.weaknesses = swot["weaknesses"]
        analysis.opportunities = swot["opportunities"]
        analysis.threats = swot["threats"]
        
        return analysis
    
    def _determine_market_position(
        self,
        market_share: float,
        market_cap_rank: int,
    ) -> str:
        """Determine market position category."""
        if market_share > 0.30 or market_cap_rank == 1:
            return "leader"
        elif market_share > 0.15 or market_cap_rank <= 3:
            return "challenger"
        elif market_share > 0.05:
            return "follower"
        return "niche"
    
    def _build_competitor_profiles(
        self,
        competitor_data: dict,
    ) -> list[CompetitorProfile]:
        """Build competitor profiles from data."""
        profiles = []
        
        for symbol, data in competitor_data.items():
            if isinstance(data, dict):
                profile = CompetitorProfile(
                    symbol=symbol,
                    name=data.get("name", symbol),
                    market_cap=data.get("market_cap", 0),
                    revenue=data.get("revenue", 0),
                    market_share=data.get("market_share", 0),
                    strengths=data.get("strengths", []),
                    weaknesses=data.get("weaknesses", []),
                )
                profiles.append(profile)
        
        return profiles
    
    def _assess_moat(
        self,
        metrics: FinancialMetrics,
        market_data: dict,
    ) -> tuple[MoatRating, list[str]]:
        """Assess economic moat."""
        moat_sources = []
        moat_score = 0
        
        # High ROIC suggests competitive advantage
        if metrics.roic > 0.20:
            moat_score += 3
            moat_sources.append("High return on invested capital")
        elif metrics.roic > 0.15:
            moat_score += 2
        
        # Consistent high margins
        if metrics.gross_margin > 0.50:
            moat_score += 2
            moat_sources.append("Premium pricing power")
        elif metrics.gross_margin > 0.40:
            moat_score += 1
        
        # Network effects (from market data)
        if market_data.get("has_network_effects", False):
            moat_score += 3
            moat_sources.append("Network effects")
        
        # Switching costs
        if market_data.get("high_switching_costs", False):
            moat_score += 2
            moat_sources.append("High switching costs")
        
        # Brand strength
        if market_data.get("brand_value", 0) > 0:
            moat_score += 2
            moat_sources.append("Strong brand")
        
        # Scale advantages
        if market_data.get("market_share", 0) > 0.25:
            moat_score += 2
            moat_sources.append("Economies of scale")
        
        # Intellectual property
        if market_data.get("patents", 0) > 100:
            moat_score += 1
            moat_sources.append("Intellectual property")
        
        # Regulatory advantages
        if market_data.get("regulatory_moat", False):
            moat_score += 2
            moat_sources.append("Regulatory barriers")
        
        # Determine rating
        if moat_score >= 8:
            rating = MoatRating.WIDE
        elif moat_score >= 4:
            rating = MoatRating.NARROW
        else:
            rating = MoatRating.NONE
        
        return rating, moat_sources
    
    def _assess_moat_trend(
        self,
        metrics: FinancialMetrics,
        market_data: dict,
    ) -> MoatTrend:
        """Assess moat trend."""
        # Check margin trends
        margin_improving = market_data.get("margin_trend", "stable") == "improving"
        market_share_growing = market_data.get("market_share_trend", 0) > 0
        roic_stable = metrics.roic > 0.12
        
        if margin_improving and market_share_growing:
            return MoatTrend.STRENGTHENING
        elif not roic_stable or market_data.get("competitive_pressure", False):
            return MoatTrend.WEAKENING
        
        return MoatTrend.STABLE
    
    def _analyze_five_forces(self, market_data: dict) -> PortersFiveForces:
        """Analyze Porter's Five Forces."""
        forces = PortersFiveForces()
        
        # Supplier power
        supplier_concentration = market_data.get("supplier_concentration", 0.3)
        if supplier_concentration > 0.6:
            forces.supplier_power = ForceRating.HIGH
            forces.supplier_power_factors.append("Concentrated supplier base")
        elif supplier_concentration < 0.2:
            forces.supplier_power = ForceRating.LOW
            forces.supplier_power_factors.append("Fragmented supplier base")
        else:
            forces.supplier_power = ForceRating.MODERATE
        
        # Buyer power
        buyer_concentration = market_data.get("buyer_concentration", 0.3)
        if buyer_concentration > 0.5:
            forces.buyer_power = ForceRating.HIGH
            forces.buyer_power_factors.append("Concentrated customer base")
        elif market_data.get("b2c", False):
            forces.buyer_power = ForceRating.LOW
            forces.buyer_power_factors.append("Fragmented consumer base")
        else:
            forces.buyer_power = ForceRating.MODERATE
        
        # Competitive rivalry
        num_competitors = market_data.get("num_major_competitors", 5)
        market_growth = market_data.get("market_growth", 0.05)
        
        if num_competitors > 10 and market_growth < 0.03:
            forces.competitive_rivalry = ForceRating.VERY_HIGH
            forces.rivalry_factors.append("Fragmented, slow-growth market")
        elif num_competitors < 4:
            forces.competitive_rivalry = ForceRating.MODERATE
            forces.rivalry_factors.append("Oligopolistic market structure")
        else:
            forces.competitive_rivalry = ForceRating.HIGH
        
        # Threat of substitutes
        if market_data.get("substitute_threat", False):
            forces.threat_of_substitutes = ForceRating.HIGH
            forces.substitute_factors.append("Viable alternatives exist")
        else:
            forces.threat_of_substitutes = ForceRating.MODERATE
        
        # Threat of new entrants
        capital_intensity = market_data.get("capital_intensity", 0.5)
        regulatory_barriers = market_data.get("regulatory_barriers", False)
        
        if capital_intensity > 0.7 or regulatory_barriers:
            forces.threat_of_new_entrants = ForceRating.LOW
            forces.entry_barrier_factors.append("High barriers to entry")
        elif capital_intensity < 0.2:
            forces.threat_of_new_entrants = ForceRating.HIGH
            forces.entry_barrier_factors.append("Low capital requirements")
        else:
            forces.threat_of_new_entrants = ForceRating.MODERATE
        
        return forces
    
    def _generate_swot(
        self,
        metrics: FinancialMetrics,
        market_data: dict,
        analysis: CompetitiveAnalysis,
    ) -> dict:
        """Generate SWOT analysis."""
        strengths = []
        weaknesses = []
        opportunities = []
        threats = []
        
        # Strengths
        if analysis.moat_rating != MoatRating.NONE:
            strengths.append(f"{analysis.moat_rating.value.title()} economic moat")
        if metrics.gross_margin > 0.40:
            strengths.append("Strong gross margins")
        if metrics.roe > 0.15:
            strengths.append("High return on equity")
        if analysis.market_position == "leader":
            strengths.append("Market leadership position")
        if metrics.debt_to_equity < 0.5:
            strengths.append("Strong balance sheet")
        if metrics.fcf_margin > 0.10:
            strengths.append("Strong cash generation")
        
        # Weaknesses
        if metrics.debt_to_equity > 1.5:
            weaknesses.append("High leverage")
        if metrics.operating_margin < 0.10:
            weaknesses.append("Low operating margins")
        if metrics.revenue_growth_yoy < 0:
            weaknesses.append("Declining revenue")
        if analysis.market_position == "niche":
            weaknesses.append("Limited market presence")
        if metrics.roe < 0.08:
            weaknesses.append("Below-average returns")
        
        # Opportunities
        if market_data.get("market_growth", 0) > 0.10:
            opportunities.append("Fast-growing addressable market")
        if market_data.get("international_expansion", False):
            opportunities.append("International expansion potential")
        if market_data.get("m_and_a_opportunity", False):
            opportunities.append("Strategic M&A opportunities")
        if market_data.get("new_products", False):
            opportunities.append("New product pipeline")
        opportunities.append("Digital transformation initiatives")
        
        # Threats
        if analysis.five_forces.competitive_rivalry in [ForceRating.HIGH, ForceRating.VERY_HIGH]:
            threats.append("Intense competitive pressure")
        if analysis.five_forces.threat_of_new_entrants == ForceRating.HIGH:
            threats.append("Low barriers to entry")
        if market_data.get("regulatory_risk", False):
            threats.append("Regulatory headwinds")
        if market_data.get("disruption_risk", False):
            threats.append("Technology disruption risk")
        threats.append("Macroeconomic uncertainty")
        
        return {
            "strengths": strengths[:5],
            "weaknesses": weaknesses[:5],
            "opportunities": opportunities[:5],
            "threats": threats[:5],
        }
