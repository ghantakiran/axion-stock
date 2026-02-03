"""Credit Risk Analysis Configuration."""

from dataclasses import dataclass, field
from enum import Enum


class CreditRating(Enum):
    """Credit rating scale."""
    AAA = "AAA"
    AA = "AA"
    A = "A"
    BBB = "BBB"
    BB = "BB"
    B = "B"
    CCC = "CCC"
    D = "D"


class RatingOutlook(Enum):
    """Rating outlook."""
    POSITIVE = "positive"
    STABLE = "stable"
    NEGATIVE = "negative"
    WATCH = "watch"


class SpreadType(Enum):
    """Credit spread type."""
    OAS = "oas"
    Z_SPREAD = "z_spread"
    ASW = "asset_swap"


class DefaultModel(Enum):
    """Default probability model."""
    MERTON = "merton"
    CDS_IMPLIED = "cds_implied"
    STATISTICAL = "statistical"


# Numeric ordering for ratings (lower = better credit)
RATING_ORDER: dict[CreditRating, int] = {
    CreditRating.AAA: 1,
    CreditRating.AA: 2,
    CreditRating.A: 3,
    CreditRating.BBB: 4,
    CreditRating.BB: 5,
    CreditRating.B: 6,
    CreditRating.CCC: 7,
    CreditRating.D: 8,
}

# Investment grade boundary
INVESTMENT_GRADE = {CreditRating.AAA, CreditRating.AA, CreditRating.A, CreditRating.BBB}


@dataclass
class SpreadConfig:
    """Spread analysis config."""
    lookback_periods: int = 252
    z_score_window: int = 60
    widening_threshold_bps: float = 20.0
    tightening_threshold_bps: float = -20.0


@dataclass
class DefaultConfig:
    """Default probability config."""
    default_recovery_rate: float = 0.40
    risk_free_rate: float = 0.045
    default_maturity: float = 1.0


@dataclass
class RatingConfig:
    """Rating tracker config."""
    min_history: int = 4
    momentum_window: int = 8


@dataclass
class StructureConfig:
    """Debt structure config."""
    high_leverage_threshold: float = 4.0  # debt/EBITDA
    low_coverage_threshold: float = 2.0  # interest coverage
    near_term_maturity_years: int = 3
    refinancing_risk_pct: float = 0.30  # % of debt maturing in near term


@dataclass
class CreditConfig:
    """Top-level credit config."""
    spread: SpreadConfig = field(default_factory=SpreadConfig)
    default: DefaultConfig = field(default_factory=DefaultConfig)
    rating: RatingConfig = field(default_factory=RatingConfig)
    structure: StructureConfig = field(default_factory=StructureConfig)


DEFAULT_CREDIT_CONFIG = CreditConfig()
