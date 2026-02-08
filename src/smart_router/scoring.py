"""Venue scoring and fill probability estimation."""

import math
from typing import Dict, List, Optional

from .config import DEFAULT_WEIGHTS, RoutingConfig
from .models import FillProbability, RoutingScore, Venue


class RouteScorer:
    """Scores venues for optimal routing decisions."""

    def __init__(self, config: Optional[RoutingConfig] = None):
        self.config = config or RoutingConfig()

    def estimate_fill_probability(
        self,
        venue: Venue,
        quantity: int,
        is_aggressive: bool = True,
        adv: float = 1_000_000,
    ) -> FillProbability:
        """Estimate fill probability for a given venue and order size."""
        base_rate = venue.fill_rate

        # Adjust for participation rate
        participation = quantity / max(adv, 1)
        size_penalty = max(0, 1.0 - participation * 5)

        # Aggressive orders fill more reliably
        aggression_bonus = 0.10 if is_aggressive else -0.05

        prob = min(1.0, base_rate * size_penalty + aggression_bonus)
        prob = max(0.0, prob)

        # Expected fill time: latency + queue time
        queue_time = venue.avg_latency_ms * (1.0 / max(prob, 0.01))
        expected_time = venue.avg_latency_ms + queue_time

        # Partial fill estimate
        partial_pct = min(1.0, 0.5 + prob * 0.5)

        confidence = min(1.0, 0.5 + venue.volume_24h / 100_000_000)

        return FillProbability(
            venue_id=venue.venue_id,
            probability=prob,
            expected_fill_time_ms=expected_time,
            partial_fill_pct=partial_pct,
            confidence=confidence,
        )

    def score_venue(
        self,
        venue: Venue,
        fill_prob: FillProbability,
        net_cost: float,
        max_latency: float = 10.0,
        max_cost: float = 0.01,
    ) -> RoutingScore:
        """Calculate composite routing score for a venue."""
        # Fill probability score (0-1)
        fill_score = fill_prob.probability

        # Cost score (lower is better, inverted to 0-1)
        cost_score = max(0.0, 1.0 - abs(net_cost) / max(max_cost, 0.0001))

        # Latency score (lower is better)
        latency_score = max(0.0, 1.0 - venue.avg_latency_ms / max(max_latency, 0.1))

        # Price improvement score
        pi_score = min(1.0, venue.avg_price_improvement / 0.001) if venue.avg_price_improvement > 0 else 0.0

        # Adverse selection score (lower is better)
        as_score = max(0.0, 1.0 - venue.adverse_selection_rate / 0.10)

        # Weighted composite
        composite = (
            fill_score * self.config.fill_weight
            + cost_score * self.config.cost_weight
            + latency_score * self.config.latency_weight
            + pi_score * self.config.impact_weight
            + as_score * self.config.adverse_selection_weight
        )

        return RoutingScore(
            venue_id=venue.venue_id,
            fill_score=fill_score,
            cost_score=cost_score,
            latency_score=latency_score,
            price_improvement_score=pi_score,
            adverse_selection_score=as_score,
            composite_score=composite,
        )

    def rank_venues(self, scores: List[RoutingScore]) -> List[RoutingScore]:
        """Rank venues by composite score."""
        ranked = sorted(scores, key=lambda s: s.composite_score, reverse=True)
        for i, s in enumerate(ranked):
            s.rank = i + 1
        return ranked

    def score_all_venues(
        self,
        venues: List[Venue],
        quantity: int,
        is_aggressive: bool = True,
        adv: float = 1_000_000,
    ) -> List[RoutingScore]:
        """Score and rank all venues for an order."""
        scores = []
        for venue in venues:
            fill_prob = self.estimate_fill_probability(venue, quantity, is_aggressive, adv)

            # Net cost depends on maker/taker
            net_cost = venue.taker_fee if is_aggressive else venue.maker_fee

            score = self.score_venue(venue, fill_prob, net_cost)
            scores.append(score)

        return self.rank_venues(scores)
