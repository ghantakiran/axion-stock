"""Sector Rotation Detection.

Detect rotation signals between sectors.
"""

from datetime import datetime, date, timedelta, timezone
from typing import Optional
import logging

from src.sectors.config import (
    SectorName,
    SignalStrength,
    Trend,
    SECTOR_CHARACTERISTICS,
)
from src.sectors.models import (
    Sector,
    RotationSignal,
    RotationPattern,
)
from src.sectors.rankings import SectorRankings

logger = logging.getLogger(__name__)


# Predefined rotation patterns
ROTATION_PATTERNS = {
    "risk_on": {
        "name": "Risk-On Rotation",
        "from_sectors": [SectorName.UTILITIES, SectorName.CONSUMER_STAPLES, SectorName.HEALTHCARE],
        "to_sectors": [SectorName.TECHNOLOGY, SectorName.CONSUMER_DISC, SectorName.FINANCIALS],
        "description": "Money flowing from defensive to cyclical/growth sectors",
    },
    "risk_off": {
        "name": "Risk-Off Rotation",
        "from_sectors": [SectorName.TECHNOLOGY, SectorName.CONSUMER_DISC, SectorName.FINANCIALS],
        "to_sectors": [SectorName.UTILITIES, SectorName.CONSUMER_STAPLES, SectorName.HEALTHCARE],
        "description": "Money flowing from cyclical to defensive sectors",
    },
    "inflation_trade": {
        "name": "Inflation Trade",
        "from_sectors": [SectorName.TECHNOLOGY, SectorName.CONSUMER_DISC],
        "to_sectors": [SectorName.ENERGY, SectorName.MATERIALS, SectorName.FINANCIALS],
        "description": "Rotation into inflation beneficiaries",
    },
    "growth_to_value": {
        "name": "Growth to Value Rotation",
        "from_sectors": [SectorName.TECHNOLOGY, SectorName.COMMUNICATION],
        "to_sectors": [SectorName.FINANCIALS, SectorName.ENERGY, SectorName.INDUSTRIALS],
        "description": "Rotation from growth to value sectors",
    },
    "rate_sensitive": {
        "name": "Rate Sensitive Rotation",
        "from_sectors": [SectorName.UTILITIES, SectorName.REAL_ESTATE],
        "to_sectors": [SectorName.FINANCIALS, SectorName.TECHNOLOGY],
        "description": "Rotation based on interest rate expectations",
    },
}


class RotationDetector:
    """Detects sector rotation signals.
    
    Example:
        detector = RotationDetector(rankings)
        
        signals = detector.detect_rotation()
        for signal in signals:
            print(f"{signal.from_sector.value} -> {signal.to_sector.value}")
    """
    
    def __init__(self, rankings: SectorRankings):
        self.rankings = rankings
        self._signals: list[RotationSignal] = []
        self._patterns: list[RotationPattern] = []
    
    def detect_rotation(
        self,
        min_rs_change: float = 0.03,
        lookback_periods: int = 1,
    ) -> list[RotationSignal]:
        """Detect rotation signals.
        
        Args:
            min_rs_change: Minimum RS change to trigger signal.
            lookback_periods: Periods to compare.
            
        Returns:
            List of rotation signals.
        """
        signals = []
        sectors = self.rankings.get_all_sectors()
        
        # Compare top vs bottom performers
        top = self.rankings.get_top_sectors(3, by="momentum")
        bottom = self.rankings.get_bottom_sectors(3, by="momentum")
        
        # Generate rotation signals from bottom to top
        for from_sector in bottom:
            for to_sector in top:
                # Calculate RS change
                rs_diff = to_sector.rs_ratio - from_sector.rs_ratio
                
                if rs_diff >= min_rs_change:
                    signal = self._create_signal(from_sector, to_sector, rs_diff)
                    signals.append(signal)
        
        self._signals = signals
        
        # Detect patterns
        self._detect_patterns()
        
        return signals
    
    def _create_signal(
        self,
        from_sector: Sector,
        to_sector: Sector,
        rs_change: float,
    ) -> RotationSignal:
        """Create a rotation signal."""
        # Determine signal strength
        if rs_change >= 0.10:
            strength = SignalStrength.STRONG
            confidence = 80
        elif rs_change >= 0.05:
            strength = SignalStrength.MODERATE
            confidence = 60
        else:
            strength = SignalStrength.WEAK
            confidence = 40
        
        # Check confirmations
        volume_confirmation = (
            to_sector.relative_volume > 1.2 if to_sector.relative_volume else False
        )
        breadth_confirmation = to_sector.pct_above_50ma > 60 if to_sector.pct_above_50ma else False
        
        # Adjust confidence
        if volume_confirmation:
            confidence += 10
        if breadth_confirmation:
            confidence += 10
        
        return RotationSignal(
            signal_date=date.today(),
            from_sector=from_sector.name,
            to_sector=to_sector.name,
            signal_type="rs_breakout",
            signal_strength=strength,
            confidence=min(100, confidence),
            rs_change=rs_change,
            volume_confirmation=volume_confirmation,
            breadth_confirmation=breadth_confirmation,
            description=f"Rotation from {from_sector.name.value} to {to_sector.name.value} "
                        f"(RS diff: {rs_change:.1%})",
        )
    
    def _detect_patterns(self) -> None:
        """Detect named rotation patterns."""
        patterns = []
        
        top_sectors = set(s.name for s in self.rankings.get_top_sectors(4))
        bottom_sectors = set(s.name for s in self.rankings.get_bottom_sectors(4))
        
        for pattern_id, pattern_data in ROTATION_PATTERNS.items():
            to_sectors = set(pattern_data["to_sectors"])
            from_sectors = set(pattern_data["from_sectors"])
            
            # Check if pattern matches
            to_match = len(top_sectors & to_sectors)
            from_match = len(bottom_sectors & from_sectors)
            
            if to_match >= 2 and from_match >= 2:
                confidence = (to_match + from_match) / (len(to_sectors) + len(from_sectors)) * 100
                
                pattern = RotationPattern(
                    name=pattern_data["name"],
                    from_sectors=list(from_sectors & bottom_sectors),
                    to_sectors=list(to_sectors & top_sectors),
                    description=pattern_data["description"],
                    is_active=True,
                    confidence=confidence,
                    start_date=date.today(),
                )
                patterns.append(pattern)
        
        self._patterns = patterns
    
    def get_signals(
        self,
        min_strength: Optional[SignalStrength] = None,
    ) -> list[RotationSignal]:
        """Get rotation signals."""
        signals = self._signals
        
        if min_strength:
            strength_order = {
                SignalStrength.WEAK: 0,
                SignalStrength.MODERATE: 1,
                SignalStrength.STRONG: 2,
            }
            min_level = strength_order[min_strength]
            signals = [
                s for s in signals
                if strength_order.get(s.signal_strength, 0) >= min_level
            ]
        
        return signals
    
    def get_active_patterns(self) -> list[RotationPattern]:
        """Get active rotation patterns."""
        return [p for p in self._patterns if p.is_active]
    
    def get_rotation_summary(self) -> dict:
        """Get rotation summary."""
        top = self.rankings.get_top_sectors(3)
        bottom = self.rankings.get_bottom_sectors(3)
        
        # Determine overall rotation direction
        top_cyclical = sum(
            1 for s in top
            if SECTOR_CHARACTERISTICS.get(s.name, {}).get("cyclical", False)
        )
        top_defensive = sum(
            1 for s in top
            if SECTOR_CHARACTERISTICS.get(s.name, {}).get("type") == "defensive"
        )
        
        if top_cyclical >= 2:
            direction = "Risk-On"
        elif top_defensive >= 2:
            direction = "Risk-Off"
        else:
            direction = "Mixed"
        
        return {
            "direction": direction,
            "top_sectors": [s.name.value for s in top],
            "bottom_sectors": [s.name.value for s in bottom],
            "signal_count": len(self._signals),
            "active_patterns": [p.name for p in self._patterns if p.is_active],
        }
    
    def is_risk_on(self) -> bool:
        """Check if market is in risk-on mode."""
        summary = self.get_rotation_summary()
        return summary["direction"] == "Risk-On"
    
    def is_risk_off(self) -> bool:
        """Check if market is in risk-off mode."""
        summary = self.get_rotation_summary()
        return summary["direction"] == "Risk-Off"
