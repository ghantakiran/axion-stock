"""Enhanced M&A Probability Modeling.

Estimates deal completion probability using regulatory timeline,
antitrust risk, financing conditions, and historical completion
rates by deal type.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional
from datetime import date

import numpy as np

from src.events.config import MergerConfig
from src.events.models import MergerEvent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class DealRiskFactors:
    """Risk factor decomposition for a deal."""
    regulatory_risk: float = 0.0  # 0 (low) to 1 (high)
    financing_risk: float = 0.0
    antitrust_risk: float = 0.0
    shareholder_risk: float = 0.0
    market_risk: float = 0.0

    @property
    def total_risk(self) -> float:
        return min(1.0, (
            self.regulatory_risk * 0.30
            + self.financing_risk * 0.25
            + self.antitrust_risk * 0.25
            + self.shareholder_risk * 0.10
            + self.market_risk * 0.10
        ))

    @property
    def risk_level(self) -> str:
        if self.total_risk >= 0.6:
            return "high"
        elif self.total_risk >= 0.3:
            return "medium"
        return "low"


@dataclass
class CompletionEstimate:
    """Deal completion probability estimate."""
    target: str = ""
    acquirer: str = ""
    base_probability: float = 0.0
    adjusted_probability: float = 0.0
    risk_factors: DealRiskFactors = field(default_factory=DealRiskFactors)
    expected_days_to_close: int = 0
    confidence: float = 0.0

    # Component adjustments
    status_factor: float = 0.0
    deal_type_factor: float = 0.0
    spread_signal: float = 0.0
    size_factor: float = 0.0

    @property
    def is_likely(self) -> bool:
        return self.adjusted_probability >= 0.70

    @property
    def risk_adjusted_return(self) -> float:
        """Expected return adjusted for completion risk."""
        return self.adjusted_probability * self.spread_signal


@dataclass
class HistoricalRates:
    """Historical completion rates by category."""
    overall_rate: float = 0.85
    cash_deal_rate: float = 0.92
    stock_deal_rate: float = 0.78
    hostile_rate: float = 0.45
    friendly_rate: float = 0.88
    cross_border_rate: float = 0.75
    same_industry_rate: float = 0.87

    @property
    def rates_dict(self) -> dict[str, float]:
        return {
            "overall": self.overall_rate,
            "cash": self.cash_deal_rate,
            "stock": self.stock_deal_rate,
            "hostile": self.hostile_rate,
            "friendly": self.friendly_rate,
            "cross_border": self.cross_border_rate,
            "same_industry": self.same_industry_rate,
        }


# ---------------------------------------------------------------------------
# Probability Modeler
# ---------------------------------------------------------------------------
class DealProbabilityModeler:
    """Enhanced M&A completion probability estimation."""

    # Historical base rates by deal status
    STATUS_BASE_RATES = {
        "announced": 0.65,
        "pending": 0.75,
        "approved": 0.95,
        "closed": 1.0,
        "terminated": 0.0,
    }

    def __init__(
        self,
        config: Optional[MergerConfig] = None,
        historical_rates: Optional[HistoricalRates] = None,
    ) -> None:
        self.config = config or MergerConfig()
        self.rates = historical_rates or HistoricalRates()

    def estimate_probability(
        self,
        deal: MergerEvent,
        is_hostile: bool = False,
        is_cross_border: bool = False,
        has_financing: bool = True,
        regulatory_filings: int = 0,
        competing_bids: int = 0,
    ) -> CompletionEstimate:
        """Estimate deal completion probability.

        Args:
            deal: M&A event details.
            is_hostile: Whether the deal is hostile.
            is_cross_border: Cross-border transaction.
            has_financing: Committed financing in place.
            regulatory_filings: Number of regulatory filings required.
            competing_bids: Number of competing bids.

        Returns:
            CompletionEstimate with risk-adjusted probability.
        """
        status = deal.status.value if hasattr(deal.status, 'value') else str(deal.status)
        base_prob = self.STATUS_BASE_RATES.get(status, 0.65)

        # Deal type adjustment
        if deal.is_cash:
            type_factor = self.rates.cash_deal_rate / self.rates.overall_rate
        else:
            type_factor = self.rates.stock_deal_rate / self.rates.overall_rate
        type_adj = (type_factor - 1.0) * 0.5

        # Risk factors
        risks = self._compute_risk_factors(
            deal, is_hostile, is_cross_border, has_financing,
            regulatory_filings, competing_bids,
        )

        # Size factor: larger deals have slightly lower completion rate
        size_adj = 0.0
        if deal.deal_value > 50_000_000_000:  # >$50B
            size_adj = -0.05
        elif deal.deal_value > 10_000_000_000:  # >$10B
            size_adj = -0.02

        # Spread signal: wide spread suggests market doubts
        spread_signal = 0.0
        if deal.spread > 0:
            if deal.spread > 0.20:  # >20% spread
                spread_signal = -0.10
            elif deal.spread > 0.10:
                spread_signal = -0.05
            elif deal.spread < 0.02:  # Very tight
                spread_signal = 0.05

        # Competing bids increase probability (bidding war)
        compete_adj = min(0.10, competing_bids * 0.05) if competing_bids > 0 else 0.0

        # Final adjusted probability
        adjusted = base_prob + type_adj - risks.total_risk + size_adj + spread_signal + compete_adj
        adjusted = max(0.0, min(1.0, adjusted))

        # Confidence based on information quality
        confidence = self._estimate_confidence(deal, regulatory_filings)

        # Expected days to close
        expected_days = self._estimate_timeline(deal, regulatory_filings)

        return CompletionEstimate(
            target=deal.target,
            acquirer=deal.acquirer,
            base_probability=round(base_prob, 4),
            adjusted_probability=round(adjusted, 4),
            risk_factors=risks,
            expected_days_to_close=expected_days,
            confidence=round(confidence, 4),
            status_factor=round(base_prob, 4),
            deal_type_factor=round(type_adj, 4),
            spread_signal=round(deal.spread, 4),
            size_factor=round(size_adj, 4),
        )

    def compare_deals(
        self,
        estimates: list[CompletionEstimate],
    ) -> list[CompletionEstimate]:
        """Rank deals by risk-adjusted return.

        Args:
            estimates: List of deal completion estimates.

        Returns:
            Sorted list (best opportunity first).
        """
        return sorted(
            estimates,
            key=lambda e: e.adjusted_probability * max(0, e.spread_signal),
            reverse=True,
        )

    def _compute_risk_factors(
        self,
        deal: MergerEvent,
        is_hostile: bool,
        is_cross_border: bool,
        has_financing: bool,
        regulatory_filings: int,
        competing_bids: int,
    ) -> DealRiskFactors:
        """Compute individual risk factors."""
        # Regulatory risk
        reg_risk = min(1.0, regulatory_filings * 0.15)
        if is_cross_border:
            reg_risk = min(1.0, reg_risk + 0.20)

        # Financing risk
        fin_risk = 0.0 if has_financing else 0.30
        if not deal.is_cash and not has_financing:
            fin_risk += 0.10

        # Antitrust risk
        anti_risk = 0.0
        if deal.deal_value > 10_000_000_000:
            anti_risk = 0.15
        if regulatory_filings >= 3:
            anti_risk = min(1.0, anti_risk + 0.20)

        # Shareholder risk
        sh_risk = 0.20 if is_hostile else 0.05
        if competing_bids > 0:
            sh_risk = min(1.0, sh_risk + 0.10)

        # Market risk: based on deal duration
        market_risk = 0.10  # Base market risk

        return DealRiskFactors(
            regulatory_risk=round(reg_risk, 4),
            financing_risk=round(fin_risk, 4),
            antitrust_risk=round(anti_risk, 4),
            shareholder_risk=round(sh_risk, 4),
            market_risk=round(market_risk, 4),
        )

    def _estimate_confidence(
        self, deal: MergerEvent, regulatory_filings: int
    ) -> float:
        """Estimate confidence in the probability estimate."""
        status = deal.status.value if hasattr(deal.status, 'value') else str(deal.status)
        # Higher confidence for later-stage deals
        base = {"announced": 0.5, "pending": 0.65, "approved": 0.85,
                "closed": 1.0, "terminated": 1.0}
        conf = base.get(status, 0.5)
        # More info = higher confidence
        if deal.deal_value > 0:
            conf += 0.05
        if regulatory_filings > 0:
            conf += 0.05
        return min(1.0, conf)

    def _estimate_timeline(
        self, deal: MergerEvent, regulatory_filings: int
    ) -> int:
        """Estimate days to closing."""
        status = deal.status.value if hasattr(deal.status, 'value') else str(deal.status)
        base_days = {"announced": 180, "pending": 120, "approved": 30,
                     "closed": 0, "terminated": 0}
        days = base_days.get(status, 180)
        # Regulatory filings add time
        days += regulatory_filings * 30
        return days
