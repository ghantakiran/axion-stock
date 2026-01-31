"""Earnings History Analysis.

Analyze historical earnings patterns and statistics.
"""

from datetime import date
from typing import Optional
import logging

from src.earnings.config import SurpriseType, BEAT_THRESHOLD, MISS_THRESHOLD
from src.earnings.models import QuarterlyEarnings, EarningsHistory

logger = logging.getLogger(__name__)


class HistoryAnalyzer:
    """Analyzes historical earnings data.
    
    Calculates beat rates, surprise patterns, and consistency metrics.
    
    Example:
        analyzer = HistoryAnalyzer()
        
        history = analyzer.analyze_history("AAPL", quarterly_data)
        print(f"Beat rate: {history.beat_rate_eps:.0%}")
        print(f"Avg surprise: {history.avg_surprise_eps:.1%}")
    """
    
    def __init__(self):
        self._histories: dict[str, EarningsHistory] = {}
    
    def add_quarterly_data(
        self,
        symbol: str,
        quarters: list[QuarterlyEarnings],
    ) -> EarningsHistory:
        """Add quarterly earnings data and compute history.
        
        Args:
            symbol: Stock symbol.
            quarters: List of quarterly earnings.
            
        Returns:
            Computed EarningsHistory.
        """
        # Sort by date (oldest first)
        quarters = sorted(quarters, key=lambda q: q.report_date or date.min)
        
        history = EarningsHistory(symbol=symbol, quarters=quarters)
        
        # Calculate statistics
        self._calculate_beat_rates(history)
        self._calculate_surprises(history)
        self._calculate_consistency(history)
        self._calculate_reactions(history)
        
        self._histories[symbol] = history
        return history
    
    def get_history(self, symbol: str) -> Optional[EarningsHistory]:
        """Get earnings history for a symbol."""
        return self._histories.get(symbol)
    
    def _calculate_beat_rates(self, history: EarningsHistory) -> None:
        """Calculate beat rates for EPS and revenue."""
        if not history.quarters:
            return
        
        eps_beats = 0
        revenue_beats = 0
        total = len(history.quarters)
        
        for q in history.quarters:
            if q.eps_surprise_pct > BEAT_THRESHOLD:
                eps_beats += 1
            if q.revenue_surprise_pct > BEAT_THRESHOLD:
                revenue_beats += 1
        
        history.beat_rate_eps = eps_beats / total if total > 0 else 0
        history.beat_rate_revenue = revenue_beats / total if total > 0 else 0
    
    def _calculate_surprises(self, history: EarningsHistory) -> None:
        """Calculate average surprise percentages."""
        if not history.quarters:
            return
        
        eps_surprises = [q.eps_surprise_pct for q in history.quarters]
        revenue_surprises = [q.revenue_surprise_pct for q in history.quarters]
        
        history.avg_surprise_eps = sum(eps_surprises) / len(eps_surprises)
        history.avg_surprise_revenue = sum(revenue_surprises) / len(revenue_surprises)
    
    def _calculate_consistency(self, history: EarningsHistory) -> None:
        """Calculate consecutive beats/misses."""
        if not history.quarters:
            return
        
        # Start from most recent
        quarters = list(reversed(history.quarters))
        
        # Count consecutive beats
        beats = 0
        for q in quarters:
            if q.eps_surprise_pct > BEAT_THRESHOLD:
                beats += 1
            else:
                break
        history.consecutive_beats = beats
        
        # Count consecutive misses
        misses = 0
        for q in quarters:
            if q.eps_surprise_pct < MISS_THRESHOLD:
                misses += 1
            else:
                break
        history.consecutive_misses = misses
    
    def _calculate_reactions(self, history: EarningsHistory) -> None:
        """Calculate average price reactions."""
        if not history.quarters:
            return
        
        beat_reactions = []
        miss_reactions = []
        
        for q in history.quarters:
            if q.eps_surprise_pct > BEAT_THRESHOLD:
                beat_reactions.append(q.price_change_1d)
            elif q.eps_surprise_pct < MISS_THRESHOLD:
                miss_reactions.append(q.price_change_1d)
        
        history.avg_reaction_beat = sum(beat_reactions) / len(beat_reactions) if beat_reactions else 0
        history.avg_reaction_miss = sum(miss_reactions) / len(miss_reactions) if miss_reactions else 0
    
    def get_surprise_pattern(self, symbol: str) -> dict:
        """Analyze surprise patterns.
        
        Returns:
            Dict with pattern analysis.
        """
        history = self.get_history(symbol)
        if not history or not history.quarters:
            return {"pattern": "unknown"}
        
        # Count by type
        beats = 0
        meets = 0
        misses = 0
        
        for q in history.quarters:
            st = q.surprise_type
            if st == SurpriseType.BEAT:
                beats += 1
            elif st == SurpriseType.MISS:
                misses += 1
            else:
                meets += 1
        
        total = len(history.quarters)
        
        # Determine pattern
        if beats >= total * 0.75:
            pattern = "consistent_beater"
        elif misses >= total * 0.5:
            pattern = "frequent_misser"
        elif history.consecutive_beats >= 4:
            pattern = "on_streak"
        else:
            pattern = "mixed"
        
        return {
            "pattern": pattern,
            "beats": beats,
            "meets": meets,
            "misses": misses,
            "total": total,
            "beat_rate": beats / total if total > 0 else 0,
        }
    
    def get_seasonal_pattern(self, symbol: str) -> dict:
        """Analyze seasonal patterns by quarter.
        
        Returns:
            Dict with Q1-Q4 analysis.
        """
        history = self.get_history(symbol)
        if not history or not history.quarters:
            return {}
        
        by_quarter = {"Q1": [], "Q2": [], "Q3": [], "Q4": []}
        
        for q in history.quarters:
            quarter_num = q.fiscal_quarter[:2]
            if quarter_num in by_quarter:
                by_quarter[quarter_num].append(q.eps_surprise_pct)
        
        result = {}
        for quarter, surprises in by_quarter.items():
            if surprises:
                result[quarter] = {
                    "avg_surprise": sum(surprises) / len(surprises),
                    "beat_rate": sum(1 for s in surprises if s > BEAT_THRESHOLD) / len(surprises),
                    "count": len(surprises),
                }
        
        return result
    
    def compare_to_sector(
        self,
        symbol: str,
        sector_symbols: list[str],
    ) -> dict:
        """Compare earnings metrics to sector peers.
        
        Returns:
            Dict with comparison metrics.
        """
        history = self.get_history(symbol)
        if not history:
            return {}
        
        # Get sector histories
        sector_beat_rates = []
        sector_surprises = []
        
        for peer in sector_symbols:
            peer_history = self.get_history(peer)
            if peer_history and peer != symbol:
                sector_beat_rates.append(peer_history.beat_rate_eps)
                sector_surprises.append(peer_history.avg_surprise_eps)
        
        if not sector_beat_rates:
            return {"vs_sector": "no_data"}
        
        sector_avg_beat = sum(sector_beat_rates) / len(sector_beat_rates)
        sector_avg_surprise = sum(sector_surprises) / len(sector_surprises)
        
        return {
            "beat_rate": history.beat_rate_eps,
            "sector_beat_rate": sector_avg_beat,
            "beat_rate_vs_sector": history.beat_rate_eps - sector_avg_beat,
            "avg_surprise": history.avg_surprise_eps,
            "sector_avg_surprise": sector_avg_surprise,
            "surprise_vs_sector": history.avg_surprise_eps - sector_avg_surprise,
        }


def generate_sample_history() -> HistoryAnalyzer:
    """Generate sample earnings history for testing."""
    analyzer = HistoryAnalyzer()
    
    # AAPL sample data
    aapl_quarters = [
        QuarterlyEarnings(
            symbol="AAPL", fiscal_quarter="Q1 2025",
            report_date=date(2025, 1, 30),
            eps_estimate=2.10, eps_actual=2.18,
            revenue_estimate=118e9, revenue_actual=119.5e9,
            price_before=185.0, price_after=192.0,
            price_change_1d=0.038, price_change_5d=0.045,
        ),
        QuarterlyEarnings(
            symbol="AAPL", fiscal_quarter="Q4 2024",
            report_date=date(2024, 10, 31),
            eps_estimate=1.60, eps_actual=1.64,
            revenue_estimate=94e9, revenue_actual=94.9e9,
            price_before=175.0, price_after=178.0,
            price_change_1d=0.017, price_change_5d=0.025,
        ),
        QuarterlyEarnings(
            symbol="AAPL", fiscal_quarter="Q3 2024",
            report_date=date(2024, 8, 1),
            eps_estimate=1.35, eps_actual=1.40,
            revenue_estimate=84e9, revenue_actual=85.8e9,
            price_before=195.0, price_after=205.0,
            price_change_1d=0.051, price_change_5d=0.062,
        ),
        QuarterlyEarnings(
            symbol="AAPL", fiscal_quarter="Q2 2024",
            report_date=date(2024, 5, 2),
            eps_estimate=1.50, eps_actual=1.53,
            revenue_estimate=90e9, revenue_actual=90.8e9,
            price_before=170.0, price_after=173.0,
            price_change_1d=0.018, price_change_5d=0.022,
        ),
    ]
    
    analyzer.add_quarterly_data("AAPL", aapl_quarters)
    
    return analyzer
