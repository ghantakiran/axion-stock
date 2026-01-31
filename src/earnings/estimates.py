"""Earnings Estimates Tracking.

Track analyst estimates, revisions, and consensus.
"""

from datetime import date, timedelta
from typing import Optional
import logging

from src.earnings.models import EarningsEstimate

logger = logging.getLogger(__name__)


class EstimateTracker:
    """Tracks analyst earnings estimates.
    
    Monitors consensus estimates, tracks revisions, and
    provides estimate analysis.
    
    Example:
        tracker = EstimateTracker()
        
        estimate = tracker.get_estimate("AAPL", "Q1 2024")
        print(f"EPS Consensus: ${estimate.eps_consensus}")
        print(f"Revision trend: {estimate.revision_trend}")
    """
    
    def __init__(self):
        self._estimates: dict[str, EarningsEstimate] = {}  # key: symbol_quarter
        self._history: dict[str, list[EarningsEstimate]] = {}  # key: symbol_quarter -> history
    
    def _make_key(self, symbol: str, fiscal_quarter: str) -> str:
        """Create lookup key."""
        return f"{symbol}_{fiscal_quarter}"
    
    def add_estimate(self, estimate: EarningsEstimate) -> None:
        """Add or update an estimate."""
        key = self._make_key(estimate.symbol, estimate.fiscal_quarter)
        
        # Store history
        if key not in self._history:
            self._history[key] = []
        
        # If we have an existing estimate, save to history
        if key in self._estimates:
            self._history[key].append(self._estimates[key])
        
        self._estimates[key] = estimate
    
    def get_estimate(
        self,
        symbol: str,
        fiscal_quarter: str,
    ) -> Optional[EarningsEstimate]:
        """Get current estimate."""
        key = self._make_key(symbol, fiscal_quarter)
        return self._estimates.get(key)
    
    def get_estimate_history(
        self,
        symbol: str,
        fiscal_quarter: str,
    ) -> list[EarningsEstimate]:
        """Get estimate history (revisions over time)."""
        key = self._make_key(symbol, fiscal_quarter)
        history = self._history.get(key, [])
        
        # Include current estimate
        current = self._estimates.get(key)
        if current:
            return history + [current]
        return history
    
    def get_all_estimates(self, symbol: str) -> list[EarningsEstimate]:
        """Get all estimates for a symbol."""
        estimates = []
        for key, estimate in self._estimates.items():
            if estimate.symbol == symbol:
                estimates.append(estimate)
        return sorted(estimates, key=lambda e: e.fiscal_quarter, reverse=True)
    
    def calculate_revision_momentum(
        self,
        symbol: str,
        fiscal_quarter: str,
        days: int = 30,
    ) -> dict:
        """Calculate estimate revision momentum.
        
        Args:
            symbol: Stock symbol.
            fiscal_quarter: Target quarter.
            days: Look-back period.
            
        Returns:
            Dict with revision analysis.
        """
        history = self.get_estimate_history(symbol, fiscal_quarter)
        
        if len(history) < 2:
            return {
                "eps_change": 0,
                "eps_change_pct": 0,
                "direction": "neutral",
                "num_revisions": 0,
            }
        
        cutoff = date.today() - timedelta(days=days)
        recent_history = [e for e in history if e.as_of_date >= cutoff]
        
        if len(recent_history) < 2:
            recent_history = history[-2:]
        
        oldest = recent_history[0]
        newest = recent_history[-1]
        
        eps_change = newest.eps_consensus - oldest.eps_consensus
        eps_change_pct = eps_change / abs(oldest.eps_consensus) if oldest.eps_consensus else 0
        
        if eps_change > 0.01:
            direction = "positive"
        elif eps_change < -0.01:
            direction = "negative"
        else:
            direction = "neutral"
        
        return {
            "eps_change": eps_change,
            "eps_change_pct": eps_change_pct,
            "direction": direction,
            "num_revisions": len(recent_history) - 1,
            "oldest_estimate": oldest.eps_consensus,
            "newest_estimate": newest.eps_consensus,
        }
    
    def get_estimate_spread(
        self,
        symbol: str,
        fiscal_quarter: str,
    ) -> dict:
        """Get spread between high and low estimates.
        
        Returns:
            Dict with spread analysis.
        """
        estimate = self.get_estimate(symbol, fiscal_quarter)
        
        if not estimate:
            return {"eps_spread": 0, "revenue_spread": 0, "dispersion": "unknown"}
        
        eps_spread = estimate.eps_high - estimate.eps_low
        eps_spread_pct = eps_spread / abs(estimate.eps_consensus) if estimate.eps_consensus else 0
        
        # Categorize dispersion
        if eps_spread_pct < 0.10:
            dispersion = "low"
        elif eps_spread_pct < 0.25:
            dispersion = "moderate"
        else:
            dispersion = "high"
        
        return {
            "eps_spread": eps_spread,
            "eps_spread_pct": eps_spread_pct,
            "revenue_spread": estimate.revenue_high - estimate.revenue_low,
            "dispersion": dispersion,
            "num_analysts": estimate.eps_num_analysts,
        }
    
    def compare_to_year_ago(
        self,
        symbol: str,
        fiscal_quarter: str,
    ) -> dict:
        """Compare estimates to year-ago actuals.
        
        Returns:
            Dict with YoY comparison.
        """
        estimate = self.get_estimate(symbol, fiscal_quarter)
        
        if not estimate:
            return {"eps_growth": None, "revenue_growth": None}
        
        eps_growth = None
        if estimate.eps_year_ago and estimate.eps_year_ago != 0:
            eps_growth = (estimate.eps_consensus - estimate.eps_year_ago) / abs(estimate.eps_year_ago)
        
        revenue_growth = None
        if estimate.revenue_year_ago and estimate.revenue_year_ago != 0:
            revenue_growth = (estimate.revenue_consensus - estimate.revenue_year_ago) / abs(estimate.revenue_year_ago)
        
        return {
            "eps_growth": eps_growth,
            "revenue_growth": revenue_growth,
            "eps_year_ago": estimate.eps_year_ago,
            "revenue_year_ago": estimate.revenue_year_ago,
        }
    
    def get_symbols_with_positive_revisions(self) -> list[str]:
        """Get symbols with recent positive revisions."""
        positive = []
        
        for estimate in self._estimates.values():
            if estimate.eps_revisions_up > estimate.eps_revisions_down:
                positive.append(estimate.symbol)
        
        return list(set(positive))
    
    def get_symbols_with_negative_revisions(self) -> list[str]:
        """Get symbols with recent negative revisions."""
        negative = []
        
        for estimate in self._estimates.values():
            if estimate.eps_revisions_down > estimate.eps_revisions_up:
                negative.append(estimate.symbol)
        
        return list(set(negative))


def generate_sample_estimates() -> EstimateTracker:
    """Generate sample estimates for testing."""
    tracker = EstimateTracker()
    
    sample_data = [
        ("AAPL", "Q4 2025", 2.10, 2.25, 1.95, 32, 94.5e9, 98e9, 91e9, 28, 5, 2, 1.98, 89.5e9),
        ("MSFT", "Q4 2025", 2.95, 3.10, 2.80, 35, 62.0e9, 64e9, 60e9, 30, 8, 1, 2.69, 56.2e9),
        ("GOOGL", "Q4 2025", 1.55, 1.70, 1.40, 40, 86.0e9, 90e9, 82e9, 35, 6, 3, 1.64, 76.7e9),
        ("AMZN", "Q4 2025", 0.85, 1.00, 0.70, 38, 165.0e9, 170e9, 160e9, 32, 10, 2, 0.03, 149.2e9),
        ("META", "Q4 2025", 4.95, 5.20, 4.70, 42, 39.0e9, 41e9, 37e9, 36, 7, 1, 4.39, 32.2e9),
        ("NVDA", "Q4 2025", 4.60, 4.90, 4.30, 45, 24.0e9, 26e9, 22e9, 38, 12, 0, 2.70, 14.5e9),
    ]
    
    for (symbol, quarter, eps_cons, eps_hi, eps_lo, eps_num,
         rev_cons, rev_hi, rev_lo, rev_num, rev_up, rev_down,
         eps_yoy, rev_yoy) in sample_data:
        estimate = EarningsEstimate(
            symbol=symbol,
            fiscal_quarter=quarter,
            eps_consensus=eps_cons,
            eps_high=eps_hi,
            eps_low=eps_lo,
            eps_num_analysts=eps_num,
            revenue_consensus=rev_cons,
            revenue_high=rev_hi,
            revenue_low=rev_lo,
            revenue_num_analysts=rev_num,
            eps_revisions_up=rev_up,
            eps_revisions_down=rev_down,
            eps_year_ago=eps_yoy,
            revenue_year_ago=rev_yoy,
        )
        tracker.add_estimate(estimate)
    
    return tracker
