"""Risk Assessment Module.

Identifies and quantifies company-specific risks.
"""

from typing import Optional
import logging

from src.research.config import (
    ResearchConfig,
    DEFAULT_RESEARCH_CONFIG,
    RiskLevel,
    RiskCategory,
)
from src.research.models import (
    RiskAssessment,
    RiskFactor,
    FinancialMetrics,
)

logger = logging.getLogger(__name__)


class RiskAnalyzer:
    """Analyzes company-specific risks.
    
    Features:
    - Business risk assessment
    - Financial risk analysis
    - Operational risk evaluation
    - ESG risk screening
    - Risk scoring
    
    Example:
        analyzer = RiskAnalyzer()
        assessment = analyzer.analyze(symbol, metrics, market_data)
    """
    
    def __init__(self, config: Optional[ResearchConfig] = None):
        self.config = config or DEFAULT_RESEARCH_CONFIG
        self._risk_config = self.config.risk
    
    def analyze(
        self,
        symbol: str,
        metrics: FinancialMetrics,
        market_data: dict,
    ) -> RiskAssessment:
        """Perform comprehensive risk assessment.
        
        Args:
            symbol: Stock symbol.
            metrics: Financial metrics.
            market_data: Market and company data.
            
        Returns:
            RiskAssessment object.
        """
        assessment = RiskAssessment(symbol=symbol)
        
        # Collect risk factors by category
        risk_factors = []
        
        # Business risks
        business_risks = self._assess_business_risks(metrics, market_data)
        risk_factors.extend(business_risks)
        
        # Financial risks
        financial_risks = self._assess_financial_risks(metrics)
        risk_factors.extend(financial_risks)
        
        # Operational risks
        operational_risks = self._assess_operational_risks(market_data)
        risk_factors.extend(operational_risks)
        
        # Regulatory risks
        regulatory_risks = self._assess_regulatory_risks(market_data)
        risk_factors.extend(regulatory_risks)
        
        # Macro risks
        if self._risk_config.include_macro:
            macro_risks = self._assess_macro_risks(market_data)
            risk_factors.extend(macro_risks)
        
        # ESG risks
        if self._risk_config.include_esg:
            esg = self._assess_esg_risks(market_data)
            assessment.environmental_risks = esg["environmental"]
            assessment.social_risks = esg["social"]
            assessment.governance_risks = esg["governance"]
            assessment.esg_risk_score = esg["score"]
        
        # Sort by risk score and limit
        risk_factors.sort(key=lambda r: r.risk_score, reverse=True)
        assessment.risk_factors = risk_factors[:self._risk_config.max_risk_factors]
        
        # Key risks (top 3)
        assessment.key_risks = [r.title for r in assessment.risk_factors[:3]]
        
        # Category scores
        assessment.business_risk = self._calculate_category_score(
            risk_factors, RiskCategory.BUSINESS
        )
        assessment.financial_risk = self._calculate_category_score(
            risk_factors, RiskCategory.FINANCIAL
        )
        assessment.operational_risk = self._calculate_category_score(
            risk_factors, RiskCategory.OPERATIONAL
        )
        assessment.regulatory_risk = self._calculate_category_score(
            risk_factors, RiskCategory.REGULATORY
        )
        
        # Overall risk score (weighted average)
        assessment.risk_score = (
            assessment.business_risk * 0.30 +
            assessment.financial_risk * 0.25 +
            assessment.operational_risk * 0.20 +
            assessment.regulatory_risk * 0.15 +
            assessment.esg_risk_score * 0.10
        )
        
        # Overall risk rating
        assessment.overall_risk_rating = self._score_to_level(assessment.risk_score)
        
        return assessment
    
    def _assess_business_risks(
        self,
        metrics: FinancialMetrics,
        market_data: dict,
    ) -> list[RiskFactor]:
        """Assess business-related risks."""
        risks = []
        
        # Revenue concentration
        concentration = market_data.get("customer_concentration", 0)
        if concentration > 0.30:
            risks.append(RiskFactor(
                category=RiskCategory.BUSINESS,
                title="Customer Concentration Risk",
                description=f"Top customers represent {concentration:.0%} of revenue",
                probability=RiskLevel.MEDIUM,
                impact=RiskLevel.HIGH,
                risk_score=7.0,
                mitigants=["Diversification initiatives", "Long-term contracts"],
            ))
        
        # Revenue decline
        if metrics.revenue_growth_yoy < -0.05:
            risks.append(RiskFactor(
                category=RiskCategory.BUSINESS,
                title="Revenue Decline",
                description=f"Revenue declining {abs(metrics.revenue_growth_yoy):.1%} YoY",
                probability=RiskLevel.HIGH,
                impact=RiskLevel.HIGH,
                risk_score=8.0,
                mitigants=["Cost restructuring", "New product launches"],
            ))
        
        # Competitive pressure
        if market_data.get("competitive_pressure", False):
            risks.append(RiskFactor(
                category=RiskCategory.BUSINESS,
                title="Competitive Pressure",
                description="Facing increased competition and potential market share loss",
                probability=RiskLevel.MEDIUM,
                impact=RiskLevel.MEDIUM,
                risk_score=5.5,
                mitigants=["Product differentiation", "Cost leadership"],
            ))
        
        # Technology disruption
        if market_data.get("disruption_risk", False):
            risks.append(RiskFactor(
                category=RiskCategory.BUSINESS,
                title="Technology Disruption",
                description="Business model vulnerable to technological change",
                probability=RiskLevel.MEDIUM,
                impact=RiskLevel.HIGH,
                risk_score=6.5,
                mitigants=["R&D investment", "Strategic partnerships"],
            ))
        
        # Margin pressure
        if metrics.gross_margin < 0.25:
            risks.append(RiskFactor(
                category=RiskCategory.BUSINESS,
                title="Margin Pressure",
                description=f"Low gross margin ({metrics.gross_margin:.1%}) limits profitability",
                probability=RiskLevel.MEDIUM,
                impact=RiskLevel.MEDIUM,
                risk_score=5.0,
                mitigants=["Pricing optimization", "Cost reduction"],
            ))
        
        return risks
    
    def _assess_financial_risks(self, metrics: FinancialMetrics) -> list[RiskFactor]:
        """Assess financial risks."""
        risks = []
        
        # Leverage risk
        if metrics.debt_to_equity > 2.0:
            risks.append(RiskFactor(
                category=RiskCategory.FINANCIAL,
                title="High Leverage",
                description=f"Debt/Equity ratio of {metrics.debt_to_equity:.1f}x poses refinancing risk",
                probability=RiskLevel.MEDIUM,
                impact=RiskLevel.HIGH,
                risk_score=7.5,
                mitigants=["Debt paydown", "Equity issuance"],
            ))
        elif metrics.debt_to_equity > 1.0:
            risks.append(RiskFactor(
                category=RiskCategory.FINANCIAL,
                title="Elevated Debt Levels",
                description=f"D/E of {metrics.debt_to_equity:.1f}x requires monitoring",
                probability=RiskLevel.MEDIUM,
                impact=RiskLevel.MEDIUM,
                risk_score=5.0,
            ))
        
        # Liquidity risk
        if metrics.current_ratio < 1.0:
            risks.append(RiskFactor(
                category=RiskCategory.FINANCIAL,
                title="Liquidity Risk",
                description=f"Current ratio of {metrics.current_ratio:.2f} below 1.0",
                probability=RiskLevel.MEDIUM,
                impact=RiskLevel.HIGH,
                risk_score=7.0,
                mitigants=["Credit facility", "Working capital management"],
            ))
        
        # Negative cash flow
        if metrics.free_cash_flow < 0:
            risks.append(RiskFactor(
                category=RiskCategory.FINANCIAL,
                title="Negative Free Cash Flow",
                description="Company burning cash, may need external financing",
                probability=RiskLevel.HIGH,
                impact=RiskLevel.MEDIUM,
                risk_score=6.5,
                mitigants=["Cost cutting", "CapEx reduction"],
            ))
        
        # Interest coverage (estimated)
        if metrics.operating_income > 0 and metrics.total_debt > 0:
            interest_expense = metrics.total_debt * 0.05  # Assume 5% rate
            coverage = metrics.operating_income / interest_expense
            if coverage < 2:
                risks.append(RiskFactor(
                    category=RiskCategory.FINANCIAL,
                    title="Interest Coverage Risk",
                    description=f"Interest coverage of {coverage:.1f}x is tight",
                    probability=RiskLevel.MEDIUM,
                    impact=RiskLevel.HIGH,
                    risk_score=6.5,
                ))
        
        return risks
    
    def _assess_operational_risks(self, market_data: dict) -> list[RiskFactor]:
        """Assess operational risks."""
        risks = []
        
        # Supply chain
        if market_data.get("supply_chain_risk", False):
            risks.append(RiskFactor(
                category=RiskCategory.OPERATIONAL,
                title="Supply Chain Disruption",
                description="Vulnerable to supply chain disruptions",
                probability=RiskLevel.MEDIUM,
                impact=RiskLevel.MEDIUM,
                risk_score=5.5,
                mitigants=["Supplier diversification", "Inventory buffers"],
            ))
        
        # Key person risk
        if market_data.get("key_person_risk", False):
            risks.append(RiskFactor(
                category=RiskCategory.OPERATIONAL,
                title="Key Person Risk",
                description="Heavy reliance on key executives",
                probability=RiskLevel.LOW,
                impact=RiskLevel.HIGH,
                risk_score=4.5,
                mitigants=["Succession planning", "Management depth"],
            ))
        
        # Geographic concentration
        geo_concentration = market_data.get("geographic_concentration", 0)
        if geo_concentration > 0.70:
            risks.append(RiskFactor(
                category=RiskCategory.OPERATIONAL,
                title="Geographic Concentration",
                description=f"{geo_concentration:.0%} of operations in single region",
                probability=RiskLevel.MEDIUM,
                impact=RiskLevel.MEDIUM,
                risk_score=5.0,
                mitigants=["Geographic expansion"],
            ))
        
        # Cybersecurity
        if market_data.get("cyber_risk", True):  # Most companies have this
            risks.append(RiskFactor(
                category=RiskCategory.OPERATIONAL,
                title="Cybersecurity Risk",
                description="Potential for data breaches and cyber attacks",
                probability=RiskLevel.MEDIUM,
                impact=RiskLevel.MEDIUM,
                risk_score=5.0,
                mitigants=["Security investments", "Insurance"],
            ))
        
        return risks
    
    def _assess_regulatory_risks(self, market_data: dict) -> list[RiskFactor]:
        """Assess regulatory and legal risks."""
        risks = []
        
        # General regulatory risk
        if market_data.get("regulatory_risk", False):
            risks.append(RiskFactor(
                category=RiskCategory.REGULATORY,
                title="Regulatory Risk",
                description="Subject to significant regulatory oversight",
                probability=RiskLevel.MEDIUM,
                impact=RiskLevel.MEDIUM,
                risk_score=5.5,
                mitigants=["Compliance programs", "Government relations"],
            ))
        
        # Litigation
        if market_data.get("litigation_pending", False):
            risks.append(RiskFactor(
                category=RiskCategory.REGULATORY,
                title="Litigation Risk",
                description="Material litigation pending",
                probability=RiskLevel.MEDIUM,
                impact=RiskLevel.HIGH,
                risk_score=6.0,
                mitigants=["Legal reserves", "Settlement negotiations"],
            ))
        
        # Tax risk
        if market_data.get("tax_risk", False):
            risks.append(RiskFactor(
                category=RiskCategory.REGULATORY,
                title="Tax Risk",
                description="Potential for tax policy changes affecting company",
                probability=RiskLevel.LOW,
                impact=RiskLevel.MEDIUM,
                risk_score=4.0,
            ))
        
        return risks
    
    def _assess_macro_risks(self, market_data: dict) -> list[RiskFactor]:
        """Assess macroeconomic risks."""
        risks = []
        
        # Recession sensitivity
        beta = market_data.get("beta", 1.0)
        if beta > 1.3:
            risks.append(RiskFactor(
                category=RiskCategory.MACRO,
                title="Economic Sensitivity",
                description=f"High beta ({beta:.2f}) indicates cyclical exposure",
                probability=RiskLevel.MEDIUM,
                impact=RiskLevel.MEDIUM,
                risk_score=5.0,
            ))
        
        # Currency risk
        international_revenue = market_data.get("international_revenue_pct", 0)
        if international_revenue > 0.40:
            risks.append(RiskFactor(
                category=RiskCategory.MACRO,
                title="Currency Risk",
                description=f"{international_revenue:.0%} of revenue exposed to FX",
                probability=RiskLevel.MEDIUM,
                impact=RiskLevel.MEDIUM,
                risk_score=5.0,
                mitigants=["FX hedging"],
            ))
        
        # Interest rate sensitivity
        if market_data.get("interest_rate_sensitive", False):
            risks.append(RiskFactor(
                category=RiskCategory.MACRO,
                title="Interest Rate Risk",
                description="Business sensitive to interest rate changes",
                probability=RiskLevel.MEDIUM,
                impact=RiskLevel.MEDIUM,
                risk_score=4.5,
            ))
        
        return risks
    
    def _assess_esg_risks(self, market_data: dict) -> dict:
        """Assess ESG risks."""
        environmental = []
        social = []
        governance = []
        score = 50.0  # Base score
        
        # Environmental
        if market_data.get("carbon_intensive", False):
            environmental.append("High carbon footprint")
            score += 10
        if market_data.get("environmental_liabilities", False):
            environmental.append("Environmental liabilities")
            score += 15
        
        # Social
        if market_data.get("labor_issues", False):
            social.append("Labor relations concerns")
            score += 10
        if market_data.get("product_safety_issues", False):
            social.append("Product safety concerns")
            score += 10
        
        # Governance
        if market_data.get("dual_class_shares", False):
            governance.append("Dual-class share structure")
            score += 5
        if market_data.get("related_party_transactions", False):
            governance.append("Related party transactions")
            score += 10
        if market_data.get("board_independence", 0) < 0.5:
            governance.append("Limited board independence")
            score += 5
        
        return {
            "environmental": environmental,
            "social": social,
            "governance": governance,
            "score": min(100, score),
        }
    
    def _calculate_category_score(
        self,
        risks: list[RiskFactor],
        category: RiskCategory,
    ) -> float:
        """Calculate average risk score for a category."""
        category_risks = [r for r in risks if r.category == category]
        
        if not category_risks:
            return 30.0  # Low base risk if no specific risks identified
        
        avg_score = sum(r.risk_score for r in category_risks) / len(category_risks)
        return avg_score * 10  # Scale to 0-100
    
    def _score_to_level(self, score: float) -> RiskLevel:
        """Convert score to risk level."""
        if score >= 70:
            return RiskLevel.VERY_HIGH
        elif score >= 55:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
