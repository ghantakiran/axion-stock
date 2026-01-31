"""Earnings Price Reaction Analysis.

Analyze price reactions to earnings announcements.
"""

from datetime import date
from typing import Optional
import logging

from src.earnings.config import (
    ReactionDirection,
    SIGNIFICANT_GAP,
    HIGH_VOLUME_RATIO,
)
from src.earnings.models import EarningsReaction, QuarterlyEarnings

logger = logging.getLogger(__name__)


class ReactionAnalyzer:
    """Analyzes price reactions to earnings.
    
    Tracks gaps, extended moves, and drift patterns
    around earnings announcements.
    
    Example:
        analyzer = ReactionAnalyzer()
        
        reaction = analyzer.analyze_reaction("AAPL", "Q1 2024", price_data)
        print(f"Gap: {reaction.gap_open_pct:.1%}")
        print(f"5-day move: {reaction.price_change_5d:.1%}")
    """
    
    def __init__(self):
        self._reactions: dict[str, EarningsReaction] = {}  # key: symbol_quarter
    
    def _make_key(self, symbol: str, fiscal_quarter: str) -> str:
        """Create lookup key."""
        return f"{symbol}_{fiscal_quarter}"
    
    def record_reaction(
        self,
        symbol: str,
        fiscal_quarter: str,
        report_date: date,
        # Pre-earnings
        price_5d_before: float,
        price_1d_before: float,
        volume_avg: float,
        iv_percentile: float = 0.0,
        # Earnings day
        open_price: float = 0.0,
        close_price: float = 0.0,
        high_price: float = 0.0,
        low_price: float = 0.0,
        volume: float = 0.0,
        # Post-earnings
        price_1d_after: float = 0.0,
        price_5d_after: float = 0.0,
        price_20d_after: float = 0.0,
    ) -> EarningsReaction:
        """Record a price reaction.
        
        Args:
            symbol: Stock symbol.
            fiscal_quarter: Quarter (e.g., "Q1 2024").
            report_date: Earnings date.
            ... price data ...
            
        Returns:
            EarningsReaction object.
        """
        reaction = EarningsReaction(
            symbol=symbol,
            fiscal_quarter=fiscal_quarter,
            report_date=report_date,
            price_5d_before=price_5d_before,
            price_1d_before=price_1d_before,
            volume_avg_before=volume_avg,
            iv_percentile_before=iv_percentile,
        )
        
        # Calculate gap
        if price_1d_before > 0 and open_price > 0:
            reaction.gap_open_pct = (open_price - price_1d_before) / price_1d_before
        
        # Calculate close change
        if price_1d_before > 0 and close_price > 0:
            reaction.close_change_pct = (close_price - price_1d_before) / price_1d_before
        
        # Calculate range
        if low_price > 0 and high_price > 0:
            reaction.high_low_range_pct = (high_price - low_price) / low_price
        
        # Volume ratio
        if volume_avg > 0 and volume > 0:
            reaction.volume_ratio = volume / volume_avg
        
        # Extended reactions
        if price_1d_before > 0:
            if price_1d_after > 0:
                reaction.price_change_1d = (price_1d_after - price_1d_before) / price_1d_before
            if price_5d_after > 0:
                reaction.price_change_5d = (price_5d_after - price_1d_before) / price_1d_before
            if price_20d_after > 0:
                reaction.price_change_20d = (price_20d_after - price_1d_before) / price_1d_before
        
        # Pre-earnings drift
        if price_5d_before > 0 and price_1d_before > 0:
            reaction.pre_earnings_drift = (price_1d_before - price_5d_before) / price_5d_before
        
        # Post-earnings drift (difference between 5d and gap)
        if reaction.price_change_5d != 0 and reaction.gap_open_pct != 0:
            reaction.post_earnings_drift = reaction.price_change_5d - reaction.gap_open_pct
        
        key = self._make_key(symbol, fiscal_quarter)
        self._reactions[key] = reaction
        return reaction
    
    def get_reaction(
        self,
        symbol: str,
        fiscal_quarter: str,
    ) -> Optional[EarningsReaction]:
        """Get reaction for a symbol/quarter."""
        key = self._make_key(symbol, fiscal_quarter)
        return self._reactions.get(key)
    
    def get_all_reactions(self, symbol: str) -> list[EarningsReaction]:
        """Get all reactions for a symbol."""
        reactions = []
        for key, reaction in self._reactions.items():
            if reaction.symbol == symbol:
                reactions.append(reaction)
        return sorted(reactions, key=lambda r: r.report_date or date.min, reverse=True)
    
    def calculate_historical_stats(self, symbol: str) -> dict:
        """Calculate historical reaction statistics.
        
        Returns:
            Dict with summary statistics.
        """
        reactions = self.get_all_reactions(symbol)
        
        if not reactions:
            return {"count": 0}
        
        gaps = [r.gap_open_pct for r in reactions]
        changes_1d = [r.price_change_1d for r in reactions]
        changes_5d = [r.price_change_5d for r in reactions]
        
        # Gap statistics
        gap_up = sum(1 for g in gaps if g > SIGNIFICANT_GAP)
        gap_down = sum(1 for g in gaps if g < -SIGNIFICANT_GAP)
        
        # Fade analysis (gap reverses within the day)
        fades = 0
        for r in reactions:
            if r.gap_open_pct > 0 and r.close_change_pct < r.gap_open_pct:
                fades += 1
            elif r.gap_open_pct < 0 and r.close_change_pct > r.gap_open_pct:
                fades += 1
        
        return {
            "count": len(reactions),
            "avg_gap": sum(gaps) / len(gaps),
            "max_gap_up": max(gaps),
            "max_gap_down": min(gaps),
            "gap_up_count": gap_up,
            "gap_down_count": gap_down,
            "avg_1d_change": sum(changes_1d) / len(changes_1d),
            "avg_5d_change": sum(changes_5d) / len(changes_5d),
            "fade_rate": fades / len(reactions),
        }
    
    def analyze_reaction_by_surprise(
        self,
        symbol: str,
        quarters: list[QuarterlyEarnings],
    ) -> dict:
        """Analyze reactions based on surprise direction.
        
        Args:
            symbol: Stock symbol.
            quarters: Historical quarterly data.
            
        Returns:
            Dict with beat/miss reaction analysis.
        """
        beat_reactions = []
        miss_reactions = []
        
        for q in quarters:
            reaction = self.get_reaction(symbol, q.fiscal_quarter)
            if not reaction:
                continue
            
            if q.eps_surprise_pct > 0.01:  # Beat
                beat_reactions.append(reaction)
            elif q.eps_surprise_pct < -0.01:  # Miss
                miss_reactions.append(reaction)
        
        result = {}
        
        if beat_reactions:
            result["beat"] = {
                "count": len(beat_reactions),
                "avg_gap": sum(r.gap_open_pct for r in beat_reactions) / len(beat_reactions),
                "avg_5d": sum(r.price_change_5d for r in beat_reactions) / len(beat_reactions),
            }
        
        if miss_reactions:
            result["miss"] = {
                "count": len(miss_reactions),
                "avg_gap": sum(r.gap_open_pct for r in miss_reactions) / len(miss_reactions),
                "avg_5d": sum(r.price_change_5d for r in miss_reactions) / len(miss_reactions),
            }
        
        return result
    
    def get_extreme_reactions(
        self,
        threshold: float = 0.10,
    ) -> list[EarningsReaction]:
        """Get extreme reactions (large gaps).
        
        Args:
            threshold: Gap percentage threshold.
            
        Returns:
            List of extreme reactions.
        """
        extreme = []
        
        for reaction in self._reactions.values():
            if abs(reaction.gap_open_pct) >= threshold:
                extreme.append(reaction)
        
        return sorted(extreme, key=lambda r: abs(r.gap_open_pct), reverse=True)
    
    def screen_for_drift(
        self,
        min_drift: float = 0.03,
    ) -> dict[str, list[EarningsReaction]]:
        """Screen for stocks with significant post-earnings drift.
        
        Args:
            min_drift: Minimum drift threshold.
            
        Returns:
            Dict with "continuation" and "reversal" lists.
        """
        continuation = []  # Gap continues in same direction
        reversal = []      # Gap reverses
        
        for reaction in self._reactions.values():
            if abs(reaction.gap_open_pct) < SIGNIFICANT_GAP:
                continue
            
            drift = reaction.post_earnings_drift
            
            # Continuation: drift in same direction as gap
            if (reaction.gap_open_pct > 0 and drift > min_drift) or \
               (reaction.gap_open_pct < 0 and drift < -min_drift):
                continuation.append(reaction)
            
            # Reversal: drift in opposite direction
            if (reaction.gap_open_pct > 0 and drift < -min_drift) or \
               (reaction.gap_open_pct < 0 and drift > min_drift):
                reversal.append(reaction)
        
        return {
            "continuation": continuation,
            "reversal": reversal,
        }
