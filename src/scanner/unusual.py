"""Unusual Activity Detection.

Detect unusual volume, price movements, and other anomalies.
"""

from datetime import datetime, timezone
from typing import Optional
import logging
import math

from src.scanner.config import (
    ActivityType,
    UnusualActivityConfig,
    DEFAULT_UNUSUAL_CONFIG,
)
from src.scanner.models import UnusualActivity

logger = logging.getLogger(__name__)


class UnusualActivityDetector:
    """Detects unusual market activity.
    
    Identifies volume surges, price spikes, and other anomalies
    that may indicate significant trading interest.
    
    Example:
        detector = UnusualActivityDetector()
        
        activities = detector.scan(market_data, historical_data)
        for activity in activities:
            print(f"{activity.symbol}: {activity.activity_type.value}")
    """
    
    def __init__(self, config: Optional[UnusualActivityConfig] = None):
        self.config = config or DEFAULT_UNUSUAL_CONFIG
        self._activities: list[UnusualActivity] = []
    
    def scan(
        self,
        current_data: dict[str, dict],
        historical_data: Optional[dict[str, dict]] = None,
    ) -> list[UnusualActivity]:
        """Scan for unusual activity.
        
        Args:
            current_data: Current market data (symbol -> data dict).
            historical_data: Historical stats (symbol -> {avg_volume, std_volume, ...}).
            
        Returns:
            List of detected UnusualActivity.
        """
        activities = []
        historical_data = historical_data or {}
        
        for symbol, data in current_data.items():
            hist = historical_data.get(symbol, {})
            
            # Check volume
            volume_activity = self._check_volume(symbol, data, hist)
            if volume_activity:
                activities.append(volume_activity)
            
            # Check price
            price_activity = self._check_price(symbol, data, hist)
            if price_activity:
                activities.append(price_activity)
            
            # Check gap
            gap_activity = self._check_gap(symbol, data, hist)
            if gap_activity:
                activities.append(gap_activity)
        
        # Sort by deviation
        activities.sort(key=lambda a: a.deviation, reverse=True)
        
        self._activities = activities
        return activities
    
    def _check_volume(
        self,
        symbol: str,
        data: dict,
        hist: dict,
    ) -> Optional[UnusualActivity]:
        """Check for unusual volume."""
        volume = data.get("volume", 0)
        avg_volume = hist.get("avg_volume", data.get("avg_volume", 0))
        std_volume = hist.get("std_volume", avg_volume * 0.5)  # Estimate
        
        if avg_volume == 0 or std_volume == 0:
            return None
        
        # Calculate z-score
        z_score = (volume - avg_volume) / std_volume
        
        if z_score >= self.config.volume_std_threshold:
            relative_volume = volume / avg_volume if avg_volume > 0 else 0
            
            return UnusualActivity(
                symbol=symbol,
                company_name=data.get("name", ""),
                activity_type=ActivityType.VOLUME_SURGE,
                current_value=volume,
                normal_value=avg_volume,
                deviation=z_score,
                percentile=self._z_to_percentile(z_score),
                price=data.get("price", 0),
                change_pct=data.get("change_pct", 0),
                description=f"Volume {relative_volume:.1f}x average ({z_score:.1f} std dev)",
            )
        
        return None
    
    def _check_price(
        self,
        symbol: str,
        data: dict,
        hist: dict,
    ) -> Optional[UnusualActivity]:
        """Check for unusual price movement."""
        change_pct = abs(data.get("change_pct", 0))
        avg_change = hist.get("avg_daily_change", 2.0)  # Default 2%
        std_change = hist.get("std_daily_change", 1.0)  # Default 1%
        
        if std_change == 0:
            return None
        
        z_score = (change_pct - avg_change) / std_change
        
        if z_score >= self.config.price_std_threshold:
            direction = "up" if data.get("change_pct", 0) > 0 else "down"
            
            return UnusualActivity(
                symbol=symbol,
                company_name=data.get("name", ""),
                activity_type=ActivityType.PRICE_SPIKE,
                current_value=change_pct,
                normal_value=avg_change,
                deviation=z_score,
                percentile=self._z_to_percentile(z_score),
                price=data.get("price", 0),
                change_pct=data.get("change_pct", 0),
                description=f"Price {direction} {change_pct:.1f}% ({z_score:.1f} std dev)",
            )
        
        return None
    
    def _check_gap(
        self,
        symbol: str,
        data: dict,
        hist: dict,
    ) -> Optional[UnusualActivity]:
        """Check for unusual gap."""
        gap_pct = abs(data.get("gap_pct", 0))
        avg_gap = hist.get("avg_gap", 0.5)  # Default 0.5%
        std_gap = hist.get("std_gap", 0.5)  # Default 0.5%
        
        if std_gap == 0 or gap_pct < 2.0:  # Minimum 2% gap
            return None
        
        z_score = (gap_pct - avg_gap) / std_gap
        
        if z_score >= 2.0:  # Lower threshold for gaps
            direction = "up" if data.get("gap_pct", 0) > 0 else "down"
            
            return UnusualActivity(
                symbol=symbol,
                company_name=data.get("name", ""),
                activity_type=ActivityType.GAP,
                current_value=gap_pct,
                normal_value=avg_gap,
                deviation=z_score,
                percentile=self._z_to_percentile(z_score),
                price=data.get("price", 0),
                change_pct=data.get("change_pct", 0),
                description=f"Gap {direction} {gap_pct:.1f}%",
            )
        
        return None
    
    def _z_to_percentile(self, z: float) -> float:
        """Convert z-score to percentile (approximate)."""
        # Using error function approximation
        return 0.5 * (1 + math.erf(z / math.sqrt(2))) * 100
    
    def get_activities(
        self,
        activity_type: Optional[ActivityType] = None,
        min_deviation: float = 0,
    ) -> list[UnusualActivity]:
        """Get detected activities with optional filters.
        
        Args:
            activity_type: Filter by type.
            min_deviation: Minimum deviation threshold.
            
        Returns:
            Filtered list of activities.
        """
        activities = self._activities
        
        if activity_type:
            activities = [a for a in activities if a.activity_type == activity_type]
        
        if min_deviation > 0:
            activities = [a for a in activities if a.deviation >= min_deviation]
        
        return activities
    
    def get_top_volume_surges(self, limit: int = 10) -> list[UnusualActivity]:
        """Get top volume surges."""
        volume_activities = [
            a for a in self._activities
            if a.activity_type == ActivityType.VOLUME_SURGE
        ]
        return volume_activities[:limit]
    
    def get_top_movers(self, limit: int = 10) -> list[UnusualActivity]:
        """Get top price movers."""
        price_activities = [
            a for a in self._activities
            if a.activity_type == ActivityType.PRICE_SPIKE
        ]
        return price_activities[:limit]
    
    def get_gaps(self, limit: int = 10) -> list[UnusualActivity]:
        """Get significant gaps."""
        gap_activities = [
            a for a in self._activities
            if a.activity_type == ActivityType.GAP
        ]
        return gap_activities[:limit]
