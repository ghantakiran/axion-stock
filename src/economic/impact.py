"""Market Impact Analysis.

Analyze and predict market impact of economic events.
"""

from datetime import datetime, timezone
from typing import Optional
import logging

from src.economic.config import (
    ImpactLevel,
    EventCategory,
    TYPICAL_REACTIONS,
)
from src.economic.models import (
    EconomicEvent,
    HistoricalRelease,
    MarketImpact,
)
from src.economic.history import HistoryAnalyzer

logger = logging.getLogger(__name__)


# Sector sensitivity to economic events
SECTOR_SENSITIVITY = {
    "Non-Farm Payrolls": {
        "Consumer Discretionary": 1.2,
        "Financials": 1.1,
        "Industrials": 1.0,
        "Technology": 0.9,
        "Healthcare": 0.6,
        "Utilities": 0.5,
    },
    "CPI": {
        "Real Estate": 1.5,
        "Financials": 1.3,
        "Consumer Staples": 1.1,
        "Utilities": 1.0,
        "Technology": 0.8,
        "Healthcare": 0.7,
    },
    "Fed Interest Rate Decision": {
        "Financials": 1.5,
        "Real Estate": 1.4,
        "Utilities": 1.2,
        "Technology": 1.0,
        "Consumer Discretionary": 1.0,
        "Healthcare": 0.7,
    },
    "Retail Sales": {
        "Consumer Discretionary": 1.5,
        "Consumer Staples": 1.2,
        "Industrials": 0.9,
        "Financials": 0.8,
    },
}


class ImpactAnalyzer:
    """Analyzes market impact of economic events.
    
    Example:
        analyzer = ImpactAnalyzer(history_analyzer)
        
        # Get expected impact for upcoming event
        impact = analyzer.analyze_event(event)
        print(f"Expected SPX move: {impact.historical_avg_move}%")
        
        # Get sector impacts
        for sector, sensitivity in impact.sector_impacts.items():
            print(f"{sector}: {sensitivity}x average")
    """
    
    def __init__(self, history: Optional[HistoryAnalyzer] = None):
        self.history = history or HistoryAnalyzer()
    
    def analyze_event(self, event: EconomicEvent) -> MarketImpact:
        """Analyze expected market impact of an event.
        
        Args:
            event: Economic event.
            
        Returns:
            MarketImpact analysis.
        """
        impact = MarketImpact(
            event_id=event.event_id,
            event_name=event.name,
        )
        
        # Get historical stats
        stats = self.history.get_stats(event.name)
        
        # Expected volatility based on impact level
        vol_multiplier = {
            ImpactLevel.LOW: 0.5,
            ImpactLevel.MEDIUM: 1.0,
            ImpactLevel.HIGH: 2.0,
        }
        impact.expected_volatility = vol_multiplier.get(event.impact, 1.0)
        
        # Historical average move
        if stats.max_spx_move > 0:
            impact.historical_avg_move = stats.avg_spx_reaction
        else:
            # Use typical reactions if no history
            typical = TYPICAL_REACTIONS.get(event.name, {})
            avg_move = (
                abs(typical.get("spx_surprise_up", 0)) +
                abs(typical.get("spx_surprise_down", 0))
            ) / 2
            impact.historical_avg_move = avg_move
        
        # Sector impacts
        impact.sector_impacts = SECTOR_SENSITIVITY.get(event.name, {})
        
        # Pre-event trading notes
        impact.pre_event_notes = self._generate_pre_event_notes(event, stats)
        
        return impact
    
    def analyze_release(
        self,
        event: EconomicEvent,
        market_data: Optional[dict] = None,
    ) -> MarketImpact:
        """Analyze actual market impact after release.
        
        Args:
            event: Released economic event.
            market_data: Current market data (optional).
            
        Returns:
            MarketImpact with actual reaction.
        """
        impact = self.analyze_event(event)
        
        if not event.is_released:
            return impact
        
        # Add post-event analysis
        if market_data:
            impact.actual_spx_change = market_data.get("spx_change")
            impact.actual_vix_change = market_data.get("vix_change")
            impact.actual_dxy_change = market_data.get("dxy_change")
            
            # Compare to history
            if impact.historical_avg_move > 0 and impact.actual_spx_change:
                ratio = abs(impact.actual_spx_change) / impact.historical_avg_move
                if ratio < 0.5:
                    impact.reaction_vs_history = "muted"
                elif ratio > 1.5:
                    impact.reaction_vs_history = "amplified"
                else:
                    impact.reaction_vs_history = "normal"
        
        # Post-event notes
        impact.post_event_notes = self._generate_post_event_notes(event, impact)
        
        return impact
    
    def _generate_pre_event_notes(
        self,
        event: EconomicEvent,
        stats,
    ) -> list[str]:
        """Generate pre-event trading notes."""
        notes = []
        
        # Impact level warning
        if event.impact == ImpactLevel.HIGH:
            notes.append("⚠️ High-impact event - expect elevated volatility")
        
        # Historical beat rate
        if stats.total_releases > 0:
            if stats.beat_rate > 60:
                notes.append(f"📈 Historical beat rate: {stats.beat_rate:.0f}% (tends to beat)")
            elif stats.beat_rate < 40:
                notes.append(f"📉 Historical beat rate: {stats.beat_rate:.0f}% (tends to miss)")
        
        # Typical reactions
        typical = TYPICAL_REACTIONS.get(event.name, {})
        if typical:
            notes.append(f"📊 Typical SPX reaction: ±{abs(typical.get('spx_surprise_up', 0.3)):.1f}%")
        
        # Category-specific notes
        if event.category == EventCategory.INFLATION:
            notes.append("💡 Higher-than-expected = hawkish (negative for stocks)")
        elif event.category == EventCategory.EMPLOYMENT:
            notes.append("💡 Strong jobs = positive sentiment but may be hawkish")
        elif event.category == EventCategory.CENTRAL_BANK:
            notes.append("💡 Focus on forward guidance, not just the decision")
        
        return notes
    
    def _generate_post_event_notes(
        self,
        event: EconomicEvent,
        impact: MarketImpact,
    ) -> list[str]:
        """Generate post-event analysis notes."""
        notes = []
        
        # Surprise analysis
        if event.surprise_pct is not None:
            if abs(event.surprise_pct) > 10:
                notes.append(f"🎯 Significant surprise: {event.surprise_pct:+.1f}%")
            
            direction = "beat" if event.surprise_pct > 0 else "miss"
            notes.append(f"📊 Result: {direction} consensus by {abs(event.surprise_pct):.1f}%")
        
        # Reaction analysis
        if impact.reaction_vs_history:
            if impact.reaction_vs_history == "muted":
                notes.append("📉 Market reaction more muted than typical")
            elif impact.reaction_vs_history == "amplified":
                notes.append("📈 Market reaction stronger than typical")
        
        # Interpretation
        if event.category == EventCategory.INFLATION:
            if event.surprise_pct and event.surprise_pct > 0:
                notes.append("🔥 Hotter inflation = more hawkish Fed expectations")
            elif event.surprise_pct and event.surprise_pct < 0:
                notes.append("❄️ Cooler inflation = dovish signal, positive for risk")
        
        return notes
    
    def get_sector_exposure(self, event: EconomicEvent) -> dict[str, float]:
        """Get sector sensitivity for an event."""
        return SECTOR_SENSITIVITY.get(event.name, {})
    
    def compare_events(
        self,
        events: list[EconomicEvent],
    ) -> list[dict]:
        """Compare impact of multiple events."""
        comparisons = []
        
        for event in events:
            stats = self.history.get_stats(event.name)
            
            comparisons.append({
                "name": event.name,
                "impact": event.impact.value,
                "avg_spx_reaction": stats.avg_spx_reaction,
                "beat_rate": stats.beat_rate,
                "total_releases": stats.total_releases,
            })
        
        # Sort by average reaction
        comparisons.sort(key=lambda x: abs(x["avg_spx_reaction"]), reverse=True)
        
        return comparisons
    
    def get_most_impactful(
        self,
        events: list[EconomicEvent],
        top_n: int = 5,
    ) -> list[EconomicEvent]:
        """Get most impactful events from a list."""
        # Score each event
        scored = []
        for event in events:
            score = 0
            
            # Impact level
            if event.impact == ImpactLevel.HIGH:
                score += 3
            elif event.impact == ImpactLevel.MEDIUM:
                score += 2
            else:
                score += 1
            
            # Historical volatility
            stats = self.history.get_stats(event.name)
            score += min(2, stats.max_spx_move)
            
            scored.append((event, score))
        
        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return [e for e, _ in scored[:top_n]]
