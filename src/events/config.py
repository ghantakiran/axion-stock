"""Event-Driven Analytics Configuration."""

from dataclasses import dataclass, field
from enum import Enum


class EventType(Enum):
    """Type of corporate event."""
    EARNINGS = "earnings"
    MERGER = "merger"
    DIVIDEND = "dividend"
    SPLIT = "split"
    SPINOFF = "spinoff"
    BUYBACK = "buyback"


class EarningsResult(Enum):
    """Earnings report result."""
    BEAT = "beat"
    MEET = "meet"
    MISS = "miss"


class DealStatus(Enum):
    """M&A deal status."""
    ANNOUNCED = "announced"
    PENDING = "pending"
    APPROVED = "approved"
    CLOSED = "closed"
    TERMINATED = "terminated"


class SignalStrength(Enum):
    """Event signal strength."""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    NONE = "none"


@dataclass
class EarningsConfig:
    """Earnings analysis config."""
    beat_threshold: float = 0.02  # 2% surprise to count as beat
    miss_threshold: float = -0.02
    drift_window: int = 20  # trading days for PEAD
    pre_drift_window: int = 5  # days before earnings
    min_history: int = 4  # quarters for pattern analysis


@dataclass
class MergerConfig:
    """Merger analysis config."""
    min_probability: float = 0.5
    high_probability: float = 0.85
    spread_annualization_days: int = 252
    regulatory_risk_factor: float = 0.15


@dataclass
class CorporateConfig:
    """Corporate action config."""
    upcoming_window_days: int = 30
    min_dividend_yield: float = 0.01
    significant_buyback_pct: float = 0.02


@dataclass
class SignalConfig:
    """Signal generation config."""
    strong_threshold: float = 0.7
    moderate_threshold: float = 0.4
    weak_threshold: float = 0.2
    earnings_weight: float = 0.40
    merger_weight: float = 0.35
    corporate_weight: float = 0.25


@dataclass
class EventConfig:
    """Top-level event config."""
    earnings: EarningsConfig = field(default_factory=EarningsConfig)
    merger: MergerConfig = field(default_factory=MergerConfig)
    corporate: CorporateConfig = field(default_factory=CorporateConfig)
    signal: SignalConfig = field(default_factory=SignalConfig)


DEFAULT_EVENT_CONFIG = EventConfig()
