"""Earnings Calendar Configuration.

Enums, constants, and configuration for earnings tracking.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =============================================================================
# Enums
# =============================================================================

class EarningsTime(str, Enum):
    """When earnings are reported."""
    BEFORE_MARKET = "bmo"  # Before market open
    AFTER_MARKET = "amc"   # After market close
    DURING_MARKET = "dmh"  # During market hours
    UNKNOWN = "unknown"


class SurpriseType(str, Enum):
    """Type of earnings surprise."""
    BEAT = "beat"
    MEET = "meet"
    MISS = "miss"


class ReactionDirection(str, Enum):
    """Price reaction direction."""
    GAP_UP = "gap_up"
    GAP_DOWN = "gap_down"
    FLAT = "flat"


class AlertType(str, Enum):
    """Earnings alert type."""
    UPCOMING = "upcoming"
    REVISION = "revision"
    RELEASED = "released"
    SURPRISE = "surprise"
    GUIDANCE = "guidance"


class QualityRating(str, Enum):
    """Earnings quality rating."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    WARNING = "warning"


class CalendarView(str, Enum):
    """Calendar view type."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    PORTFOLIO = "portfolio"
    WATCHLIST = "watchlist"


# =============================================================================
# Constants
# =============================================================================

# Surprise thresholds
BEAT_THRESHOLD = 0.01  # 1% beat threshold
MISS_THRESHOLD = -0.01  # 1% miss threshold

# Quality thresholds
BENEISH_THRESHOLD = -2.22  # M-Score above this suggests manipulation
ACCRUALS_WARNING = 0.10  # High accruals warning

# Reaction thresholds
SIGNIFICANT_GAP = 0.03  # 3% gap is significant
HIGH_VOLUME_RATIO = 2.0  # 2x average volume

# Default days before earnings for alerts
DEFAULT_ALERT_DAYS = [7, 3, 1]

# Fiscal quarters
FISCAL_QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

# Common earnings seasons (approximate)
EARNINGS_SEASONS = {
    "Q1": (4, 5),   # April-May
    "Q2": (7, 8),   # July-August
    "Q3": (10, 11), # October-November
    "Q4": (1, 2),   # January-February
}


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class EarningsConfig:
    """Configuration for earnings tracking."""
    # Alert settings
    alert_days_before: list[int] = field(default_factory=lambda: [7, 3, 1])
    surprise_alert_threshold: float = 0.05  # 5% surprise
    
    # Historical data
    history_years: int = 5
    
    # Quality settings
    beneish_threshold: float = BENEISH_THRESHOLD
    
    # Reaction analysis
    pre_earnings_days: int = 5
    post_earnings_days: int = 20


@dataclass
class CalendarConfig:
    """Configuration for calendar display."""
    default_view: CalendarView = CalendarView.WEEKLY
    show_estimates: bool = True
    show_history: bool = True
    highlight_portfolio: bool = True


DEFAULT_EARNINGS_CONFIG = EarningsConfig()
DEFAULT_CALENDAR_CONFIG = CalendarConfig()
