"""Sector Rotation Configuration.

Enums, constants, and configuration for sector analysis.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# =============================================================================
# Enums
# =============================================================================

class SectorName(str, Enum):
    """GICS Sector names."""
    TECHNOLOGY = "Technology"
    HEALTHCARE = "Healthcare"
    FINANCIALS = "Financials"
    CONSUMER_DISC = "Consumer Discretionary"
    CONSUMER_STAPLES = "Consumer Staples"
    ENERGY = "Energy"
    UTILITIES = "Utilities"
    REAL_ESTATE = "Real Estate"
    MATERIALS = "Materials"
    INDUSTRIALS = "Industrials"
    COMMUNICATION = "Communication Services"


class CyclePhase(str, Enum):
    """Business cycle phases."""
    EARLY_EXPANSION = "early_expansion"
    MID_EXPANSION = "mid_expansion"
    LATE_EXPANSION = "late_expansion"
    EARLY_CONTRACTION = "early_contraction"
    LATE_CONTRACTION = "late_contraction"


class Trend(str, Enum):
    """Trend direction."""
    UP = "up"
    DOWN = "down"
    NEUTRAL = "neutral"


class SignalStrength(str, Enum):
    """Signal strength levels."""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class Recommendation(str, Enum):
    """Sector recommendation."""
    OVERWEIGHT = "overweight"
    NEUTRAL = "neutral"
    UNDERWEIGHT = "underweight"


class Conviction(str, Enum):
    """Conviction level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# =============================================================================
# Constants
# =============================================================================

# Sector ETF mapping
SECTOR_ETFS = {
    SectorName.TECHNOLOGY: "XLK",
    SectorName.HEALTHCARE: "XLV",
    SectorName.FINANCIALS: "XLF",
    SectorName.CONSUMER_DISC: "XLY",
    SectorName.CONSUMER_STAPLES: "XLP",
    SectorName.ENERGY: "XLE",
    SectorName.UTILITIES: "XLU",
    SectorName.REAL_ESTATE: "XLRE",
    SectorName.MATERIALS: "XLB",
    SectorName.INDUSTRIALS: "XLI",
    SectorName.COMMUNICATION: "XLC",
}

# ETF to sector reverse mapping
ETF_TO_SECTOR = {v: k for k, v in SECTOR_ETFS.items()}

# Sector characteristics
SECTOR_CHARACTERISTICS = {
    SectorName.TECHNOLOGY: {
        "type": "growth",
        "rate_sensitive": True,
        "cyclical": True,
        "beta": 1.2,
    },
    SectorName.HEALTHCARE: {
        "type": "defensive",
        "rate_sensitive": False,
        "cyclical": False,
        "beta": 0.8,
    },
    SectorName.FINANCIALS: {
        "type": "cyclical",
        "rate_sensitive": True,
        "cyclical": True,
        "beta": 1.1,
    },
    SectorName.CONSUMER_DISC: {
        "type": "cyclical",
        "rate_sensitive": True,
        "cyclical": True,
        "beta": 1.1,
    },
    SectorName.CONSUMER_STAPLES: {
        "type": "defensive",
        "rate_sensitive": False,
        "cyclical": False,
        "beta": 0.7,
    },
    SectorName.ENERGY: {
        "type": "cyclical",
        "rate_sensitive": False,
        "cyclical": True,
        "beta": 1.3,
    },
    SectorName.UTILITIES: {
        "type": "defensive",
        "rate_sensitive": True,
        "cyclical": False,
        "beta": 0.5,
    },
    SectorName.REAL_ESTATE: {
        "type": "income",
        "rate_sensitive": True,
        "cyclical": False,
        "beta": 0.9,
    },
    SectorName.MATERIALS: {
        "type": "cyclical",
        "rate_sensitive": False,
        "cyclical": True,
        "beta": 1.1,
    },
    SectorName.INDUSTRIALS: {
        "type": "cyclical",
        "rate_sensitive": False,
        "cyclical": True,
        "beta": 1.0,
    },
    SectorName.COMMUNICATION: {
        "type": "growth",
        "rate_sensitive": True,
        "cyclical": True,
        "beta": 1.0,
    },
}

# Business cycle sector preferences
CYCLE_SECTOR_PREFERENCES = {
    CyclePhase.EARLY_EXPANSION: {
        "overweight": [SectorName.FINANCIALS, SectorName.CONSUMER_DISC, SectorName.INDUSTRIALS, SectorName.REAL_ESTATE],
        "underweight": [SectorName.UTILITIES, SectorName.CONSUMER_STAPLES],
    },
    CyclePhase.MID_EXPANSION: {
        "overweight": [SectorName.TECHNOLOGY, SectorName.INDUSTRIALS, SectorName.MATERIALS, SectorName.COMMUNICATION],
        "underweight": [SectorName.UTILITIES, SectorName.CONSUMER_STAPLES],
    },
    CyclePhase.LATE_EXPANSION: {
        "overweight": [SectorName.ENERGY, SectorName.MATERIALS, SectorName.HEALTHCARE],
        "underweight": [SectorName.TECHNOLOGY, SectorName.CONSUMER_DISC, SectorName.REAL_ESTATE],
    },
    CyclePhase.EARLY_CONTRACTION: {
        "overweight": [SectorName.HEALTHCARE, SectorName.CONSUMER_STAPLES, SectorName.UTILITIES],
        "underweight": [SectorName.FINANCIALS, SectorName.INDUSTRIALS, SectorName.MATERIALS],
    },
    CyclePhase.LATE_CONTRACTION: {
        "overweight": [SectorName.UTILITIES, SectorName.CONSUMER_STAPLES, SectorName.HEALTHCARE],
        "underweight": [SectorName.ENERGY, SectorName.MATERIALS, SectorName.INDUSTRIALS],
    },
}

# Default benchmark
DEFAULT_BENCHMARK = "SPY"

# Relative strength periods
RS_PERIODS = {
    "short": 20,   # 1 month
    "medium": 60,  # 3 months
    "long": 120,   # 6 months
}


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class SectorConfig:
    """Configuration for sector analysis."""
    benchmark: str = "SPY"
    rs_period: int = 60  # days
    momentum_period: int = 20
    rotation_threshold: float = 0.05  # 5% RS change


@dataclass
class CycleConfig:
    """Configuration for business cycle detection."""
    use_yield_curve: bool = True
    use_leading_indicators: bool = True
    smoothing_period: int = 3  # months


DEFAULT_SECTOR_CONFIG = SectorConfig()
DEFAULT_CYCLE_CONFIG = CycleConfig()
