"""Economic Calendar Configuration.

Enums, constants, and configuration for economic events.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =============================================================================
# Enums
# =============================================================================

class ImpactLevel(str, Enum):
    """Event impact level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EventCategory(str, Enum):
    """Economic event categories."""
    EMPLOYMENT = "employment"
    INFLATION = "inflation"
    GDP = "gdp"
    CENTRAL_BANK = "central_bank"
    MANUFACTURING = "manufacturing"
    CONSUMER = "consumer"
    HOUSING = "housing"
    TRADE = "trade"
    TREASURY = "treasury"
    OTHER = "other"


class Country(str, Enum):
    """Country codes."""
    US = "US"
    EU = "EU"
    UK = "UK"
    JP = "JP"
    CN = "CN"
    CA = "CA"
    AU = "AU"
    CH = "CH"
    GLOBAL = "GLOBAL"


class RateDecision(str, Enum):
    """Central bank rate decision."""
    HIKE = "hike"
    CUT = "cut"
    HOLD = "hold"


class AlertTrigger(str, Enum):
    """Alert trigger types."""
    UPCOMING = "upcoming"
    RELEASED = "released"
    SURPRISE = "surprise"
    CUSTOM = "custom"


# =============================================================================
# Constants
# =============================================================================

# High-impact US events
HIGH_IMPACT_EVENTS = [
    "Non-Farm Payrolls",
    "CPI",
    "Core CPI",
    "Fed Interest Rate Decision",
    "FOMC Statement",
    "GDP",
    "PCE Price Index",
    "Core PCE",
    "Retail Sales",
    "ISM Manufacturing PMI",
    "ISM Services PMI",
    "Unemployment Rate",
    "Initial Jobless Claims",
    "Consumer Confidence",
    "Michigan Consumer Sentiment",
]

# Category descriptions
CATEGORY_INFO = {
    EventCategory.EMPLOYMENT: {
        "name": "Employment",
        "description": "Jobs data including payrolls, unemployment, claims",
        "key_events": ["Non-Farm Payrolls", "Unemployment Rate", "Jobless Claims"],
    },
    EventCategory.INFLATION: {
        "name": "Inflation",
        "description": "Price indices including CPI, PPI, PCE",
        "key_events": ["CPI", "Core CPI", "PPI", "PCE Price Index"],
    },
    EventCategory.GDP: {
        "name": "GDP & Growth",
        "description": "Economic growth indicators",
        "key_events": ["GDP", "GDP Price Index"],
    },
    EventCategory.CENTRAL_BANK: {
        "name": "Central Bank",
        "description": "Fed, ECB, BOJ policy decisions",
        "key_events": ["Fed Rate Decision", "FOMC Minutes", "ECB Rate Decision"],
    },
    EventCategory.MANUFACTURING: {
        "name": "Manufacturing",
        "description": "Industrial production and PMI data",
        "key_events": ["ISM Manufacturing", "Industrial Production", "PMI"],
    },
    EventCategory.CONSUMER: {
        "name": "Consumer",
        "description": "Consumer spending and sentiment",
        "key_events": ["Retail Sales", "Consumer Confidence", "Michigan Sentiment"],
    },
    EventCategory.HOUSING: {
        "name": "Housing",
        "description": "Real estate and construction data",
        "key_events": ["Housing Starts", "Existing Home Sales", "Building Permits"],
    },
    EventCategory.TRADE: {
        "name": "Trade",
        "description": "International trade data",
        "key_events": ["Trade Balance", "Import Prices", "Export Prices"],
    },
    EventCategory.TREASURY: {
        "name": "Treasury",
        "description": "Government bond auctions and yields",
        "key_events": ["10-Year Note Auction", "30-Year Bond Auction"],
    },
}

# Typical market reactions (historical averages)
TYPICAL_REACTIONS = {
    "Non-Farm Payrolls": {
        "spx_surprise_up": 0.3,  # % move on positive surprise
        "spx_surprise_down": -0.4,
        "vix_change": 1.5,
    },
    "CPI": {
        "spx_surprise_up": -0.2,  # Higher CPI = hawkish = stocks down
        "spx_surprise_down": 0.3,
        "vix_change": 2.0,
    },
    "Fed Interest Rate Decision": {
        "spx_surprise_up": -0.5,  # Unexpected hike
        "spx_surprise_down": 0.5,
        "vix_change": 3.0,
    },
}

# Default alert settings
DEFAULT_ALERT_MINUTES = 30
DEFAULT_SURPRISE_THRESHOLD = 0.5  # 0.5 standard deviations


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class CalendarConfig:
    """Configuration for economic calendar."""
    default_country: Country = Country.US
    include_low_impact: bool = False
    timezone: str = "America/New_York"
    alert_minutes_before: int = 30


@dataclass
class FedWatchConfig:
    """Configuration for Fed watch."""
    current_rate: float = 5.50  # Current Fed funds rate
    rate_step: float = 0.25  # Typical rate change increment


DEFAULT_CALENDAR_CONFIG = CalendarConfig()
DEFAULT_FED_CONFIG = FedWatchConfig()
