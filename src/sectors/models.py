"""Sector Rotation Data Models.

Dataclasses for sectors, rotation signals, and business cycles.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Optional
import uuid

from src.sectors.config import (
    SectorName,
    CyclePhase,
    Trend,
    SignalStrength,
    Recommendation,
    Conviction,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# =============================================================================
# Sector Models
# =============================================================================

@dataclass
class Sector:
    """A market sector with performance metrics."""
    sector_id: str = field(default_factory=_new_id)
    name: SectorName = SectorName.TECHNOLOGY
    
    # ETF tracking
    etf_symbol: str = ""
    
    # Current price data
    price: float = 0.0
    change_1d: float = 0.0
    change_1w: float = 0.0
    change_1m: float = 0.0
    change_3m: float = 0.0
    change_6m: float = 0.0
    change_ytd: float = 0.0
    change_1y: float = 0.0
    
    # Relative strength vs benchmark
    rs_ratio: float = 1.0
    rs_change: float = 0.0
    rs_rank: int = 0
    
    # Momentum
    momentum_score: float = 0.0
    trend: Trend = Trend.NEUTRAL
    
    # Volume
    volume: int = 0
    avg_volume: int = 0
    relative_volume: float = 1.0
    
    # Breadth
    pct_above_50ma: float = 0.0
    pct_above_200ma: float = 0.0
    
    # Updated
    updated_at: datetime = field(default_factory=_utc_now)
    
    @property
    def is_outperforming(self) -> bool:
        """Check if sector is outperforming benchmark."""
        return self.rs_ratio > 1.0
    
    @property
    def is_trending_up(self) -> bool:
        """Check if sector is in uptrend."""
        return self.trend == Trend.UP


@dataclass
class SectorPerformance:
    """Sector performance analysis."""
    sector: SectorName = SectorName.TECHNOLOGY
    period: str = "1m"  # 1d, 1w, 1m, 3m, 6m, 1y
    
    # Returns
    absolute_return: float = 0.0
    relative_return: float = 0.0  # vs benchmark
    benchmark_return: float = 0.0
    
    # Risk metrics
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    
    # Comparison
    rank: int = 0
    percentile: float = 0.0
    
    # Dates
    start_date: Optional[date] = None
    end_date: Optional[date] = None


# =============================================================================
# Rotation Models
# =============================================================================

@dataclass
class RotationSignal:
    """A sector rotation signal."""
    signal_id: str = field(default_factory=_new_id)
    signal_date: Optional[date] = None
    
    # Flow direction
    from_sector: SectorName = SectorName.TECHNOLOGY
    to_sector: SectorName = SectorName.HEALTHCARE
    
    # Signal details
    signal_type: str = "rs_breakout"  # rs_breakout, momentum_shift, breadth_divergence
    signal_strength: SignalStrength = SignalStrength.MODERATE
    confidence: float = 0.0
    
    # Evidence
    rs_change: float = 0.0
    volume_confirmation: bool = False
    breadth_confirmation: bool = False
    
    # Description
    description: str = ""
    
    # Metadata
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class RotationPattern:
    """A named rotation pattern."""
    pattern_id: str = field(default_factory=_new_id)
    name: str = ""  # risk_on, risk_off, inflation_trade, etc.
    
    # Pattern details
    from_sectors: list[SectorName] = field(default_factory=list)
    to_sectors: list[SectorName] = field(default_factory=list)
    
    # Characteristics
    description: str = ""
    typical_duration: str = ""  # weeks, months
    
    # Detection
    is_active: bool = False
    confidence: float = 0.0
    start_date: Optional[date] = None


# =============================================================================
# Business Cycle Models
# =============================================================================

@dataclass
class BusinessCycle:
    """Business cycle analysis."""
    cycle_id: str = field(default_factory=_new_id)
    
    # Current phase
    current_phase: CyclePhase = CyclePhase.MID_EXPANSION
    phase_confidence: float = 0.0
    phase_duration_months: int = 0
    
    # Economic indicators
    gdp_trend: Trend = Trend.NEUTRAL
    employment_trend: Trend = Trend.NEUTRAL
    inflation_trend: Trend = Trend.NEUTRAL
    yield_curve_trend: Trend = Trend.NEUTRAL
    
    # Leading indicators
    leading_indicator_score: float = 0.0
    
    # Sector implications
    overweight_sectors: list[SectorName] = field(default_factory=list)
    underweight_sectors: list[SectorName] = field(default_factory=list)
    
    # Analysis date
    analysis_date: Optional[date] = None
    updated_at: datetime = field(default_factory=_utc_now)


@dataclass
class CycleTransition:
    """A business cycle phase transition."""
    transition_id: str = field(default_factory=_new_id)
    
    from_phase: CyclePhase = CyclePhase.MID_EXPANSION
    to_phase: CyclePhase = CyclePhase.LATE_EXPANSION
    
    transition_date: Optional[date] = None
    confidence: float = 0.0
    
    # Implications
    sector_changes: dict = field(default_factory=dict)


# =============================================================================
# Recommendation Models
# =============================================================================

@dataclass
class SectorRecommendation:
    """Sector ETF recommendation."""
    recommendation_id: str = field(default_factory=_new_id)
    sector: SectorName = SectorName.TECHNOLOGY
    etf_symbol: str = ""
    
    # Rating
    recommendation: Recommendation = Recommendation.NEUTRAL
    conviction: Conviction = Conviction.MEDIUM
    
    # Scores
    momentum_score: float = 0.0
    relative_strength_score: float = 0.0
    cycle_alignment_score: float = 0.0
    overall_score: float = 0.0
    
    # Weights
    target_weight: float = 0.0
    benchmark_weight: float = 0.0
    active_weight: float = 0.0  # target - benchmark
    
    # Rationale
    rationale: list[str] = field(default_factory=list)
    
    # Metadata
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class SectorAllocation:
    """Portfolio sector allocation."""
    allocation_id: str = field(default_factory=_new_id)
    name: str = "Tactical Allocation"
    
    # Allocations
    allocations: dict[SectorName, float] = field(default_factory=dict)
    
    # Comparison to benchmark
    benchmark_allocations: dict[SectorName, float] = field(default_factory=dict)
    
    # Summary
    total_overweight: float = 0.0
    total_underweight: float = 0.0
    active_share: float = 0.0
    
    # Metadata
    created_at: datetime = field(default_factory=_utc_now)
