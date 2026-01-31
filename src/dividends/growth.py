"""Dividend Growth Analysis.

Track dividend growth history and identify aristocrats/kings.
"""

from datetime import date
from typing import Optional
import logging
import math

from src.dividends.config import (
    DividendStatus,
    KING_YEARS,
    ARISTOCRAT_YEARS,
    ACHIEVER_YEARS,
    CONTENDER_YEARS,
)
from src.dividends.models import DividendGrowth, DividendRecord

logger = logging.getLogger(__name__)


class GrowthAnalyzer:
    """Analyzes dividend growth history.
    
    Calculates growth rates, tracks consecutive increases,
    and identifies dividend aristocrats and kings.
    
    Example:
        analyzer = GrowthAnalyzer()
        
        history = [
            DividendRecord(year=2023, amount=2.00),
            DividendRecord(year=2024, amount=2.10),
            ...
        ]
        
        growth = analyzer.analyze("AAPL", history)
        print(f"5-year CAGR: {growth.cagr_5y:.1%}")
        print(f"Status: {growth.status.value}")
    """
    
    def __init__(self):
        self._growth_data: dict[str, DividendGrowth] = {}
    
    def analyze(
        self,
        symbol: str,
        history: list[DividendRecord],
        current_annual_dividend: float = 0.0,
    ) -> DividendGrowth:
        """Analyze dividend growth.
        
        Args:
            symbol: Stock symbol.
            history: Historical dividend records.
            current_annual_dividend: Current annual dividend.
            
        Returns:
            DividendGrowth analysis.
        """
        growth = DividendGrowth(
            symbol=symbol,
            dividend_history=history,
            current_annual_dividend=current_annual_dividend,
        )
        
        if not history:
            return growth
        
        # Sort history by year
        sorted_history = sorted(history, key=lambda r: r.year)
        
        # Calculate growth rates
        self._calculate_growth_rates(growth, sorted_history)
        
        # Calculate streak
        self._calculate_streak(growth, sorted_history)
        
        # Determine status
        growth.status = self._determine_status(growth.consecutive_increases)
        
        # Most recent increase
        if len(sorted_history) >= 2:
            prev = sorted_history[-2].amount
            curr = sorted_history[-1].amount
            if prev > 0:
                growth.most_recent_increase_pct = (curr - prev) / prev
        
        self._growth_data[symbol] = growth
        return growth
    
    def _calculate_growth_rates(
        self,
        growth: DividendGrowth,
        history: list[DividendRecord],
    ) -> None:
        """Calculate CAGR for different periods."""
        if len(history) < 2:
            return
        
        # Get annual dividends by year
        by_year = {}
        for record in history:
            year = record.year
            by_year[year] = by_year.get(year, 0) + record.amount
        
        years = sorted(by_year.keys())
        growth.years_of_dividends = len(years)
        
        if len(years) < 2:
            return
        
        latest_year = years[-1]
        latest_dividend = by_year[latest_year]
        
        # 1-year CAGR
        if len(years) >= 2:
            prev_year = years[-2]
            prev_dividend = by_year[prev_year]
            if prev_dividend > 0:
                growth.cagr_1y = (latest_dividend / prev_dividend) - 1
        
        # 3-year CAGR
        if len(years) >= 4:
            start_year = latest_year - 3
            if start_year in by_year and by_year[start_year] > 0:
                growth.cagr_3y = self._calculate_cagr(
                    by_year[start_year], latest_dividend, 3
                )
        
        # 5-year CAGR
        if len(years) >= 6:
            start_year = latest_year - 5
            if start_year in by_year and by_year[start_year] > 0:
                growth.cagr_5y = self._calculate_cagr(
                    by_year[start_year], latest_dividend, 5
                )
        
        # 10-year CAGR
        if len(years) >= 11:
            start_year = latest_year - 10
            if start_year in by_year and by_year[start_year] > 0:
                growth.cagr_10y = self._calculate_cagr(
                    by_year[start_year], latest_dividend, 10
                )
    
    def _calculate_cagr(
        self,
        start_value: float,
        end_value: float,
        years: int,
    ) -> float:
        """Calculate compound annual growth rate."""
        if start_value <= 0 or years <= 0:
            return 0.0
        
        return (end_value / start_value) ** (1 / years) - 1
    
    def _calculate_streak(
        self,
        growth: DividendGrowth,
        history: list[DividendRecord],
    ) -> None:
        """Calculate consecutive years of increases."""
        if len(history) < 2:
            growth.consecutive_increases = 0
            return
        
        # Get annual dividends by year
        by_year = {}
        for record in history:
            year = record.year
            by_year[year] = by_year.get(year, 0) + record.amount
        
        years = sorted(by_year.keys(), reverse=True)
        
        if len(years) < 2:
            growth.consecutive_increases = 0
            return
        
        streak = 0
        for i in range(len(years) - 1):
            current_year = years[i]
            prev_year = years[i + 1]
            
            # Check if consecutive years
            if current_year - prev_year != 1:
                break
            
            if by_year[current_year] > by_year[prev_year]:
                streak += 1
            else:
                break
        
        growth.consecutive_increases = streak
    
    def _determine_status(self, consecutive_years: int) -> DividendStatus:
        """Determine dividend aristocrat/king status."""
        if consecutive_years >= KING_YEARS:
            return DividendStatus.KING
        elif consecutive_years >= ARISTOCRAT_YEARS:
            return DividendStatus.ARISTOCRAT
        elif consecutive_years >= ACHIEVER_YEARS:
            return DividendStatus.ACHIEVER
        elif consecutive_years >= CONTENDER_YEARS:
            return DividendStatus.CONTENDER
        elif consecutive_years >= 1:
            return DividendStatus.CHALLENGER
        return DividendStatus.NONE
    
    def get_growth(self, symbol: str) -> Optional[DividendGrowth]:
        """Get growth data for a symbol."""
        return self._growth_data.get(symbol)
    
    def get_aristocrats(self) -> list[str]:
        """Get all dividend aristocrats (25+ years)."""
        return [
            symbol for symbol, growth in self._growth_data.items()
            if growth.consecutive_increases >= ARISTOCRAT_YEARS
        ]
    
    def get_kings(self) -> list[str]:
        """Get all dividend kings (50+ years)."""
        return [
            symbol for symbol, growth in self._growth_data.items()
            if growth.consecutive_increases >= KING_YEARS
        ]
    
    def screen_by_growth(
        self,
        min_cagr_5y: float = 0.05,
        min_streak: int = 5,
    ) -> list[str]:
        """Screen for dividend growth stocks.
        
        Args:
            min_cagr_5y: Minimum 5-year CAGR.
            min_streak: Minimum consecutive increases.
            
        Returns:
            List of qualifying symbols.
        """
        return [
            symbol for symbol, growth in self._growth_data.items()
            if growth.cagr_5y >= min_cagr_5y and growth.consecutive_increases >= min_streak
        ]
    
    def rank_by_growth(self) -> list[tuple[str, float]]:
        """Rank stocks by 5-year dividend growth.
        
        Returns:
            List of (symbol, cagr_5y) sorted by growth.
        """
        results = [
            (symbol, growth.cagr_5y)
            for symbol, growth in self._growth_data.items()
        ]
        return sorted(results, key=lambda x: x[1], reverse=True)


def generate_sample_growth_data() -> GrowthAnalyzer:
    """Generate sample growth data for testing."""
    analyzer = GrowthAnalyzer()
    
    # Sample data for dividend aristocrats
    samples = {
        "JNJ": {
            "years": 62,
            "history": [(2024, 4.96), (2023, 4.76), (2022, 4.52), (2021, 4.24), (2020, 4.04)],
            "current": 4.96,
        },
        "KO": {
            "years": 62,
            "history": [(2024, 1.94), (2023, 1.84), (2022, 1.76), (2021, 1.68), (2020, 1.64)],
            "current": 1.94,
        },
        "PG": {
            "years": 68,
            "history": [(2024, 4.03), (2023, 3.76), (2022, 3.52), (2021, 3.48), (2020, 3.16)],
            "current": 4.03,
        },
        "AAPL": {
            "years": 12,
            "history": [(2024, 0.96), (2023, 0.92), (2022, 0.88), (2021, 0.85), (2020, 0.80)],
            "current": 0.96,
        },
        "MSFT": {
            "years": 22,
            "history": [(2024, 3.00), (2023, 2.72), (2022, 2.48), (2021, 2.24), (2020, 2.04)],
            "current": 3.00,
        },
    }
    
    for symbol, data in samples.items():
        records = [
            DividendRecord(symbol=symbol, year=year, amount=amount)
            for year, amount in data["history"]
        ]
        
        growth = analyzer.analyze(symbol, records, data["current"])
        # Override streak for demo purposes
        growth.consecutive_increases = data["years"]
        growth.status = analyzer._determine_status(data["years"])
    
    return analyzer
