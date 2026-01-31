"""Earnings Quality Analysis.

Assess earnings quality using accruals, cash conversion, and Beneish M-Score.
"""

from datetime import date
from dataclasses import dataclass
from typing import Optional
import logging
import math

from src.earnings.config import (
    QualityRating,
    BENEISH_THRESHOLD,
    ACCRUALS_WARNING,
)
from src.earnings.models import EarningsQuality

logger = logging.getLogger(__name__)


@dataclass
class FinancialData:
    """Financial data for quality analysis."""
    # Current period
    revenue: float = 0
    cost_of_revenue: float = 0
    gross_profit: float = 0
    operating_income: float = 0
    net_income: float = 0
    
    # Cash flow
    operating_cash_flow: float = 0
    
    # Balance sheet
    receivables: float = 0
    current_assets: float = 0
    total_assets: float = 0
    ppe: float = 0  # Property, plant, equipment
    total_liabilities: float = 0
    long_term_debt: float = 0
    
    # Expenses
    depreciation: float = 0
    sga_expense: float = 0
    
    # Prior period (for comparisons)
    revenue_prior: float = 0
    gross_profit_prior: float = 0
    receivables_prior: float = 0
    current_assets_prior: float = 0
    total_assets_prior: float = 0
    ppe_prior: float = 0
    depreciation_prior: float = 0
    sga_expense_prior: float = 0
    long_term_debt_prior: float = 0


class QualityAnalyzer:
    """Analyzes earnings quality.
    
    Uses Beneish M-Score and other metrics to assess
    the quality and reliability of reported earnings.
    
    Example:
        analyzer = QualityAnalyzer()
        
        quality = analyzer.analyze("AAPL", financial_data)
        print(f"M-Score: {quality.beneish_m_score:.2f}")
        print(f"Manipulation risk: {quality.is_manipulation_risk}")
    """
    
    def __init__(self):
        self._quality_data: dict[str, EarningsQuality] = {}
    
    def analyze(
        self,
        symbol: str,
        data: FinancialData,
    ) -> EarningsQuality:
        """Perform full quality analysis.
        
        Args:
            symbol: Stock symbol.
            data: Financial data.
            
        Returns:
            EarningsQuality assessment.
        """
        quality = EarningsQuality(symbol=symbol)
        
        # Calculate M-Score components
        self._calculate_mscore_components(quality, data)
        
        # Calculate M-Score
        self._calculate_mscore(quality)
        
        # Calculate other quality metrics
        self._calculate_accruals(quality, data)
        self._calculate_cash_conversion(quality, data)
        
        # Calculate quality scores
        self._calculate_quality_scores(quality, data)
        
        # Identify red flags
        self._identify_red_flags(quality, data)
        
        # Determine rating
        quality.quality_rating = self._determine_rating(quality)
        
        self._quality_data[symbol] = quality
        return quality
    
    def _calculate_mscore_components(
        self,
        quality: EarningsQuality,
        data: FinancialData,
    ) -> None:
        """Calculate Beneish M-Score components."""
        # DSRI - Days Sales Receivable Index
        if data.revenue_prior > 0 and data.receivables_prior > 0:
            dsr_current = data.receivables / data.revenue if data.revenue > 0 else 0
            dsr_prior = data.receivables_prior / data.revenue_prior
            quality.dsri = dsr_current / dsr_prior if dsr_prior > 0 else 1.0
        else:
            quality.dsri = 1.0
        
        # GMI - Gross Margin Index
        if data.revenue > 0 and data.revenue_prior > 0:
            gm_prior = data.gross_profit_prior / data.revenue_prior
            gm_current = data.gross_profit / data.revenue
            quality.gmi = gm_prior / gm_current if gm_current > 0 else 1.0
        else:
            quality.gmi = 1.0
        
        # AQI - Asset Quality Index
        if data.total_assets > 0 and data.total_assets_prior > 0:
            aq_current = 1 - (data.current_assets + data.ppe) / data.total_assets
            aq_prior = 1 - (data.current_assets_prior + data.ppe_prior) / data.total_assets_prior
            quality.aqi = aq_current / aq_prior if aq_prior > 0 else 1.0
        else:
            quality.aqi = 1.0
        
        # SGI - Sales Growth Index
        if data.revenue_prior > 0:
            quality.sgi = data.revenue / data.revenue_prior
        else:
            quality.sgi = 1.0
        
        # DEPI - Depreciation Index
        if data.ppe > 0 and data.ppe_prior > 0:
            dep_rate_prior = data.depreciation_prior / (data.depreciation_prior + data.ppe_prior) if (data.depreciation_prior + data.ppe_prior) > 0 else 0
            dep_rate_current = data.depreciation / (data.depreciation + data.ppe) if (data.depreciation + data.ppe) > 0 else 0
            quality.depi = dep_rate_prior / dep_rate_current if dep_rate_current > 0 else 1.0
        else:
            quality.depi = 1.0
        
        # SGAI - SGA Expense Index
        if data.revenue > 0 and data.revenue_prior > 0:
            sga_ratio_current = data.sga_expense / data.revenue
            sga_ratio_prior = data.sga_expense_prior / data.revenue_prior if data.revenue_prior > 0 else 0
            quality.sgai = sga_ratio_current / sga_ratio_prior if sga_ratio_prior > 0 else 1.0
        else:
            quality.sgai = 1.0
        
        # LVGI - Leverage Index
        if data.total_assets > 0 and data.total_assets_prior > 0:
            lev_current = data.total_liabilities / data.total_assets
            lev_prior = (data.long_term_debt_prior + data.total_liabilities) / data.total_assets_prior if data.total_assets_prior > 0 else 0
            quality.lvgi = lev_current / lev_prior if lev_prior > 0 else 1.0
        else:
            quality.lvgi = 1.0
        
        # TATA - Total Accruals to Total Assets
        if data.total_assets > 0:
            accruals = data.net_income - data.operating_cash_flow
            quality.tata = accruals / data.total_assets
        else:
            quality.tata = 0.0
    
    def _calculate_mscore(self, quality: EarningsQuality) -> None:
        """Calculate Beneish M-Score."""
        # M-Score formula
        quality.beneish_m_score = (
            -4.84 +
            0.920 * quality.dsri +
            0.528 * quality.gmi +
            0.404 * quality.aqi +
            0.892 * quality.sgi +
            0.115 * quality.depi +
            -0.172 * quality.sgai +
            4.679 * quality.tata +
            -0.327 * quality.lvgi
        )
        
        # Check manipulation risk
        quality.is_manipulation_risk = quality.beneish_m_score > BENEISH_THRESHOLD
    
    def _calculate_accruals(
        self,
        quality: EarningsQuality,
        data: FinancialData,
    ) -> None:
        """Calculate accruals ratio."""
        if data.total_assets > 0:
            accruals = data.net_income - data.operating_cash_flow
            quality.accruals_ratio = accruals / data.total_assets
        else:
            quality.accruals_ratio = 0.0
    
    def _calculate_cash_conversion(
        self,
        quality: EarningsQuality,
        data: FinancialData,
    ) -> None:
        """Calculate cash conversion ratio."""
        if data.net_income != 0:
            quality.cash_conversion = data.operating_cash_flow / data.net_income
        else:
            quality.cash_conversion = 0.0
    
    def _calculate_quality_scores(
        self,
        quality: EarningsQuality,
        data: FinancialData,
    ) -> None:
        """Calculate quality scores (0-100)."""
        # Earnings quality score
        scores = []
        
        # Cash conversion (higher is better)
        if quality.cash_conversion >= 1.2:
            scores.append(100)
        elif quality.cash_conversion >= 1.0:
            scores.append(80)
        elif quality.cash_conversion >= 0.8:
            scores.append(60)
        else:
            scores.append(40)
        
        # Accruals (lower is better)
        if abs(quality.accruals_ratio) < 0.03:
            scores.append(100)
        elif abs(quality.accruals_ratio) < 0.05:
            scores.append(80)
        elif abs(quality.accruals_ratio) < 0.10:
            scores.append(60)
        else:
            scores.append(40)
        
        # M-Score (lower is better)
        if quality.beneish_m_score < -2.5:
            scores.append(100)
        elif quality.beneish_m_score < -2.22:
            scores.append(80)
        elif quality.beneish_m_score < -1.78:
            scores.append(60)
        else:
            scores.append(30)
        
        quality.earnings_quality_score = sum(scores) / len(scores)
        
        # Revenue quality score (simplified)
        quality.revenue_quality_score = quality.earnings_quality_score * 0.9
        
        # Overall
        quality.overall_quality_score = (
            quality.earnings_quality_score * 0.6 +
            quality.revenue_quality_score * 0.4
        )
    
    def _identify_red_flags(
        self,
        quality: EarningsQuality,
        data: FinancialData,
    ) -> None:
        """Identify earnings quality red flags."""
        flags = []
        
        if quality.is_manipulation_risk:
            flags.append("High manipulation risk (M-Score)")
        
        if quality.accruals_ratio > ACCRUALS_WARNING:
            flags.append("High accruals ratio")
        
        if quality.cash_conversion < 0.5:
            flags.append("Low cash conversion")
        
        if quality.dsri > 1.5:
            flags.append("Receivables growing faster than sales")
        
        if quality.gmi > 1.3:
            flags.append("Declining gross margins")
        
        if quality.aqi > 1.5:
            flags.append("Declining asset quality")
        
        if quality.sgi > 1.5 and quality.tata > 0.05:
            flags.append("High growth with high accruals")
        
        quality.red_flags = flags
    
    def _determine_rating(self, quality: EarningsQuality) -> QualityRating:
        """Determine overall quality rating."""
        if quality.is_manipulation_risk or len(quality.red_flags) >= 3:
            return QualityRating.WARNING
        
        if quality.overall_quality_score >= 80:
            return QualityRating.HIGH
        elif quality.overall_quality_score >= 60:
            return QualityRating.MEDIUM
        else:
            return QualityRating.LOW
    
    def get_quality(self, symbol: str) -> Optional[EarningsQuality]:
        """Get quality data for a symbol."""
        return self._quality_data.get(symbol)
    
    def screen_by_quality(
        self,
        min_score: float = 70,
        exclude_manipulation_risk: bool = True,
    ) -> list[str]:
        """Screen for high-quality earnings.
        
        Args:
            min_score: Minimum quality score.
            exclude_manipulation_risk: Exclude manipulation risk stocks.
            
        Returns:
            List of qualifying symbols.
        """
        results = []
        
        for symbol, quality in self._quality_data.items():
            if quality.overall_quality_score < min_score:
                continue
            if exclude_manipulation_risk and quality.is_manipulation_risk:
                continue
            results.append(symbol)
        
        return results
