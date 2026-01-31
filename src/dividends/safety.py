"""Dividend Safety Analysis.

Assess dividend sustainability using payout ratios and financial health.
"""

from datetime import date
from dataclasses import dataclass
from typing import Optional
import logging

from src.dividends.config import (
    SafetyRating,
    PAYOUT_RATIO_THRESHOLDS,
    COVERAGE_RATIO_THRESHOLDS,
)
from src.dividends.models import DividendSafety

logger = logging.getLogger(__name__)


@dataclass
class FinancialMetrics:
    """Financial metrics for safety analysis."""
    # Earnings
    eps: float = 0.0
    net_income: float = 0.0
    
    # Cash flow
    operating_cash_flow: float = 0.0
    free_cash_flow: float = 0.0
    
    # Balance sheet
    total_debt: float = 0.0
    ebitda: float = 0.0
    interest_expense: float = 0.0
    current_assets: float = 0.0
    current_liabilities: float = 0.0
    
    # Dividends
    dividend_per_share: float = 0.0
    total_dividends_paid: float = 0.0
    shares_outstanding: float = 0.0


class SafetyAnalyzer:
    """Analyzes dividend safety.
    
    Uses payout ratios, coverage ratios, and balance sheet
    metrics to assess dividend sustainability.
    
    Example:
        analyzer = SafetyAnalyzer()
        
        metrics = FinancialMetrics(eps=5.0, dividend_per_share=2.0, ...)
        safety = analyzer.analyze("AAPL", metrics)
        
        print(f"Safety score: {safety.safety_score}")
        print(f"Rating: {safety.safety_rating.value}")
    """
    
    def __init__(self):
        self._safety_data: dict[str, DividendSafety] = {}
    
    def analyze(
        self,
        symbol: str,
        metrics: FinancialMetrics,
    ) -> DividendSafety:
        """Perform safety analysis.
        
        Args:
            symbol: Stock symbol.
            metrics: Financial metrics.
            
        Returns:
            DividendSafety assessment.
        """
        safety = DividendSafety(symbol=symbol)
        
        # Calculate payout ratios
        self._calculate_payout_ratios(safety, metrics)
        
        # Calculate balance sheet metrics
        self._calculate_balance_sheet(safety, metrics)
        
        # Identify red flags
        self._identify_red_flags(safety)
        
        # Calculate safety score
        self._calculate_safety_score(safety)
        
        # Determine rating
        safety.safety_rating = self._determine_rating(safety)
        
        self._safety_data[symbol] = safety
        return safety
    
    def _calculate_payout_ratios(
        self,
        safety: DividendSafety,
        metrics: FinancialMetrics,
    ) -> None:
        """Calculate payout and coverage ratios."""
        # Earnings payout ratio
        if metrics.eps > 0:
            safety.payout_ratio = metrics.dividend_per_share / metrics.eps
            safety.coverage_ratio = metrics.eps / metrics.dividend_per_share if metrics.dividend_per_share > 0 else 0
        else:
            safety.payout_ratio = float('inf') if metrics.dividend_per_share > 0 else 0
            safety.coverage_ratio = 0
        
        # Cash payout ratio (FCF based)
        if metrics.free_cash_flow > 0 and metrics.shares_outstanding > 0:
            fcf_per_share = metrics.free_cash_flow / metrics.shares_outstanding
            if fcf_per_share > 0:
                safety.cash_payout_ratio = metrics.dividend_per_share / fcf_per_share
            else:
                safety.cash_payout_ratio = float('inf')
        elif metrics.total_dividends_paid > 0:
            if metrics.free_cash_flow > 0:
                safety.cash_payout_ratio = metrics.total_dividends_paid / metrics.free_cash_flow
            else:
                safety.cash_payout_ratio = float('inf')
    
    def _calculate_balance_sheet(
        self,
        safety: DividendSafety,
        metrics: FinancialMetrics,
    ) -> None:
        """Calculate balance sheet health metrics."""
        # Debt to EBITDA
        if metrics.ebitda > 0:
            safety.debt_to_ebitda = metrics.total_debt / metrics.ebitda
        else:
            safety.debt_to_ebitda = float('inf') if metrics.total_debt > 0 else 0
        
        # Interest coverage
        if metrics.interest_expense > 0:
            # EBIT approximation
            ebit = metrics.ebitda * 0.85  # Rough approximation
            safety.interest_coverage = ebit / metrics.interest_expense
        else:
            safety.interest_coverage = float('inf')
        
        # Current ratio
        if metrics.current_liabilities > 0:
            safety.current_ratio = metrics.current_assets / metrics.current_liabilities
        else:
            safety.current_ratio = float('inf') if metrics.current_assets > 0 else 0
    
    def _identify_red_flags(self, safety: DividendSafety) -> None:
        """Identify dividend safety red flags."""
        flags = []
        
        # High payout ratio
        if safety.payout_ratio > 1.0:
            flags.append("Payout ratio exceeds 100% of earnings")
        elif safety.payout_ratio > 0.90:
            flags.append("Payout ratio above 90%")
        
        # High cash payout
        if safety.cash_payout_ratio > 1.0:
            flags.append("Dividends exceed free cash flow")
        elif safety.cash_payout_ratio > 0.85:
            flags.append("Cash payout ratio above 85%")
        
        # Low coverage
        if safety.coverage_ratio < 1.0:
            flags.append("Earnings do not cover dividend")
        elif safety.coverage_ratio < 1.25:
            flags.append("Low earnings coverage")
        
        # High leverage
        if safety.debt_to_ebitda > 4.0:
            flags.append("High debt/EBITDA ratio")
        
        # Low interest coverage
        if safety.interest_coverage < 2.0:
            flags.append("Low interest coverage")
        
        # Liquidity issues
        if safety.current_ratio < 1.0:
            flags.append("Current ratio below 1")
        
        safety.red_flags = flags
    
    def _calculate_safety_score(self, safety: DividendSafety) -> None:
        """Calculate overall safety score (0-100)."""
        scores = []
        
        # Payout ratio score (40% weight)
        if safety.payout_ratio <= 0.40:
            payout_score = 100
        elif safety.payout_ratio <= 0.60:
            payout_score = 80
        elif safety.payout_ratio <= 0.75:
            payout_score = 60
        elif safety.payout_ratio <= 0.90:
            payout_score = 40
        elif safety.payout_ratio <= 1.0:
            payout_score = 20
        else:
            payout_score = 0
        scores.append(payout_score * 0.40)
        
        # Cash payout score (25% weight)
        if safety.cash_payout_ratio <= 0.50:
            cash_score = 100
        elif safety.cash_payout_ratio <= 0.70:
            cash_score = 80
        elif safety.cash_payout_ratio <= 0.85:
            cash_score = 60
        elif safety.cash_payout_ratio <= 1.0:
            cash_score = 40
        else:
            cash_score = 20
        scores.append(cash_score * 0.25)
        
        # Coverage score (20% weight)
        if safety.coverage_ratio >= 2.5:
            coverage_score = 100
        elif safety.coverage_ratio >= 2.0:
            coverage_score = 80
        elif safety.coverage_ratio >= 1.5:
            coverage_score = 60
        elif safety.coverage_ratio >= 1.0:
            coverage_score = 40
        else:
            coverage_score = 20
        scores.append(coverage_score * 0.20)
        
        # Leverage score (15% weight)
        if safety.debt_to_ebitda <= 1.5:
            leverage_score = 100
        elif safety.debt_to_ebitda <= 2.5:
            leverage_score = 80
        elif safety.debt_to_ebitda <= 3.5:
            leverage_score = 60
        elif safety.debt_to_ebitda <= 4.5:
            leverage_score = 40
        else:
            leverage_score = 20
        scores.append(leverage_score * 0.15)
        
        safety.safety_score = sum(scores)
    
    def _determine_rating(self, safety: DividendSafety) -> SafetyRating:
        """Determine safety rating from score."""
        score = safety.safety_score
        
        if score >= 85:
            return SafetyRating.VERY_SAFE
        elif score >= 70:
            return SafetyRating.SAFE
        elif score >= 50:
            return SafetyRating.MODERATE
        elif score >= 30:
            return SafetyRating.RISKY
        else:
            return SafetyRating.DANGEROUS
    
    def get_safety(self, symbol: str) -> Optional[DividendSafety]:
        """Get safety data for a symbol."""
        return self._safety_data.get(symbol)
    
    def screen_safe_dividends(
        self,
        min_score: float = 70,
    ) -> list[str]:
        """Screen for safe dividend stocks.
        
        Args:
            min_score: Minimum safety score.
            
        Returns:
            List of qualifying symbols.
        """
        return [
            symbol for symbol, safety in self._safety_data.items()
            if safety.safety_score >= min_score
        ]
    
    def compare_safety(
        self,
        symbols: list[str],
    ) -> list[tuple[str, DividendSafety]]:
        """Compare safety across multiple stocks.
        
        Returns:
            List sorted by safety score (highest first).
        """
        results = []
        for symbol in symbols:
            safety = self._safety_data.get(symbol)
            if safety:
                results.append((symbol, safety))
        
        return sorted(results, key=lambda x: x[1].safety_score, reverse=True)
