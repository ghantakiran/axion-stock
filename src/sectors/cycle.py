"""Business Cycle Analysis.

Map sectors to business cycle phases.
"""

from datetime import datetime, date, timedelta, timezone
from typing import Optional
import logging

from src.sectors.config import (
    SectorName,
    CyclePhase,
    Trend,
    CYCLE_SECTOR_PREFERENCES,
    CycleConfig,
    DEFAULT_CYCLE_CONFIG,
)
from src.sectors.models import BusinessCycle, CycleTransition

logger = logging.getLogger(__name__)


# Cycle phase characteristics
PHASE_CHARACTERISTICS = {
    CyclePhase.EARLY_EXPANSION: {
        "gdp": Trend.UP,
        "employment": Trend.UP,
        "inflation": Trend.NEUTRAL,
        "yield_curve": Trend.UP,
        "description": "Recovery from recession, accommodative policy",
    },
    CyclePhase.MID_EXPANSION: {
        "gdp": Trend.UP,
        "employment": Trend.UP,
        "inflation": Trend.UP,
        "yield_curve": Trend.NEUTRAL,
        "description": "Sustained growth, moderate inflation",
    },
    CyclePhase.LATE_EXPANSION: {
        "gdp": Trend.NEUTRAL,
        "employment": Trend.UP,
        "inflation": Trend.UP,
        "yield_curve": Trend.DOWN,
        "description": "Peak growth, rising rates, yield curve flattening",
    },
    CyclePhase.EARLY_CONTRACTION: {
        "gdp": Trend.DOWN,
        "employment": Trend.DOWN,
        "inflation": Trend.NEUTRAL,
        "yield_curve": Trend.DOWN,
        "description": "Slowdown begins, defensive positioning",
    },
    CyclePhase.LATE_CONTRACTION: {
        "gdp": Trend.DOWN,
        "employment": Trend.DOWN,
        "inflation": Trend.DOWN,
        "yield_curve": Trend.UP,
        "description": "Recession, policy easing, preparing for recovery",
    },
}


class CycleAnalyzer:
    """Analyzes business cycle and sector implications.
    
    Example:
        analyzer = CycleAnalyzer()
        
        # Set economic indicators
        analyzer.set_indicators(
            gdp_trend=Trend.UP,
            employment_trend=Trend.UP,
            inflation_trend=Trend.NEUTRAL,
        )
        
        cycle = analyzer.analyze()
        print(f"Phase: {cycle.current_phase.value}")
    """
    
    def __init__(self, config: Optional[CycleConfig] = None):
        self.config = config or DEFAULT_CYCLE_CONFIG
        self._current_cycle: Optional[BusinessCycle] = None
        self._transitions: list[CycleTransition] = []
        
        # Economic indicators
        self._gdp_trend: Trend = Trend.NEUTRAL
        self._employment_trend: Trend = Trend.NEUTRAL
        self._inflation_trend: Trend = Trend.NEUTRAL
        self._yield_curve_trend: Trend = Trend.NEUTRAL
        self._leading_indicators: float = 0.0
    
    def set_indicators(
        self,
        gdp_trend: Optional[Trend] = None,
        employment_trend: Optional[Trend] = None,
        inflation_trend: Optional[Trend] = None,
        yield_curve_trend: Optional[Trend] = None,
        leading_indicators: Optional[float] = None,
    ) -> None:
        """Set economic indicators."""
        if gdp_trend is not None:
            self._gdp_trend = gdp_trend
        if employment_trend is not None:
            self._employment_trend = employment_trend
        if inflation_trend is not None:
            self._inflation_trend = inflation_trend
        if yield_curve_trend is not None:
            self._yield_curve_trend = yield_curve_trend
        if leading_indicators is not None:
            self._leading_indicators = leading_indicators
    
    def analyze(self) -> BusinessCycle:
        """Analyze current business cycle phase.
        
        Returns:
            BusinessCycle with current phase and sector implications.
        """
        # Determine phase based on indicators
        phase, confidence = self._determine_phase()
        
        # Get sector preferences for this phase
        preferences = CYCLE_SECTOR_PREFERENCES.get(phase, {})
        overweight = preferences.get("overweight", [])
        underweight = preferences.get("underweight", [])
        
        cycle = BusinessCycle(
            current_phase=phase,
            phase_confidence=confidence,
            gdp_trend=self._gdp_trend,
            employment_trend=self._employment_trend,
            inflation_trend=self._inflation_trend,
            yield_curve_trend=self._yield_curve_trend,
            leading_indicator_score=self._leading_indicators,
            overweight_sectors=overweight,
            underweight_sectors=underweight,
            analysis_date=date.today(),
        )
        
        # Check for transition
        if self._current_cycle and self._current_cycle.current_phase != phase:
            transition = CycleTransition(
                from_phase=self._current_cycle.current_phase,
                to_phase=phase,
                transition_date=date.today(),
                confidence=confidence,
            )
            self._transitions.append(transition)
        
        self._current_cycle = cycle
        return cycle
    
    def _determine_phase(self) -> tuple[CyclePhase, float]:
        """Determine cycle phase from indicators."""
        best_phase = CyclePhase.MID_EXPANSION
        best_score = 0
        
        for phase, chars in PHASE_CHARACTERISTICS.items():
            score = 0
            total = 0
            
            # Match GDP
            if chars["gdp"] == self._gdp_trend:
                score += 1
            total += 1
            
            # Match employment
            if chars["employment"] == self._employment_trend:
                score += 1
            total += 1
            
            # Match inflation
            if chars["inflation"] == self._inflation_trend:
                score += 1
            total += 1
            
            # Match yield curve
            if self.config.use_yield_curve:
                if chars["yield_curve"] == self._yield_curve_trend:
                    score += 1
                total += 1
            
            match_pct = score / total if total > 0 else 0
            
            if match_pct > best_score:
                best_score = match_pct
                best_phase = phase
        
        confidence = best_score * 100
        return best_phase, confidence
    
    def get_current_cycle(self) -> Optional[BusinessCycle]:
        """Get current cycle analysis."""
        return self._current_cycle
    
    def get_phase_description(self, phase: Optional[CyclePhase] = None) -> str:
        """Get description of a cycle phase."""
        if phase is None and self._current_cycle:
            phase = self._current_cycle.current_phase
        
        if phase:
            return PHASE_CHARACTERISTICS.get(phase, {}).get("description", "")
        return ""
    
    def get_favored_sectors(self) -> list[SectorName]:
        """Get favored sectors for current phase."""
        if self._current_cycle:
            return self._current_cycle.overweight_sectors
        return []
    
    def get_unfavored_sectors(self) -> list[SectorName]:
        """Get unfavored sectors for current phase."""
        if self._current_cycle:
            return self._current_cycle.underweight_sectors
        return []
    
    def get_transitions(self, limit: int = 5) -> list[CycleTransition]:
        """Get recent cycle transitions."""
        return self._transitions[-limit:]
    
    def predict_next_phase(self) -> tuple[CyclePhase, float]:
        """Predict the next cycle phase.
        
        Returns:
            (next_phase, probability)
        """
        if not self._current_cycle:
            return CyclePhase.MID_EXPANSION, 0.5
        
        current = self._current_cycle.current_phase
        
        # Simple phase progression
        next_phases = {
            CyclePhase.EARLY_EXPANSION: (CyclePhase.MID_EXPANSION, 0.7),
            CyclePhase.MID_EXPANSION: (CyclePhase.LATE_EXPANSION, 0.6),
            CyclePhase.LATE_EXPANSION: (CyclePhase.EARLY_CONTRACTION, 0.5),
            CyclePhase.EARLY_CONTRACTION: (CyclePhase.LATE_CONTRACTION, 0.6),
            CyclePhase.LATE_CONTRACTION: (CyclePhase.EARLY_EXPANSION, 0.7),
        }
        
        return next_phases.get(current, (CyclePhase.MID_EXPANSION, 0.5))
    
    def get_sector_cycle_alignment(self, sector: SectorName) -> dict:
        """Get how well a sector aligns with current cycle."""
        if not self._current_cycle:
            return {"alignment": "neutral", "score": 0.5}
        
        overweight = self._current_cycle.overweight_sectors
        underweight = self._current_cycle.underweight_sectors
        
        if sector in overweight:
            return {"alignment": "favorable", "score": 0.8}
        elif sector in underweight:
            return {"alignment": "unfavorable", "score": 0.2}
        else:
            return {"alignment": "neutral", "score": 0.5}


def generate_sample_cycle() -> CycleAnalyzer:
    """Generate sample cycle analysis."""
    analyzer = CycleAnalyzer()
    
    # Set current indicators (mid-expansion scenario)
    analyzer.set_indicators(
        gdp_trend=Trend.UP,
        employment_trend=Trend.UP,
        inflation_trend=Trend.UP,
        yield_curve_trend=Trend.NEUTRAL,
        leading_indicators=0.6,
    )
    
    analyzer.analyze()
    return analyzer
