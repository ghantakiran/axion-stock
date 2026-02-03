"""Credit Risk Analysis Models."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from src.credit.config import (
    CreditRating,
    RatingOutlook,
    SpreadType,
    DefaultModel,
    RATING_ORDER,
    INVESTMENT_GRADE,
)


@dataclass
class CreditSpread:
    """Point-in-time credit spread observation."""
    symbol: str
    spread_bps: float = 0.0
    z_score: float = 0.0
    percentile: float = 0.0
    term: float = 5.0  # years
    spread_type: SpreadType = SpreadType.OAS
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def spread_pct(self) -> float:
        """Spread in percentage."""
        return self.spread_bps / 100.0

    @property
    def is_wide(self) -> bool:
        return self.z_score > 1.0

    @property
    def is_tight(self) -> bool:
        return self.z_score < -1.0


@dataclass
class SpreadSummary:
    """Aggregated spread analysis."""
    symbol: str
    current_spread: float = 0.0
    avg_spread: float = 0.0
    min_spread: float = 0.0
    max_spread: float = 0.0
    std_spread: float = 0.0
    trend: float = 0.0
    z_score: float = 0.0
    percentile: float = 0.0
    n_observations: int = 0

    @property
    def is_widening(self) -> bool:
        return self.trend > 0

    @property
    def range_bps(self) -> float:
        return self.max_spread - self.min_spread


@dataclass
class DefaultProbability:
    """Default probability estimate."""
    symbol: str
    pd_1y: float = 0.0
    pd_5y: float = 0.0
    model: DefaultModel = DefaultModel.MERTON
    distance_to_default: float = 0.0
    recovery_rate: float = 0.40

    @property
    def survival_1y(self) -> float:
        return 1.0 - self.pd_1y

    @property
    def survival_5y(self) -> float:
        return 1.0 - self.pd_5y

    @property
    def expected_loss_1y(self) -> float:
        """Expected loss = PD * (1 - recovery)."""
        return self.pd_1y * (1.0 - self.recovery_rate)


@dataclass
class RatingSnapshot:
    """Credit rating at a point in time."""
    symbol: str
    rating: CreditRating
    outlook: RatingOutlook = RatingOutlook.STABLE
    previous_rating: Optional[CreditRating] = None
    as_of: date = field(default_factory=date.today)

    @property
    def is_investment_grade(self) -> bool:
        return self.rating in INVESTMENT_GRADE

    @property
    def migration_direction(self) -> str:
        """upgrade, downgrade, or stable."""
        if self.previous_rating is None:
            return "stable"
        curr = RATING_ORDER.get(self.rating, 99)
        prev = RATING_ORDER.get(self.previous_rating, 99)
        if curr < prev:
            return "upgrade"
        elif curr > prev:
            return "downgrade"
        return "stable"

    @property
    def numeric_rating(self) -> int:
        return RATING_ORDER.get(self.rating, 99)


@dataclass
class RatingTransition:
    """Rating transition probability."""
    from_rating: CreditRating
    to_rating: CreditRating
    probability: float = 0.0
    historical_count: int = 0

    @property
    def is_upgrade(self) -> bool:
        return RATING_ORDER[self.to_rating] < RATING_ORDER[self.from_rating]

    @property
    def is_downgrade(self) -> bool:
        return RATING_ORDER[self.to_rating] > RATING_ORDER[self.from_rating]


@dataclass
class DebtItem:
    """Individual debt instrument."""
    name: str
    amount: float = 0.0
    maturity_date: Optional[date] = None
    coupon_rate: float = 0.0
    is_secured: bool = False

    @property
    def years_to_maturity(self) -> float:
        if self.maturity_date is None:
            return 0.0
        delta = (self.maturity_date - date.today()).days
        return max(delta / 365.25, 0.0)


@dataclass
class DebtStructure:
    """Comprehensive debt structure analysis."""
    symbol: str
    total_debt: float = 0.0
    net_debt: float = 0.0
    leverage_ratio: float = 0.0
    interest_coverage: float = 0.0
    avg_maturity: float = 0.0
    avg_coupon: float = 0.0
    near_term_pct: float = 0.0
    refinancing_risk: float = 0.0
    credit_health: float = 0.0

    @property
    def is_high_leverage(self) -> bool:
        return self.leverage_ratio > 4.0

    @property
    def is_low_coverage(self) -> bool:
        return 0 < self.interest_coverage < 2.0
