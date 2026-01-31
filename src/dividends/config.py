"""Dividend Tracker Configuration.

Enums, constants, and configuration for dividend tracking.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =============================================================================
# Enums
# =============================================================================

class DividendFrequency(str, Enum):
    """Dividend payment frequency."""
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    SEMI_ANNUAL = "semi_annual"
    ANNUAL = "annual"
    IRREGULAR = "irregular"


class DividendType(str, Enum):
    """Type of dividend."""
    REGULAR = "regular"
    SPECIAL = "special"
    RETURN_OF_CAPITAL = "return_of_capital"
    STOCK_DIVIDEND = "stock_dividend"


class SafetyRating(str, Enum):
    """Dividend safety rating."""
    VERY_SAFE = "very_safe"
    SAFE = "safe"
    MODERATE = "moderate"
    RISKY = "risky"
    DANGEROUS = "dangerous"


class DividendStatus(str, Enum):
    """Dividend aristocrat/king status."""
    KING = "king"            # 50+ years
    ARISTOCRAT = "aristocrat"  # 25+ years
    ACHIEVER = "achiever"    # 10+ years
    CONTENDER = "contender"  # 5-9 years
    CHALLENGER = "challenger"  # 1-4 years
    NONE = "none"


class TaxClassification(str, Enum):
    """Tax classification of dividends."""
    QUALIFIED = "qualified"
    NON_QUALIFIED = "non_qualified"
    RETURN_OF_CAPITAL = "return_of_capital"
    FOREIGN = "foreign"


# =============================================================================
# Constants
# =============================================================================

# Frequency multipliers (to annualize)
FREQUENCY_MULTIPLIERS = {
    DividendFrequency.MONTHLY: 12,
    DividendFrequency.QUARTERLY: 4,
    DividendFrequency.SEMI_ANNUAL: 2,
    DividendFrequency.ANNUAL: 1,
    DividendFrequency.IRREGULAR: 1,
}

# Safety thresholds
PAYOUT_RATIO_THRESHOLDS = {
    "very_safe": 0.40,
    "safe": 0.60,
    "moderate": 0.75,
    "risky": 0.90,
}

COVERAGE_RATIO_THRESHOLDS = {
    "very_safe": 2.5,
    "safe": 2.0,
    "moderate": 1.5,
    "risky": 1.0,
}

# Dividend aristocrat thresholds
KING_YEARS = 50
ARISTOCRAT_YEARS = 25
ACHIEVER_YEARS = 10
CONTENDER_YEARS = 5

# Tax rates (2024 estimates)
QUALIFIED_TAX_RATES = {
    "0%": (0, 44625),
    "15%": (44625, 492300),
    "20%": (492300, float('inf')),
}

ORDINARY_TAX_RATES = {
    "10%": (0, 11600),
    "12%": (11600, 47150),
    "22%": (47150, 100525),
    "24%": (100525, 191950),
    "32%": (191950, 243725),
    "35%": (243725, 609350),
    "37%": (609350, float('inf')),
}

# Sector average yields (approximate)
SECTOR_YIELDS = {
    "Utilities": 0.035,
    "Real Estate": 0.040,
    "Consumer Defensive": 0.028,
    "Energy": 0.032,
    "Financial": 0.025,
    "Healthcare": 0.018,
    "Industrial": 0.020,
    "Technology": 0.010,
    "Consumer Cyclical": 0.015,
    "Communication Services": 0.012,
    "Basic Materials": 0.022,
}


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class DividendConfig:
    """Configuration for dividend tracking."""
    # Projection settings
    default_growth_rate: float = 0.05  # 5% dividend growth
    default_price_growth: float = 0.07  # 7% price appreciation
    
    # Tax settings
    qualified_rate: float = 0.15
    ordinary_rate: float = 0.22
    state_tax_rate: float = 0.05
    
    # Safety thresholds
    max_safe_payout: float = 0.60
    min_safe_coverage: float = 1.5


@dataclass
class DRIPConfig:
    """Configuration for DRIP simulation."""
    years: int = 20
    dividend_growth_rate: float = 0.05
    price_growth_rate: float = 0.07
    reinvest_dividends: bool = True


DEFAULT_DIVIDEND_CONFIG = DividendConfig()
DEFAULT_DRIP_CONFIG = DRIPConfig()
