"""Credit Risk Analysis.

Credit spread modeling, default probability estimation, credit rating
migration tracking, and debt structure analysis.
"""

from src.credit.config import (
    CreditRating,
    RatingOutlook,
    SpreadType,
    DefaultModel,
    RATING_ORDER,
    INVESTMENT_GRADE,
    SpreadConfig,
    DefaultConfig,
    RatingConfig,
    StructureConfig,
    CreditConfig,
    DEFAULT_CREDIT_CONFIG,
)

from src.credit.models import (
    CreditSpread,
    SpreadSummary,
    DefaultProbability,
    RatingSnapshot,
    RatingTransition,
    DebtItem,
    DebtStructure,
)

from src.credit.spreads import SpreadAnalyzer
from src.credit.default import DefaultEstimator
from src.credit.rating import RatingTracker
from src.credit.structure import DebtAnalyzer

__all__ = [
    # Config
    "CreditRating",
    "RatingOutlook",
    "SpreadType",
    "DefaultModel",
    "RATING_ORDER",
    "INVESTMENT_GRADE",
    "SpreadConfig",
    "DefaultConfig",
    "RatingConfig",
    "StructureConfig",
    "CreditConfig",
    "DEFAULT_CREDIT_CONFIG",
    # Models
    "CreditSpread",
    "SpreadSummary",
    "DefaultProbability",
    "RatingSnapshot",
    "RatingTransition",
    "DebtItem",
    "DebtStructure",
    # Analyzers
    "SpreadAnalyzer",
    "DefaultEstimator",
    "RatingTracker",
    "DebtAnalyzer",
]
