"""Event-Driven Analytics Models."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from src.events.config import (
    EventType,
    EarningsResult,
    DealStatus,
    SignalStrength,
)


@dataclass
class EarningsEvent:
    """Earnings report event."""
    symbol: str
    report_date: date
    fiscal_quarter: str = ""
    eps_estimate: float = 0.0
    eps_actual: float = 0.0
    revenue_estimate: float = 0.0
    revenue_actual: float = 0.0
    result: EarningsResult = EarningsResult.MEET
    pre_drift: float = 0.0
    post_drift: float = 0.0

    @property
    def eps_surprise(self) -> float:
        """EPS surprise as percentage."""
        if abs(self.eps_estimate) < 1e-10:
            return 0.0
        return (self.eps_actual - self.eps_estimate) / abs(self.eps_estimate)

    @property
    def revenue_surprise(self) -> float:
        """Revenue surprise as percentage."""
        if abs(self.revenue_estimate) < 1e-10:
            return 0.0
        return (self.revenue_actual - self.revenue_estimate) / abs(self.revenue_estimate)

    @property
    def is_beat(self) -> bool:
        return self.result == EarningsResult.BEAT

    @property
    def is_miss(self) -> bool:
        return self.result == EarningsResult.MISS


@dataclass
class EarningsSummary:
    """Summary of earnings history for a symbol."""
    symbol: str
    total_reports: int = 0
    beats: int = 0
    meets: int = 0
    misses: int = 0
    avg_eps_surprise: float = 0.0
    avg_revenue_surprise: float = 0.0
    avg_post_drift: float = 0.0
    streak: int = 0  # positive = consecutive beats, negative = misses

    @property
    def beat_rate(self) -> float:
        return self.beats / self.total_reports if self.total_reports > 0 else 0.0

    @property
    def miss_rate(self) -> float:
        return self.misses / self.total_reports if self.total_reports > 0 else 0.0


@dataclass
class MergerEvent:
    """M&A deal event."""
    acquirer: str
    target: str
    announce_date: date
    deal_value: float = 0.0
    offer_price: float = 0.0
    premium: float = 0.0
    probability: float = 0.5
    status: DealStatus = DealStatus.ANNOUNCED
    expected_close: Optional[date] = None
    current_price: float = 0.0
    is_cash: bool = True
    exchange_ratio: float = 0.0

    @property
    def spread(self) -> float:
        """Raw deal spread."""
        if self.current_price <= 0:
            return 0.0
        return (self.offer_price - self.current_price) / self.current_price

    @property
    def is_active(self) -> bool:
        return self.status in (DealStatus.ANNOUNCED, DealStatus.PENDING, DealStatus.APPROVED)

    @property
    def expected_return(self) -> float:
        """Probability-weighted expected return."""
        return self.probability * self.spread


@dataclass
class CorporateAction:
    """Corporate action event."""
    symbol: str
    action_type: EventType
    announce_date: date
    effective_date: Optional[date] = None
    amount: float = 0.0
    details: dict = field(default_factory=dict)

    @property
    def is_upcoming(self) -> bool:
        if self.effective_date is None:
            return False
        return self.effective_date >= date.today()

    @property
    def days_until(self) -> int:
        if self.effective_date is None:
            return -1
        return (self.effective_date - date.today()).days


@dataclass
class DividendSummary:
    """Dividend analysis summary."""
    symbol: str
    annual_dividend: float = 0.0
    current_yield: float = 0.0
    payout_ratio: float = 0.0
    growth_rate: float = 0.0
    consecutive_increases: int = 0
    ex_dates: list[date] = field(default_factory=list)

    @property
    def is_dividend_grower(self) -> bool:
        return self.consecutive_increases >= 5


@dataclass
class EventSignal:
    """Event-driven trading signal."""
    symbol: str
    event_type: EventType
    strength: SignalStrength = SignalStrength.NONE
    direction: str = "neutral"  # bullish, bearish, neutral
    score: float = 0.0
    confidence: float = 0.0
    description: str = ""

    @property
    def is_actionable(self) -> bool:
        return self.strength in (SignalStrength.STRONG, SignalStrength.MODERATE)


@dataclass
class CompositeEventScore:
    """Combined score from multiple event signals."""
    symbol: str
    earnings_score: float = 0.0
    merger_score: float = 0.0
    corporate_score: float = 0.0
    composite: float = 0.0
    n_signals: int = 0
    strength: SignalStrength = SignalStrength.NONE
    direction: str = "neutral"
    signals: list[EventSignal] = field(default_factory=list)

    @property
    def has_consensus(self) -> bool:
        if not self.signals:
            return False
        bullish = sum(1 for s in self.signals if s.direction == "bullish")
        bearish = sum(1 for s in self.signals if s.direction == "bearish")
        total = len(self.signals)
        return max(bullish, bearish) / total > 0.6 if total > 0 else False
