"""Financial Analysis Module.

Analyzes company financials and generates insights.
"""

from dataclasses import dataclass
from typing import Optional
import logging

from src.research.config import (
    ResearchConfig,
    DEFAULT_RESEARCH_CONFIG,
    SECTOR_MARGINS,
    QUALITY_WEIGHTS,
)
from src.research.models import (
    FinancialMetrics,
    FinancialAnalysis,
)

logger = logging.getLogger(__name__)


class FinancialAnalyzer:
    """Analyzes company financial statements.
    
    Features:
    - Income statement analysis
    - Balance sheet assessment
    - Cash flow quality
    - Trend analysis
    - Quality scoring
    
    Example:
        analyzer = FinancialAnalyzer()
        analysis = analyzer.analyze(financial_data)
    """
    
    def __init__(self, config: Optional[ResearchConfig] = None):
        self.config = config or DEFAULT_RESEARCH_CONFIG
    
    def analyze(
        self,
        symbol: str,
        data: dict,
        sector: str = "Technology",
    ) -> FinancialAnalysis:
        """Perform comprehensive financial analysis.
        
        Args:
            symbol: Stock symbol.
            data: Financial data dict.
            sector: Company sector for benchmarking.
            
        Returns:
            FinancialAnalysis object.
        """
        # Extract metrics
        metrics = self._extract_metrics(data)
        
        # Calculate quality scores
        earnings_quality = self._calculate_earnings_quality(metrics, data)
        balance_sheet_strength = self._calculate_balance_sheet_strength(metrics)
        cash_flow_quality = self._calculate_cash_flow_quality(metrics)
        
        # Overall health score
        overall_health = (
            earnings_quality * 0.35 +
            balance_sheet_strength * 0.35 +
            cash_flow_quality * 0.30
        )
        
        # Determine trends
        revenue_trend = self._determine_trend(data.get("revenue_history", []))
        margin_trend = self._determine_margin_trend(data.get("margin_history", {}))
        debt_trend = self._determine_debt_trend(data.get("debt_history", []))
        
        # Generate insights
        strengths, concerns = self._generate_insights(metrics, sector)
        
        return FinancialAnalysis(
            symbol=symbol,
            metrics=metrics,
            revenue_history=data.get("revenue_history", []),
            eps_history=data.get("eps_history", []),
            margin_history=data.get("margin_history", {}),
            earnings_quality_score=earnings_quality,
            balance_sheet_strength=balance_sheet_strength,
            cash_flow_quality=cash_flow_quality,
            overall_financial_health=overall_health,
            revenue_trend=revenue_trend,
            margin_trend=margin_trend,
            debt_trend=debt_trend,
            strengths=strengths,
            concerns=concerns,
        )
    
    def _extract_metrics(self, data: dict) -> FinancialMetrics:
        """Extract financial metrics from data."""
        metrics = FinancialMetrics()
        
        # Income statement
        metrics.revenue_ttm = data.get("revenue", 0)
        metrics.revenue_growth_yoy = data.get("revenue_growth", 0)
        metrics.revenue_growth_3yr_cagr = data.get("revenue_cagr_3yr", 0)
        metrics.gross_profit = data.get("gross_profit", 0)
        metrics.gross_margin = data.get("gross_margin", 0)
        metrics.operating_income = data.get("operating_income", 0)
        metrics.operating_margin = data.get("operating_margin", 0)
        metrics.net_income = data.get("net_income", 0)
        metrics.net_margin = data.get("net_margin", 0)
        metrics.eps_ttm = data.get("eps", 0)
        metrics.eps_growth_yoy = data.get("eps_growth", 0)
        
        # Balance sheet
        metrics.total_assets = data.get("total_assets", 0)
        metrics.total_liabilities = data.get("total_liabilities", 0)
        metrics.total_equity = data.get("total_equity", 0)
        metrics.total_debt = data.get("total_debt", 0)
        metrics.cash_and_equivalents = data.get("cash", 0)
        metrics.net_debt = metrics.total_debt - metrics.cash_and_equivalents
        
        # Ratios
        if metrics.total_equity > 0:
            metrics.debt_to_equity = metrics.total_debt / metrics.total_equity
        
        ebitda = data.get("ebitda", metrics.operating_income * 1.1)
        if ebitda > 0:
            metrics.debt_to_ebitda = metrics.total_debt / ebitda
        
        current_assets = data.get("current_assets", metrics.total_assets * 0.4)
        current_liabilities = data.get("current_liabilities", metrics.total_liabilities * 0.3)
        if current_liabilities > 0:
            metrics.current_ratio = current_assets / current_liabilities
            inventory = data.get("inventory", 0)
            metrics.quick_ratio = (current_assets - inventory) / current_liabilities
        
        # Cash flow
        metrics.operating_cash_flow = data.get("operating_cash_flow", metrics.net_income * 1.2)
        metrics.capital_expenditures = data.get("capex", metrics.revenue_ttm * 0.05)
        metrics.free_cash_flow = metrics.operating_cash_flow - abs(metrics.capital_expenditures)
        
        if metrics.revenue_ttm > 0:
            metrics.fcf_margin = metrics.free_cash_flow / metrics.revenue_ttm
        
        market_cap = data.get("market_cap", 0)
        if market_cap > 0:
            metrics.fcf_yield = metrics.free_cash_flow / market_cap
        
        # Returns
        if metrics.total_equity > 0:
            metrics.roe = metrics.net_income / metrics.total_equity
        if metrics.total_assets > 0:
            metrics.roa = metrics.net_income / metrics.total_assets
        
        invested_capital = metrics.total_equity + metrics.total_debt - metrics.cash_and_equivalents
        if invested_capital > 0:
            nopat = metrics.operating_income * (1 - 0.21)
            metrics.roic = nopat / invested_capital
        
        return metrics
    
    def _calculate_earnings_quality(
        self,
        metrics: FinancialMetrics,
        data: dict,
    ) -> float:
        """Calculate earnings quality score (0-100)."""
        score = 50.0  # Base score
        
        # Accruals check: OCF should exceed net income
        if metrics.net_income > 0:
            ocf_ratio = metrics.operating_cash_flow / metrics.net_income
            if ocf_ratio > 1.2:
                score += 15
            elif ocf_ratio > 1.0:
                score += 10
            elif ocf_ratio > 0.8:
                score += 5
            elif ocf_ratio < 0.5:
                score -= 15
        
        # Revenue quality: consistent growth
        revenue_history = data.get("revenue_history", [])
        if len(revenue_history) >= 3:
            positive_years = sum(1 for i in range(1, len(revenue_history)) 
                               if revenue_history[i] > revenue_history[i-1])
            growth_consistency = positive_years / (len(revenue_history) - 1)
            score += (growth_consistency - 0.5) * 20
        
        # Margin stability
        if metrics.gross_margin > 0.30:
            score += 5
        if metrics.operating_margin > 0.15:
            score += 5
        
        return max(0, min(100, score))
    
    def _calculate_balance_sheet_strength(self, metrics: FinancialMetrics) -> float:
        """Calculate balance sheet strength score (0-100)."""
        score = 50.0
        
        # Debt levels
        if metrics.debt_to_equity < 0.3:
            score += 15
        elif metrics.debt_to_equity < 0.5:
            score += 10
        elif metrics.debt_to_equity < 1.0:
            score += 5
        elif metrics.debt_to_equity > 2.0:
            score -= 15
        
        # Liquidity
        if metrics.current_ratio > 2.0:
            score += 10
        elif metrics.current_ratio > 1.5:
            score += 5
        elif metrics.current_ratio < 1.0:
            score -= 10
        
        # Cash position
        if metrics.cash_and_equivalents > metrics.total_debt:
            score += 15  # Net cash position
        elif metrics.net_debt < 0:
            score += 10
        
        # Debt coverage
        if metrics.debt_to_ebitda < 2:
            score += 10
        elif metrics.debt_to_ebitda > 4:
            score -= 10
        
        return max(0, min(100, score))
    
    def _calculate_cash_flow_quality(self, metrics: FinancialMetrics) -> float:
        """Calculate cash flow quality score (0-100)."""
        score = 50.0
        
        # FCF generation
        if metrics.fcf_margin > 0.20:
            score += 20
        elif metrics.fcf_margin > 0.10:
            score += 10
        elif metrics.fcf_margin > 0.05:
            score += 5
        elif metrics.fcf_margin < 0:
            score -= 15
        
        # FCF yield
        if metrics.fcf_yield > 0.08:
            score += 15
        elif metrics.fcf_yield > 0.05:
            score += 10
        elif metrics.fcf_yield > 0.03:
            score += 5
        
        # OCF coverage of capex
        if metrics.capital_expenditures > 0:
            capex_coverage = metrics.operating_cash_flow / abs(metrics.capital_expenditures)
            if capex_coverage > 3:
                score += 10
            elif capex_coverage > 2:
                score += 5
            elif capex_coverage < 1:
                score -= 10
        
        return max(0, min(100, score))
    
    def _determine_trend(self, values: list) -> str:
        """Determine trend from historical values."""
        if not values or len(values) < 2:
            return "stable"
        
        # Simple linear trend
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return "stable"
        
        slope = numerator / denominator
        
        # Normalize by mean
        if y_mean != 0:
            relative_slope = slope / abs(y_mean)
        else:
            relative_slope = 0
        
        if relative_slope > 0.05:
            return "growing"
        elif relative_slope < -0.05:
            return "declining"
        return "stable"
    
    def _determine_margin_trend(self, margin_history: dict) -> str:
        """Determine margin trend."""
        operating_margins = margin_history.get("operating", [])
        return self._determine_trend(operating_margins)
    
    def _determine_debt_trend(self, debt_history: list) -> str:
        """Determine debt trend."""
        trend = self._determine_trend(debt_history)
        # Invert for debt (growing debt is negative)
        if trend == "growing":
            return "increasing"
        elif trend == "declining":
            return "decreasing"
        return "stable"
    
    def _generate_insights(
        self,
        metrics: FinancialMetrics,
        sector: str,
    ) -> tuple[list[str], list[str]]:
        """Generate financial strengths and concerns."""
        strengths = []
        concerns = []
        
        # Get sector benchmarks
        benchmarks = SECTOR_MARGINS.get(sector, SECTOR_MARGINS["Technology"])
        
        # Margin analysis
        if metrics.gross_margin > benchmarks["gross"]:
            strengths.append(f"Above-average gross margin ({metrics.gross_margin:.1%})")
        elif metrics.gross_margin < benchmarks["gross"] * 0.8:
            concerns.append(f"Below-average gross margin ({metrics.gross_margin:.1%})")
        
        if metrics.operating_margin > benchmarks["operating"]:
            strengths.append(f"Strong operating margin ({metrics.operating_margin:.1%})")
        elif metrics.operating_margin < benchmarks["operating"] * 0.7:
            concerns.append(f"Weak operating margin ({metrics.operating_margin:.1%})")
        
        # Growth analysis
        if metrics.revenue_growth_yoy > 0.15:
            strengths.append(f"Strong revenue growth ({metrics.revenue_growth_yoy:.1%})")
        elif metrics.revenue_growth_yoy < 0:
            concerns.append(f"Declining revenue ({metrics.revenue_growth_yoy:.1%})")
        
        # Balance sheet
        if metrics.debt_to_equity < 0.3:
            strengths.append("Conservative debt levels")
        elif metrics.debt_to_equity > 1.5:
            concerns.append(f"High leverage (D/E: {metrics.debt_to_equity:.1f}x)")
        
        if metrics.current_ratio > 2.0:
            strengths.append("Strong liquidity position")
        elif metrics.current_ratio < 1.0:
            concerns.append(f"Weak liquidity (Current ratio: {metrics.current_ratio:.1f})")
        
        # Cash flow
        if metrics.fcf_margin > 0.15:
            strengths.append(f"Excellent free cash flow generation ({metrics.fcf_margin:.1%})")
        elif metrics.fcf_margin < 0:
            concerns.append("Negative free cash flow")
        
        # Returns
        if metrics.roe > 0.20:
            strengths.append(f"High return on equity ({metrics.roe:.1%})")
        elif metrics.roe < 0.08:
            concerns.append(f"Low return on equity ({metrics.roe:.1%})")
        
        if metrics.roic > 0.15:
            strengths.append(f"Strong return on invested capital ({metrics.roic:.1%})")
        
        return strengths, concerns
