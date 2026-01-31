"""Economic Calendar Data Models.

Dataclasses for economic events, releases, and Fed meetings.
"""

from dataclasses import dataclass, field
from datetime import datetime, date, time, timezone
from typing import Optional
import uuid

from src.economic.config import (
    ImpactLevel,
    EventCategory,
    Country,
    RateDecision,
    AlertTrigger,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


# =============================================================================
# Economic Events
# =============================================================================

@dataclass
class EconomicEvent:
    """An economic calendar event."""
    event_id: str = field(default_factory=_new_id)
    name: str = ""
    country: Country = Country.US
    category: EventCategory = EventCategory.OTHER
    
    # Timing
    release_date: Optional[date] = None
    release_time: Optional[time] = None
    timezone_str: str = "America/New_York"
    
    # Importance
    impact: ImpactLevel = ImpactLevel.MEDIUM
    
    # Data
    previous: Optional[float] = None
    forecast: Optional[float] = None
    actual: Optional[float] = None
    unit: str = ""  # %, K, M, B, index
    
    # Status
    is_released: bool = False
    release_timestamp: Optional[datetime] = None
    
    # Metadata
    description: str = ""
    source: str = ""
    
    @property
    def surprise(self) -> Optional[float]:
        """Calculate surprise (actual - forecast)."""
        if self.actual is not None and self.forecast is not None:
            return self.actual - self.forecast
        return None
    
    @property
    def surprise_pct(self) -> Optional[float]:
        """Calculate surprise as percentage."""
        if self.actual is not None and self.forecast is not None and self.forecast != 0:
            return ((self.actual - self.forecast) / abs(self.forecast)) * 100
        return None
    
    @property
    def beat_or_miss(self) -> Optional[str]:
        """Determine if event beat or missed expectations."""
        surprise = self.surprise
        if surprise is None:
            return None
        if surprise > 0:
            return "beat"
        elif surprise < 0:
            return "miss"
        return "inline"


@dataclass
class HistoricalRelease:
    """Historical economic release with market reaction."""
    release_id: str = field(default_factory=_new_id)
    event_name: str = ""
    release_date: Optional[datetime] = None
    
    # Values
    actual: float = 0.0
    forecast: float = 0.0
    previous: float = 0.0
    
    # Surprise
    surprise: float = 0.0
    surprise_pct: float = 0.0
    surprise_std: float = 0.0  # Standard deviations from forecast
    
    # Market reaction (1 hour after release)
    spx_1h_change: float = 0.0
    spx_1d_change: float = 0.0
    dxy_1h_change: float = 0.0  # Dollar index
    vix_change: float = 0.0
    tnx_change: float = 0.0  # 10-year yield change (bps)
    
    # Volume
    volume_ratio: float = 1.0  # vs average


@dataclass
class EventStats:
    """Statistics for an economic event."""
    event_name: str = ""
    
    # Release stats
    total_releases: int = 0
    beat_count: int = 0
    miss_count: int = 0
    inline_count: int = 0
    
    # Surprise stats
    avg_surprise: float = 0.0
    avg_surprise_pct: float = 0.0
    surprise_std: float = 0.0
    
    # Market reaction stats
    avg_spx_reaction: float = 0.0
    avg_vix_change: float = 0.0
    max_spx_move: float = 0.0
    
    @property
    def beat_rate(self) -> float:
        """Calculate beat rate."""
        if self.total_releases == 0:
            return 0.0
        return (self.beat_count / self.total_releases) * 100


# =============================================================================
# Fed Models
# =============================================================================

@dataclass
class FedMeeting:
    """Federal Reserve meeting."""
    meeting_id: str = field(default_factory=_new_id)
    meeting_date: Optional[date] = None
    meeting_type: str = "FOMC"  # FOMC, Minutes, Speech, Testimony
    
    # Rate decision
    rate_before: Optional[float] = None
    rate_after: Optional[float] = None
    rate_decision: Optional[RateDecision] = None
    rate_change: float = 0.0
    
    # Market expectations (pre-meeting)
    prob_hike: float = 0.0
    prob_cut: float = 0.0
    prob_hold: float = 100.0
    
    # Statement
    statement_tone: Optional[str] = None  # hawkish, dovish, neutral
    key_changes: list[str] = field(default_factory=list)
    
    # Projections (SEP meetings)
    has_projections: bool = False
    median_2024: Optional[float] = None
    median_2025: Optional[float] = None
    median_long_run: Optional[float] = None
    
    @property
    def was_surprise(self) -> bool:
        """Check if decision was a surprise."""
        if self.rate_decision == RateDecision.HIKE and self.prob_hike < 50:
            return True
        if self.rate_decision == RateDecision.CUT and self.prob_cut < 50:
            return True
        if self.rate_decision == RateDecision.HOLD and self.prob_hold < 50:
            return True
        return False


@dataclass
class RateExpectation:
    """Market expectation for a future Fed meeting."""
    target_date: Optional[date] = None
    
    # Probabilities
    prob_hike_25: float = 0.0
    prob_hike_50: float = 0.0
    prob_hold: float = 0.0
    prob_cut_25: float = 0.0
    prob_cut_50: float = 0.0
    
    # Implied rate
    implied_rate: float = 0.0
    current_rate: float = 0.0
    
    @property
    def expected_change(self) -> float:
        """Calculate expected rate change."""
        return self.implied_rate - self.current_rate


# =============================================================================
# Alerts
# =============================================================================

@dataclass
class EventAlert:
    """Alert configuration for economic events."""
    alert_id: str = field(default_factory=_new_id)
    name: str = ""
    
    # Event filter
    event_pattern: str = ""  # Event name pattern (supports wildcards)
    categories: list[EventCategory] = field(default_factory=list)
    countries: list[Country] = field(default_factory=list)
    min_impact: ImpactLevel = ImpactLevel.MEDIUM
    
    # Triggers
    trigger_type: AlertTrigger = AlertTrigger.UPCOMING
    minutes_before: int = 30
    on_release: bool = True
    surprise_threshold: Optional[float] = None  # Std devs
    
    # Status
    is_active: bool = True
    created_at: datetime = field(default_factory=_utc_now)


@dataclass
class AlertNotification:
    """Generated alert notification."""
    notification_id: str = field(default_factory=_new_id)
    alert_id: str = ""
    event_id: str = ""
    
    # Content
    title: str = ""
    message: str = ""
    event_name: str = ""
    
    # Timing
    created_at: datetime = field(default_factory=_utc_now)
    
    # Status
    is_read: bool = False


# =============================================================================
# Market Impact
# =============================================================================

@dataclass
class MarketImpact:
    """Market impact analysis for an event."""
    event_id: str = ""
    event_name: str = ""
    
    # Pre-event
    expected_volatility: float = 0.0
    historical_avg_move: float = 0.0
    
    # Post-event (if released)
    actual_spx_change: Optional[float] = None
    actual_vix_change: Optional[float] = None
    actual_dxy_change: Optional[float] = None
    
    # Analysis
    reaction_vs_history: Optional[str] = None  # muted, normal, amplified
    sector_impacts: dict[str, float] = field(default_factory=dict)
    
    # Trading implications
    pre_event_notes: list[str] = field(default_factory=list)
    post_event_notes: list[str] = field(default_factory=list)
