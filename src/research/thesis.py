"""Investment Thesis Generator.

Generates bull/bear cases and investment thesis.
"""

from datetime import date, timedelta
from typing import Optional
import logging

from src.research.config import (
    ResearchConfig,
    DEFAULT_RESEARCH_CONFIG,
    Rating,
    RATING_THRESHOLDS,
)
from src.research.models import (
    InvestmentThesis,
    Catalyst,
    ValuationSummary,
    FinancialAnalysis,
    CompetitiveAnalysis,
    RiskAssessment,
)

logger = logging.getLogger(__name__)


class ThesisGenerator:
    """Generates investment thesis and recommendations.
    
    Features:
    - Bull/bear/base case scenarios
    - Price target derivation
    - Catalyst identification
    - Buy/sell reasoning
    
    Example:
        generator = ThesisGenerator()
        thesis = generator.generate(symbol, valuation, financial, competitive, risk)
    """
    
    def __init__(self, config: Optional[ResearchConfig] = None):
        self.config = config or DEFAULT_RESEARCH_CONFIG
    
    def generate(
        self,
        symbol: str,
        valuation: ValuationSummary,
        financial: FinancialAnalysis,
        competitive: CompetitiveAnalysis,
        risk: RiskAssessment,
        market_data: Optional[dict] = None,
    ) -> InvestmentThesis:
        """Generate investment thesis.
        
        Args:
            symbol: Stock symbol.
            valuation: Valuation analysis.
            financial: Financial analysis.
            competitive: Competitive analysis.
            risk: Risk assessment.
            market_data: Additional market data.
            
        Returns:
            InvestmentThesis object.
        """
        market_data = market_data or {}
        thesis = InvestmentThesis(symbol=symbol)
        
        # Generate scenarios
        bull = self._generate_bull_case(valuation, financial, competitive)
        base = self._generate_base_case(valuation, financial)
        bear = self._generate_bear_case(valuation, financial, risk)
        
        thesis.bull_case = bull["narrative"]
        thesis.bull_price_target = bull["target"]
        thesis.bull_probability = bull["probability"]
        thesis.bull_catalysts = bull["catalysts"]
        
        thesis.base_case = base["narrative"]
        thesis.base_price_target = base["target"]
        thesis.base_probability = base["probability"]
        
        thesis.bear_case = bear["narrative"]
        thesis.bear_price_target = bear["target"]
        thesis.bear_probability = bear["probability"]
        thesis.bear_risks = bear["risks"]
        
        # Expected value (probability-weighted price)
        thesis.expected_price = (
            thesis.bull_price_target * thesis.bull_probability +
            thesis.base_price_target * thesis.base_probability +
            thesis.bear_price_target * thesis.bear_probability
        )
        
        # Identify catalysts
        thesis.catalysts = self._identify_catalysts(
            financial, competitive, market_data
        )
        
        # Generate buy/sell reasons
        thesis.reasons_to_buy = self._generate_buy_reasons(
            valuation, financial, competitive
        )
        thesis.reasons_to_sell = self._generate_sell_reasons(
            valuation, financial, risk
        )
        
        return thesis
    
    def determine_rating(
        self,
        upside_pct: float,
        confidence: float,
        risk_level: str,
    ) -> Rating:
        """Determine stock rating based on upside and risk.
        
        Args:
            upside_pct: Expected upside percentage.
            confidence: Confidence in valuation (0-1).
            risk_level: Risk level string.
            
        Returns:
            Rating enum.
        """
        # Adjust upside by confidence
        adjusted_upside = upside_pct * confidence
        
        # Risk adjustment
        risk_factor = {
            "low": 1.0,
            "medium": 0.9,
            "high": 0.75,
            "very_high": 0.5,
        }.get(risk_level, 0.85)
        
        final_upside = adjusted_upside * risk_factor / 100  # Convert to decimal
        
        # Determine rating
        for rating, threshold in sorted(
            RATING_THRESHOLDS.items(),
            key=lambda x: x[1],
            reverse=True
        ):
            if final_upside >= threshold:
                return rating
        
        return Rating.HOLD
    
    def _generate_bull_case(
        self,
        valuation: ValuationSummary,
        financial: FinancialAnalysis,
        competitive: CompetitiveAnalysis,
    ) -> dict:
        """Generate bull case scenario."""
        # Bull case target = upper end of valuation range + 20%
        base_value = valuation.valuation_range_high
        bull_target = base_value * 1.15 if base_value > 0 else valuation.fair_value * 1.30
        
        # Build narrative
        narratives = []
        catalysts = []
        
        if financial.metrics.revenue_growth_yoy > 0.10:
            narratives.append("accelerating revenue growth")
            catalysts.append("Continued market share gains")
        
        if competitive.moat_rating.value == "wide":
            narratives.append("wide economic moat")
            catalysts.append("Pricing power expansion")
        
        if financial.metrics.operating_margin < 0.20:
            narratives.append("margin expansion potential")
            catalysts.append("Operating leverage")
        
        if competitive.market_growth_rate > 0.10:
            narratives.append("large growing TAM")
            catalysts.append("Industry tailwinds")
        
        # Assemble narrative
        if narratives:
            narrative = f"Bull case driven by {', '.join(narratives[:3])}. "
            narrative += "Company positioned to exceed expectations if execution continues."
        else:
            narrative = "Bull case assumes better than expected execution and favorable market conditions."
        
        return {
            "narrative": narrative,
            "target": round(bull_target, 2),
            "probability": 0.25,
            "catalysts": catalysts[:4],
        }
    
    def _generate_base_case(
        self,
        valuation: ValuationSummary,
        financial: FinancialAnalysis,
    ) -> dict:
        """Generate base case scenario."""
        # Base case = fair value
        base_target = valuation.fair_value
        
        # Build narrative
        growth = financial.metrics.revenue_growth_yoy
        margin = financial.metrics.operating_margin
        
        narrative = f"Base case assumes {growth:.0%} revenue growth stabilizing "
        narrative += f"with operating margins around {margin:.1%}. "
        narrative += "Valuation reflects current growth trajectory and industry positioning."
        
        return {
            "narrative": narrative,
            "target": round(base_target, 2),
            "probability": 0.50,
        }
    
    def _generate_bear_case(
        self,
        valuation: ValuationSummary,
        financial: FinancialAnalysis,
        risk: RiskAssessment,
    ) -> dict:
        """Generate bear case scenario."""
        # Bear case target = lower end of range - 15%
        base_value = valuation.valuation_range_low
        bear_target = base_value * 0.85 if base_value > 0 else valuation.fair_value * 0.70
        
        # Build narrative and risks
        risks = []
        narratives = []
        
        if financial.metrics.debt_to_equity > 1.0:
            risks.append("Balance sheet deterioration")
            narratives.append("leverage concerns")
        
        if risk.key_risks:
            risks.extend(risk.key_risks[:2])
        
        if financial.metrics.revenue_growth_yoy < 0.05:
            risks.append("Growth deceleration")
            narratives.append("slowing growth")
        
        if financial.metrics.operating_margin < 0.10:
            risks.append("Margin compression")
            narratives.append("margin pressure")
        
        # Assemble narrative
        if narratives:
            narrative = f"Bear case driven by {', '.join(narratives[:2])}. "
        else:
            narrative = "Bear case reflects "
        narrative += "Multiple compression and estimate cuts if key risks materialize."
        
        return {
            "narrative": narrative,
            "target": round(bear_target, 2),
            "probability": 0.25,
            "risks": risks[:4],
        }
    
    def _identify_catalysts(
        self,
        financial: FinancialAnalysis,
        competitive: CompetitiveAnalysis,
        market_data: dict,
    ) -> list[Catalyst]:
        """Identify potential catalysts."""
        catalysts = []
        today = date.today()
        
        # Earnings catalyst
        next_earnings = market_data.get("next_earnings_date")
        if next_earnings:
            catalysts.append(Catalyst(
                title="Quarterly Earnings",
                description="Upcoming earnings release",
                expected_date=next_earnings,
                timeframe="near_term",
                impact="uncertain",
                probability=1.0,
            ))
        else:
            catalysts.append(Catalyst(
                title="Quarterly Earnings",
                description="Next quarterly results",
                expected_date=today + timedelta(days=45),
                timeframe="near_term",
                impact="uncertain",
                probability=1.0,
            ))
        
        # Product launch
        if market_data.get("new_products", False):
            catalysts.append(Catalyst(
                title="Product Launch",
                description="New product introduction",
                timeframe="medium_term",
                impact="positive",
                probability=0.7,
            ))
        
        # M&A
        if market_data.get("m_and_a_candidate", False):
            catalysts.append(Catalyst(
                title="M&A Activity",
                description="Potential acquisition target or acquirer",
                timeframe="medium_term",
                impact="positive",
                probability=0.3,
            ))
        
        # Market expansion
        if competitive.market_growth_rate > 0.10:
            catalysts.append(Catalyst(
                title="Market Expansion",
                description="Growing addressable market",
                timeframe="long_term",
                impact="positive",
                probability=0.6,
            ))
        
        # Capital return
        if financial.metrics.fcf_yield > 0.05:
            catalysts.append(Catalyst(
                title="Capital Returns",
                description="Potential for increased dividends or buybacks",
                timeframe="medium_term",
                impact="positive",
                probability=0.5,
            ))
        
        return catalysts[:6]
    
    def _generate_buy_reasons(
        self,
        valuation: ValuationSummary,
        financial: FinancialAnalysis,
        competitive: CompetitiveAnalysis,
    ) -> list[str]:
        """Generate reasons to buy."""
        reasons = []
        
        # Valuation
        if valuation.upside_pct > 15:
            reasons.append(f"{valuation.upside_pct:.0f}% upside to fair value")
        
        # Growth
        if financial.metrics.revenue_growth_yoy > 0.10:
            reasons.append(f"Strong revenue growth ({financial.metrics.revenue_growth_yoy:.0%})")
        
        # Moat
        if competitive.moat_rating.value != "none":
            reasons.append(f"{competitive.moat_rating.value.title()} economic moat")
        
        # Cash flow
        if financial.metrics.fcf_margin > 0.10:
            reasons.append("Strong free cash flow generation")
        
        # Returns
        if financial.metrics.roic > 0.15:
            reasons.append("High return on invested capital")
        
        # Market position
        if competitive.market_position in ["leader", "challenger"]:
            reasons.append(f"Market {competitive.market_position}")
        
        # Balance sheet
        if financial.metrics.debt_to_equity < 0.5 and financial.metrics.cash_and_equivalents > 0:
            reasons.append("Strong balance sheet")
        
        return reasons[:5]
    
    def _generate_sell_reasons(
        self,
        valuation: ValuationSummary,
        financial: FinancialAnalysis,
        risk: RiskAssessment,
    ) -> list[str]:
        """Generate reasons to sell/avoid."""
        reasons = []
        
        # Valuation
        if valuation.upside_pct < -10:
            reasons.append(f"Overvalued ({abs(valuation.upside_pct):.0f}% downside)")
        
        # Growth
        if financial.metrics.revenue_growth_yoy < 0:
            reasons.append("Declining revenue")
        
        # Margins
        if financial.metrics.operating_margin < 0.05:
            reasons.append("Weak profitability")
        
        # Leverage
        if financial.metrics.debt_to_equity > 1.5:
            reasons.append(f"High leverage ({financial.metrics.debt_to_equity:.1f}x D/E)")
        
        # Risk
        if risk.overall_risk_rating.value in ["high", "very_high"]:
            reasons.append(f"{risk.overall_risk_rating.value.replace('_', ' ').title()} risk profile")
        
        # Key risks
        if risk.key_risks:
            reasons.append(f"Key risk: {risk.key_risks[0]}")
        
        return reasons[:5]
