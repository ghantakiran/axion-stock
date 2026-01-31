"""Earnings Data Models.

Dataclasses for earnings events, estimates, history, and analysis.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Optional
import uuid

from src.earnings.config import (
    EarningsTime,
    SurpriseType,
    ReactionDirection,
    AlertType,
    QualityRating,
    BEAT_THRESHOLD,
    MISS_THRESHOLD,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# =============================================================================
# Core Earnings Models
# =============================================================================

@dataclass
class EarningsEvent:
    """An earnings announcement event."""
    event_id: str = field(default_factory=_new_id)
    symbol: str = ""
    company_name: str = ""
    
    # Timing
    report_date: Optional[date] = None
    report_time: EarningsTime = EarningsTime.UNKNOWN
    fiscal_quarter: str = ""  # "Q1 2024"
    fiscal_year: int = 0
    
    # Estimates
    eps_estimate: Optional[float] = None
    revenue_estimate: Optional[float] = None
    num_estimates: int = 0
    
    # Actuals (filled after report)
    eps_actual: Optional[float] = None
    revenue_actual: Optional[float] = None
    
    # Conference call
    conference_call_time: Optional[datetime] = None
    conference_call_url: Optional[str] = None
    
    # Status
    is_confirmed: bool = False
    is_reported: bool = False
    last_updated: datetime = field(default_factory=_utc_now)
    
    @property
    def eps_surprise(self) -> Optional[float]:
        """Calculate EPS surprise."""
        if self.eps_actual is not None and self.eps_estimate:
            return self.eps_actual - self.eps_estimate
        return None
    
    @property
    def eps_surprise_pct(self) -> Optional[float]:
        """Calculate EPS surprise percentage."""
        if self.eps_actual is not None and self.eps_estimate and self.eps_estimate != 0:
            return (self.eps_actual - self.eps_estimate) / abs(self.eps_estimate)
        return None
    
    @property
    def revenue_surprise(self) -> Optional[float]:
        """Calculate revenue surprise."""
        if self.revenue_actual is not None and self.revenue_estimate:
            return self.revenue_actual - self.revenue_estimate
        return None
    
    @property
    def surprise_type(self) -> Optional[SurpriseType]:
        """Determine if beat, meet, or miss."""
        pct = self.eps_surprise_pct
        if pct is None:
            return None
        if pct > BEAT_THRESHOLD:
            return SurpriseType.BEAT
        elif pct < MISS_THRESHOLD:
            return SurpriseType.MISS
        return SurpriseType.MEET


@dataclass
class EarningsEstimate:
    """Analyst estimates for earnings."""
    estimate_id: str = field(default_factory=_new_id)
    symbol: str = ""
    fiscal_quarter: str = ""
    
    # EPS Estimates
    eps_consensus: float = 0.0
    eps_high: float = 0.0
    eps_low: float = 0.0
    eps_num_analysts: int = 0
    
    # Revenue Estimates (in millions)
    revenue_consensus: float = 0.0
    revenue_high: float = 0.0
    revenue_low: float = 0.0
    revenue_num_analysts: int = 0
    
    # Revisions (last 30 days)
    eps_revisions_up: int = 0
    eps_revisions_down: int = 0
    revenue_revisions_up: int = 0
    revenue_revisions_down: int = 0
    
    # Historical comparison
    eps_year_ago: Optional[float] = None
    revenue_year_ago: Optional[float] = None
    
    # Timestamp
    as_of_date: date = field(default_factory=date.today)
    
    @property
    def eps_spread(self) -> float:
        """Spread between high and low estimates."""
        return self.eps_high - self.eps_low
    
    @property
    def eps_yoy_growth(self) -> Optional[float]:
        """Year-over-year EPS growth expected."""
        if self.eps_year_ago and self.eps_year_ago != 0:
            return (self.eps_consensus - self.eps_year_ago) / abs(self.eps_year_ago)
        return None
    
    @property
    def revision_trend(self) -> str:
        """Overall revision trend."""
        net = (self.eps_revisions_up - self.eps_revisions_down)
        if net > 0:
            return "positive"
        elif net < 0:
            return "negative"
        return "neutral"


@dataclass
class QuarterlyEarnings:
    """Historical earnings for a quarter."""
    quarter_id: str = field(default_factory=_new_id)
    symbol: str = ""
    fiscal_quarter: str = ""
    report_date: Optional[date] = None
    
    # EPS
    eps_estimate: float = 0.0
    eps_actual: float = 0.0
    
    # Revenue (in millions)
    revenue_estimate: float = 0.0
    revenue_actual: float = 0.0
    
    # Price reaction
    price_before: float = 0.0
    price_after: float = 0.0
    price_change_1d: float = 0.0
    price_change_5d: float = 0.0
    
    # Guidance
    guidance_eps_low: Optional[float] = None
    guidance_eps_high: Optional[float] = None
    guidance_revenue_low: Optional[float] = None
    guidance_revenue_high: Optional[float] = None
    
    @property
    def eps_surprise(self) -> float:
        return self.eps_actual - self.eps_estimate
    
    @property
    def eps_surprise_pct(self) -> float:
        if self.eps_estimate != 0:
            return (self.eps_actual - self.eps_estimate) / abs(self.eps_estimate)
        return 0.0
    
    @property
    def revenue_surprise(self) -> float:
        return self.revenue_actual - self.revenue_estimate
    
    @property
    def revenue_surprise_pct(self) -> float:
        if self.revenue_estimate != 0:
            return (self.revenue_actual - self.revenue_estimate) / abs(self.revenue_estimate)
        return 0.0
    
    @property
    def surprise_type(self) -> SurpriseType:
        pct = self.eps_surprise_pct
        if pct > BEAT_THRESHOLD:
            return SurpriseType.BEAT
        elif pct < MISS_THRESHOLD:
            return SurpriseType.MISS
        return SurpriseType.MEET


@dataclass
class EarningsHistory:
    """Historical earnings summary for a stock."""
    symbol: str = ""
    company_name: str = ""
    quarters: list[QuarterlyEarnings] = field(default_factory=list)
    
    # Summary stats
    beat_rate_eps: float = 0.0
    beat_rate_revenue: float = 0.0
    avg_surprise_eps: float = 0.0
    avg_surprise_revenue: float = 0.0
    
    # Consistency
    consecutive_beats: int = 0
    consecutive_misses: int = 0
    
    # Reaction stats
    avg_reaction_beat: float = 0.0
    avg_reaction_miss: float = 0.0


# =============================================================================
# Quality Models
# =============================================================================

@dataclass
class EarningsQuality:
    """Earnings quality assessment."""
    quality_id: str = field(default_factory=_new_id)
    symbol: str = ""
    as_of_date: date = field(default_factory=date.today)
    
    # Core metrics
    accruals_ratio: float = 0.0
    cash_conversion: float = 0.0
    earnings_persistence: float = 0.0
    
    # Quality scores (0-100)
    revenue_quality_score: float = 0.0
    earnings_quality_score: float = 0.0
    overall_quality_score: float = 0.0
    
    # Beneish M-Score components
    dsri: float = 0.0  # Days Sales Receivable Index
    gmi: float = 0.0   # Gross Margin Index
    aqi: float = 0.0   # Asset Quality Index
    sgi: float = 0.0   # Sales Growth Index
    depi: float = 0.0  # Depreciation Index
    sgai: float = 0.0  # SGA Expense Index
    lvgi: float = 0.0  # Leverage Index
    tata: float = 0.0  # Total Accruals to Total Assets
    
    # M-Score result
    beneish_m_score: float = 0.0
    is_manipulation_risk: bool = False
    
    # Rating
    quality_rating: QualityRating = QualityRating.MEDIUM
    
    # Red flags
    red_flags: list[str] = field(default_factory=list)


# =============================================================================
# Reaction Models
# =============================================================================

@dataclass
class EarningsReaction:
    """Price reaction to earnings."""
    reaction_id: str = field(default_factory=_new_id)
    symbol: str = ""
    fiscal_quarter: str = ""
    report_date: Optional[date] = None
    
    # Pre-earnings
    price_5d_before: float = 0.0
    price_1d_before: float = 0.0
    volume_avg_before: float = 0.0
    iv_percentile_before: float = 0.0
    
    # Earnings day
    gap_open_pct: float = 0.0
    close_change_pct: float = 0.0
    high_low_range_pct: float = 0.0
    volume_ratio: float = 0.0  # vs average
    
    # Extended reaction
    price_change_1d: float = 0.0
    price_change_5d: float = 0.0
    price_change_20d: float = 0.0
    
    # Drift analysis
    pre_earnings_drift: float = 0.0
    post_earnings_drift: float = 0.0
    
    @property
    def reaction_direction(self) -> ReactionDirection:
        """Determine reaction direction."""
        if self.gap_open_pct > 0.01:
            return ReactionDirection.GAP_UP
        elif self.gap_open_pct < -0.01:
            return ReactionDirection.GAP_DOWN
        return ReactionDirection.FLAT


# =============================================================================
# Alert Models
# =============================================================================

@dataclass
class EarningsAlert:
    """An earnings-related alert."""
    alert_id: str = field(default_factory=_new_id)
    symbol: str = ""
    alert_type: AlertType = AlertType.UPCOMING
    
    # Content
    title: str = ""
    message: str = ""
    
    # Related data
    earnings_event: Optional[EarningsEvent] = None
    
    # Timing
    created_at: datetime = field(default_factory=_utc_now)
    triggered_at: Optional[datetime] = None
    
    # Status
    is_read: bool = False
    is_dismissed: bool = False
