"""Historical Economic Data Analysis.

Analyze historical releases and market reactions.
"""

from datetime import datetime, date, timezone
from typing import Optional
import logging
import statistics

from src.economic.models import (
    EconomicEvent,
    HistoricalRelease,
    EventStats,
)

logger = logging.getLogger(__name__)


class HistoryAnalyzer:
    """Analyzes historical economic releases.
    
    Example:
        analyzer = HistoryAnalyzer()
        
        # Add historical data
        analyzer.add_release(HistoricalRelease(
            event_name="Non-Farm Payrolls",
            release_date=datetime(2024, 1, 5),
            actual=216.0,
            forecast=170.0,
            previous=199.0,
            spx_1h_change=0.35,
        ))
        
        # Get statistics
        stats = analyzer.get_stats("Non-Farm Payrolls")
        print(f"Beat rate: {stats.beat_rate:.1f}%")
    """
    
    def __init__(self):
        self._releases: dict[str, list[HistoricalRelease]] = {}  # event_name -> releases
    
    # =========================================================================
    # Data Management
    # =========================================================================
    
    def add_release(self, release: HistoricalRelease) -> None:
        """Add a historical release."""
        if release.event_name not in self._releases:
            self._releases[release.event_name] = []
        
        # Calculate surprise if not set
        if release.surprise == 0 and release.forecast != 0:
            release.surprise = release.actual - release.forecast
            release.surprise_pct = (release.surprise / abs(release.forecast)) * 100
        
        self._releases[release.event_name].append(release)
        
        # Sort by date
        self._releases[release.event_name].sort(
            key=lambda r: r.release_date or datetime.min,
            reverse=True
        )
    
    def get_history(
        self,
        event_name: str,
        limit: int = 12,
    ) -> list[HistoricalRelease]:
        """Get release history for an event."""
        releases = self._releases.get(event_name, [])
        return releases[:limit]
    
    # =========================================================================
    # Statistics
    # =========================================================================
    
    def get_stats(self, event_name: str) -> EventStats:
        """Calculate statistics for an event."""
        releases = self._releases.get(event_name, [])
        
        if not releases:
            return EventStats(event_name=event_name)
        
        # Count beats/misses
        beats = sum(1 for r in releases if r.surprise > 0)
        misses = sum(1 for r in releases if r.surprise < 0)
        inline = len(releases) - beats - misses
        
        # Surprise stats
        surprises = [r.surprise for r in releases]
        surprise_pcts = [r.surprise_pct for r in releases if r.surprise_pct != 0]
        
        # Market reaction stats
        spx_reactions = [r.spx_1h_change for r in releases if r.spx_1h_change != 0]
        vix_changes = [r.vix_change for r in releases if r.vix_change != 0]
        
        return EventStats(
            event_name=event_name,
            total_releases=len(releases),
            beat_count=beats,
            miss_count=misses,
            inline_count=inline,
            avg_surprise=statistics.mean(surprises) if surprises else 0,
            avg_surprise_pct=statistics.mean(surprise_pcts) if surprise_pcts else 0,
            surprise_std=statistics.stdev(surprises) if len(surprises) > 1 else 0,
            avg_spx_reaction=statistics.mean(spx_reactions) if spx_reactions else 0,
            avg_vix_change=statistics.mean(vix_changes) if vix_changes else 0,
            max_spx_move=max(abs(r) for r in spx_reactions) if spx_reactions else 0,
        )
    
    def calculate_surprise_std(self, event_name: str) -> float:
        """Calculate standard deviation of surprises."""
        releases = self._releases.get(event_name, [])
        surprises = [r.surprise for r in releases]
        
        if len(surprises) < 2:
            return 0.0
        
        return statistics.stdev(surprises)
    
    def get_surprise_zscore(
        self,
        event_name: str,
        actual: float,
        forecast: float,
    ) -> float:
        """Calculate z-score for a surprise."""
        surprise = actual - forecast
        std = self.calculate_surprise_std(event_name)
        
        if std == 0:
            return 0.0
        
        return surprise / std
    
    # =========================================================================
    # Market Reaction Analysis
    # =========================================================================
    
    def get_typical_reaction(
        self,
        event_name: str,
        surprise_direction: str = "beat",  # beat, miss
    ) -> dict:
        """Get typical market reaction for beats/misses."""
        releases = self._releases.get(event_name, [])
        
        if surprise_direction == "beat":
            filtered = [r for r in releases if r.surprise > 0]
        else:
            filtered = [r for r in releases if r.surprise < 0]
        
        if not filtered:
            return {
                "count": 0,
                "avg_spx": 0,
                "avg_vix": 0,
                "avg_dxy": 0,
            }
        
        return {
            "count": len(filtered),
            "avg_spx": statistics.mean([r.spx_1h_change for r in filtered]),
            "avg_vix": statistics.mean([r.vix_change for r in filtered]) if any(r.vix_change for r in filtered) else 0,
            "avg_dxy": statistics.mean([r.dxy_1h_change for r in filtered]) if any(r.dxy_1h_change for r in filtered) else 0,
        }
    
    def get_reaction_by_surprise_size(
        self,
        event_name: str,
    ) -> dict:
        """Analyze reaction by surprise magnitude."""
        releases = self._releases.get(event_name, [])
        
        if not releases:
            return {}
        
        # Categorize by surprise size
        small = [r for r in releases if abs(r.surprise_pct) < 5]
        medium = [r for r in releases if 5 <= abs(r.surprise_pct) < 15]
        large = [r for r in releases if abs(r.surprise_pct) >= 15]
        
        result = {}
        
        for name, group in [("small", small), ("medium", medium), ("large", large)]:
            if group:
                result[name] = {
                    "count": len(group),
                    "avg_spx": statistics.mean([r.spx_1h_change for r in group]),
                    "avg_surprise_pct": statistics.mean([abs(r.surprise_pct) for r in group]),
                }
        
        return result
    
    def get_seasonal_pattern(
        self,
        event_name: str,
    ) -> dict[int, float]:
        """Analyze seasonal patterns (by month)."""
        releases = self._releases.get(event_name, [])
        
        monthly_surprises: dict[int, list[float]] = {i: [] for i in range(1, 13)}
        
        for r in releases:
            if r.release_date:
                month = r.release_date.month
                monthly_surprises[month].append(r.surprise_pct)
        
        return {
            month: statistics.mean(surprises) if surprises else 0
            for month, surprises in monthly_surprises.items()
        }
    
    # =========================================================================
    # Comparison
    # =========================================================================
    
    def compare_to_history(
        self,
        event_name: str,
        actual: float,
        forecast: float,
    ) -> dict:
        """Compare a release to historical patterns."""
        stats = self.get_stats(event_name)
        surprise = actual - forecast
        surprise_pct = ((actual - forecast) / abs(forecast)) * 100 if forecast != 0 else 0
        
        z_score = self.get_surprise_zscore(event_name, actual, forecast)
        
        # Determine if surprise is unusual
        is_unusual = abs(z_score) > 2
        
        # Get expected reaction
        direction = "beat" if surprise > 0 else "miss"
        typical = self.get_typical_reaction(event_name, direction)
        
        return {
            "surprise": surprise,
            "surprise_pct": surprise_pct,
            "z_score": z_score,
            "is_unusual": is_unusual,
            "historical_beat_rate": stats.beat_rate,
            "expected_spx_reaction": typical.get("avg_spx", 0),
            "expected_vix_change": typical.get("avg_vix", 0),
        }


def generate_sample_history() -> HistoryAnalyzer:
    """Generate sample historical data."""
    analyzer = HistoryAnalyzer()
    
    # Sample NFP history
    nfp_data = [
        (datetime(2024, 1, 5), 216.0, 170.0, 199.0, 0.35, 0.8, -0.2, -1.5),
        (datetime(2023, 12, 8), 199.0, 180.0, 150.0, 0.15, 0.4, -0.1, -0.5),
        (datetime(2023, 11, 3), 150.0, 170.0, 297.0, -0.25, 0.6, 0.3, 1.2),
        (datetime(2023, 10, 6), 336.0, 170.0, 227.0, 0.45, 1.2, -0.4, -2.0),
        (datetime(2023, 9, 1), 187.0, 170.0, 157.0, 0.10, 0.3, -0.1, -0.3),
    ]
    
    for rel_date, actual, forecast, prev, spx, vix, dxy, tnx in nfp_data:
        analyzer.add_release(HistoricalRelease(
            event_name="Non-Farm Payrolls",
            release_date=rel_date,
            actual=actual,
            forecast=forecast,
            previous=prev,
            spx_1h_change=spx,
            vix_change=vix,
            dxy_1h_change=dxy,
            tnx_change=tnx,
        ))
    
    # Sample CPI history
    cpi_data = [
        (datetime(2024, 1, 11), 3.4, 3.2, 3.1, -0.20, 1.5, 0.3, 5.0),
        (datetime(2023, 12, 12), 3.1, 3.1, 3.2, 0.10, 0.5, -0.1, -2.0),
        (datetime(2023, 11, 14), 3.2, 3.3, 3.7, 0.50, -2.0, -0.5, -8.0),
        (datetime(2023, 10, 12), 3.7, 3.6, 3.7, -0.15, 0.8, 0.2, 3.0),
    ]
    
    for rel_date, actual, forecast, prev, spx, vix, dxy, tnx in cpi_data:
        analyzer.add_release(HistoricalRelease(
            event_name="CPI",
            release_date=rel_date,
            actual=actual,
            forecast=forecast,
            previous=prev,
            spx_1h_change=spx,
            vix_change=vix,
            dxy_1h_change=dxy,
            tnx_change=tnx,
        ))
    
    return analyzer
