"""Core smart order routing engine."""

import uuid
from datetime import datetime
from typing import Dict, List, Optional

from .config import RoutingConfig, RoutingStrategy
from .cost import CostOptimizer
from .models import (
    RouteDecision,
    RouteSplit,
    RoutingAudit,
    RoutingScore,
    Venue,
)
from .scoring import RouteScorer
from .venue import VenueManager


class SmartRouter:
    """Multi-venue smart order router with scoring-based venue selection."""

    def __init__(
        self,
        venue_manager: Optional[VenueManager] = None,
        config: Optional[RoutingConfig] = None,
    ):
        self.config = config or RoutingConfig()
        self.venue_mgr = venue_manager or VenueManager.create_default_venues()
        self.scorer = RouteScorer(self.config)
        self.cost_optimizer = CostOptimizer()
        self._audit_log: List[RoutingAudit] = []

    def route_order(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: int,
        price: float = 100.0,
        adv: float = 1_000_000,
        nbbo_bid: float = 0.0,
        nbbo_ask: float = 0.0,
    ) -> RouteDecision:
        """Route an order across optimal venues."""
        venues = self.venue_mgr.list_venues()
        if not venues:
            return RouteDecision(
                order_id=order_id, symbol=symbol, side=side,
                total_quantity=quantity, strategy=self.config.strategy.value,
            )

        is_aggressive = side.lower() == "buy"

        # Score all venues
        scores = self.scorer.score_all_venues(venues, quantity, is_aggressive, adv)

        # Select top venues — ensure dark pools are included for SMART strategy
        top_venues = scores[:self.config.max_venues]
        if self.config.strategy in (RoutingStrategy.SMART, RoutingStrategy.LOWEST_IMPACT):
            venue_map_ids = {v.venue_id for v in venues}
            dark_ids = {v.venue_id for v in venues if v.venue_type in ("dark_pool", "midpoint")}
            included_ids = {s.venue_id for s in top_venues}
            for s in scores:
                if s.venue_id in dark_ids and s.venue_id not in included_ids:
                    top_venues.append(s)
                    included_ids.add(s.venue_id)

        # Determine splits based on strategy
        splits = self._create_splits(
            top_venues, venues, quantity, price, adv
        )

        # Calculate total cost
        total_cost = sum(s.estimated_cost for s in splits)

        decision = RouteDecision(
            order_id=order_id,
            symbol=symbol,
            side=side,
            total_quantity=quantity,
            strategy=self.config.strategy.value,
            splits=splits,
            scores=top_venues,
            total_estimated_cost=total_cost,
            nbbo_bid=nbbo_bid,
            nbbo_ask=nbbo_ask,
        )

        # Audit trail
        self._record_audit(decision, scores)

        return decision

    def _create_splits(
        self,
        top_scores: List[RoutingScore],
        all_venues: List[Venue],
        total_qty: int,
        price: float,
        adv: float,
    ) -> List[RouteSplit]:
        """Create order splits based on routing strategy."""
        venue_map = {v.venue_id: v for v in all_venues}
        splits = []
        remaining = total_qty

        if self.config.strategy == RoutingStrategy.BEST_PRICE:
            # Route to venue with best price (highest composite score)
            if top_scores:
                venue = venue_map.get(top_scores[0].venue_id)
                if venue:
                    cost_est = self.cost_optimizer.estimate_cost(venue, total_qty, price, adv)
                    splits.append(RouteSplit(
                        venue_id=venue.venue_id,
                        quantity=total_qty,
                        estimated_cost=cost_est.net_cost,
                        fill_probability=top_scores[0].fill_score,
                    ))
            return splits

        elif self.config.strategy == RoutingStrategy.FASTEST_FILL:
            # Route to fastest venues proportionally
            for score in top_scores:
                if remaining <= 0:
                    break
                venue = venue_map.get(score.venue_id)
                if not venue:
                    continue
                qty = min(remaining, max(self.config.min_slice_size, total_qty // len(top_scores)))
                cost_est = self.cost_optimizer.estimate_cost(venue, qty, price, adv)
                splits.append(RouteSplit(
                    venue_id=venue.venue_id,
                    quantity=qty,
                    estimated_cost=cost_est.net_cost,
                    fill_probability=score.fill_score,
                ))
                remaining -= qty

        elif self.config.strategy == RoutingStrategy.LOWEST_COST:
            # Route to cheapest venue
            cheapest = self.cost_optimizer.find_cheapest(all_venues, total_qty, price, adv)
            if cheapest:
                venue = venue_map.get(cheapest.venue_id)
                score = next((s for s in top_scores if s.venue_id == cheapest.venue_id), None)
                splits.append(RouteSplit(
                    venue_id=cheapest.venue_id,
                    quantity=total_qty,
                    estimated_cost=cheapest.net_cost,
                    fill_probability=score.fill_score if score else 0.5,
                ))
            return splits

        else:  # SMART or LOWEST_IMPACT
            # Score-weighted split with dark pool allocation
            dark_venues = [s for s in top_scores if venue_map.get(s.venue_id) and
                          venue_map[s.venue_id].venue_type in ("dark_pool", "midpoint")]
            lit_venues = [s for s in top_scores if s not in dark_venues]

            # Allocate dark pool portion
            dark_qty = int(total_qty * self.config.dark_pool_pct)
            lit_qty = total_qty - dark_qty

            # Dark pool splits
            for score in dark_venues:
                if dark_qty <= 0:
                    break
                venue = venue_map.get(score.venue_id)
                if not venue:
                    continue
                qty = min(dark_qty, max(self.config.min_slice_size, dark_qty // max(len(dark_venues), 1)))
                cost_est = self.cost_optimizer.estimate_cost(venue, qty, price, adv)
                splits.append(RouteSplit(
                    venue_id=venue.venue_id,
                    quantity=qty,
                    is_hidden=True,
                    is_midpoint=True,
                    estimated_cost=cost_est.net_cost,
                    fill_probability=score.fill_score,
                ))
                dark_qty -= qty
                remaining -= qty

            # Remaining lit allocation (unfilled dark goes to lit)
            lit_qty += dark_qty  # Remainder from dark
            if lit_venues:
                total_score = sum(s.composite_score for s in lit_venues)
                for score in lit_venues:
                    if lit_qty <= 0:
                        break
                    venue = venue_map.get(score.venue_id)
                    if not venue:
                        continue
                    weight = score.composite_score / max(total_score, 0.001)
                    qty = max(self.config.min_slice_size, int(lit_qty * weight))
                    qty = min(qty, lit_qty)
                    cost_est = self.cost_optimizer.estimate_cost(venue, qty, price, adv)
                    splits.append(RouteSplit(
                        venue_id=venue.venue_id,
                        quantity=qty,
                        estimated_cost=cost_est.net_cost,
                        fill_probability=score.fill_score,
                    ))
                    lit_qty -= qty

        return splits

    def _record_audit(self, decision: RouteDecision, all_scores: List[RoutingScore]) -> None:
        audit = RoutingAudit(
            audit_id=str(uuid.uuid4())[:8],
            order_id=decision.order_id,
            symbol=decision.symbol,
            side=decision.side,
            quantity=decision.total_quantity,
            strategy=decision.strategy,
            venues_considered=len(all_scores),
            venues_selected=decision.n_venues,
            nbbo_at_decision={"bid": decision.nbbo_bid, "ask": decision.nbbo_ask},
            routing_scores=[
                {"venue": s.venue_id, "score": round(s.composite_score, 4)}
                for s in all_scores[:5]
            ],
            decision_rationale=f"{decision.strategy} routing to {decision.n_venues} venues",
            reg_nms_compliant=self.config.enable_trade_through_prevention,
        )
        self._audit_log.append(audit)

    def get_audit_log(self) -> List[RoutingAudit]:
        return self._audit_log

    def get_venue_stats(self) -> Dict[str, int]:
        """Get routing statistics by venue."""
        stats: Dict[str, int] = {}
        for audit in self._audit_log:
            for score_info in audit.routing_scores:
                vid = score_info["venue"]
                stats[vid] = stats.get(vid, 0) + 1
        return stats

    @staticmethod
    def generate_sample_decision() -> RouteDecision:
        """Generate a sample routing decision for demo."""
        router = SmartRouter()
        return router.route_order(
            order_id="ORD-001",
            symbol="AAPL",
            side="buy",
            quantity=5000,
            price=175.50,
            adv=25_000_000,
            nbbo_bid=175.48,
            nbbo_ask=175.52,
        )
