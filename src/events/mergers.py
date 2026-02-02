"""Merger & Acquisition Analyzer.

Scores M&A deal probability, computes risk arbitrage spreads,
and generates deal-based trading signals.
"""

import logging
from collections import defaultdict
from datetime import date
from typing import Optional

import numpy as np

from src.events.config import (
    DealStatus,
    MergerConfig,
    DEFAULT_EVENT_CONFIG,
)
from src.events.models import MergerEvent

logger = logging.getLogger(__name__)


class MergerAnalyzer:
    """Analyzes M&A deals and risk arbitrage opportunities."""

    def __init__(self, config: Optional[MergerConfig] = None) -> None:
        self.config = config or DEFAULT_EVENT_CONFIG.merger
        self._deals: dict[str, list[MergerEvent]] = defaultdict(list)

    def add_deal(self, deal: MergerEvent) -> MergerEvent:
        """Add an M&A deal."""
        self._deals[deal.target].append(deal)
        return deal

    def add_deals(self, deals: list[MergerEvent]) -> list[MergerEvent]:
        """Add multiple deals."""
        return [self.add_deal(d) for d in deals]

    def annualized_spread(self, deal: MergerEvent) -> float:
        """Compute annualized deal spread.

        Args:
            deal: Merger event with current price and offer price.

        Returns:
            Annualized spread as decimal.
        """
        if deal.current_price <= 0 or deal.offer_price <= 0:
            return 0.0

        raw_spread = deal.spread

        # Annualize based on expected close date
        if deal.expected_close and deal.expected_close > date.today():
            days_to_close = (deal.expected_close - date.today()).days
            if days_to_close > 0:
                annualized = (1 + raw_spread) ** (
                    self.config.spread_annualization_days / days_to_close
                ) - 1
                return annualized

        return raw_spread

    def estimate_probability(self, deal: MergerEvent) -> float:
        """Estimate deal completion probability.

        Factors:
        - Deal status progression (higher status = higher probability)
        - Cash vs stock (cash = higher certainty)
        - Regulatory risk adjustment
        - Spread signal (narrow spread = market believes completion)

        Args:
            deal: Merger event.

        Returns:
            Estimated probability [0, 1].
        """
        # Closed and terminated are deterministic
        if deal.status == DealStatus.CLOSED:
            return 1.0
        if deal.status == DealStatus.TERMINATED:
            return 0.0

        base_prob = {
            DealStatus.ANNOUNCED: 0.60,
            DealStatus.PENDING: 0.70,
            DealStatus.APPROVED: 0.92,
        }.get(deal.status, 0.50)

        # Cash deals are more certain
        if deal.is_cash:
            base_prob = min(base_prob + 0.05, 1.0)

        # Spread-based adjustment: narrow spread = market confident
        if deal.spread > 0:
            if deal.spread < 0.02:
                base_prob = min(base_prob + 0.05, 1.0)
            elif deal.spread > 0.10:
                base_prob = max(base_prob - 0.10, 0.0)

        # Regulatory risk
        base_prob *= (1.0 - self.config.regulatory_risk_factor)

        return round(min(max(base_prob, 0.0), 1.0), 4)

    def risk_arb_signal(self, deal: MergerEvent) -> dict:
        """Generate risk arbitrage signal for a deal.

        Returns dict with spread, annualized_spread, probability,
        expected_return, and signal direction.
        """
        if not deal.is_active:
            return {
                "target": deal.target,
                "signal": "none",
                "reason": f"deal is {deal.status.value}",
            }

        ann_spread = self.annualized_spread(deal)
        prob = self.estimate_probability(deal)
        expected = prob * deal.spread - (1 - prob) * abs(deal.premium)

        if ann_spread > 0.10 and prob >= self.config.high_probability:
            signal = "strong_buy"
        elif ann_spread > 0.05 and prob >= self.config.min_probability:
            signal = "buy"
        elif prob < self.config.min_probability:
            signal = "avoid"
        else:
            signal = "neutral"

        return {
            "target": deal.target,
            "acquirer": deal.acquirer,
            "spread": round(deal.spread, 4),
            "annualized_spread": round(ann_spread, 4),
            "probability": round(prob, 4),
            "expected_return": round(expected, 4),
            "signal": signal,
        }

    def get_active_deals(self) -> list[MergerEvent]:
        """Get all active deals."""
        active = []
        for deals in self._deals.values():
            for d in deals:
                if d.is_active:
                    active.append(d)
        return sorted(active, key=lambda d: d.announce_date, reverse=True)

    def get_deals(self, target: str) -> list[MergerEvent]:
        """Get deals for a target symbol."""
        return sorted(
            self._deals.get(target, []),
            key=lambda d: d.announce_date,
            reverse=True,
        )

    def reset(self) -> None:
        """Clear all stored deals."""
        self._deals.clear()
