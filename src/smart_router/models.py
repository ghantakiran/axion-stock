"""Data models for smart order routing."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Venue:
    """Trading venue with quality metrics."""

    venue_id: str
    name: str
    venue_type: str
    maker_fee: float = 0.0
    taker_fee: float = 0.0
    avg_latency_ms: float = 1.0
    fill_rate: float = 0.80
    avg_price_improvement: float = 0.0
    adverse_selection_rate: float = 0.0
    is_active: bool = True
    volume_24h: float = 0.0


@dataclass
class FillProbability:
    """Estimated fill probability for a venue."""

    venue_id: str
    probability: float
    expected_fill_time_ms: float = 0.0
    partial_fill_pct: float = 0.0
    confidence: float = 0.0


@dataclass
class CostEstimate:
    """Total cost estimate for routing to a venue."""

    venue_id: str
    exchange_fee: float = 0.0
    spread_cost: float = 0.0
    impact_cost: float = 0.0
    opportunity_cost: float = 0.0
    total_cost: float = 0.0
    rebate: float = 0.0
    net_cost: float = 0.0


@dataclass
class RoutingScore:
    """Composite score for venue selection."""

    venue_id: str
    fill_score: float = 0.0
    cost_score: float = 0.0
    latency_score: float = 0.0
    price_improvement_score: float = 0.0
    adverse_selection_score: float = 0.0
    composite_score: float = 0.0
    rank: int = 0


@dataclass
class RouteSplit:
    """Order slice routed to a specific venue."""

    venue_id: str
    quantity: int
    price_limit: Optional[float] = None
    is_hidden: bool = False
    is_midpoint: bool = False
    estimated_cost: float = 0.0
    fill_probability: float = 0.0


@dataclass
class RouteDecision:
    """Complete routing decision for an order."""

    order_id: str
    symbol: str
    side: str
    total_quantity: int
    strategy: str
    splits: List[RouteSplit] = field(default_factory=list)
    scores: List[RoutingScore] = field(default_factory=list)
    total_estimated_cost: float = 0.0
    nbbo_bid: float = 0.0
    nbbo_ask: float = 0.0
    decided_at: datetime = field(default_factory=datetime.now)

    @property
    def n_venues(self) -> int:
        return len(self.splits)

    @property
    def dark_pool_pct(self) -> float:
        if self.total_quantity <= 0:
            return 0.0
        dark_qty = sum(s.quantity for s in self.splits if s.is_midpoint or s.is_hidden)
        return dark_qty / self.total_quantity


@dataclass
class VenueMetrics:
    """Performance metrics for a venue over time."""

    venue_id: str
    period: str
    orders_routed: int = 0
    shares_routed: int = 0
    fill_rate: float = 0.0
    avg_fill_time_ms: float = 0.0
    avg_price_improvement: float = 0.0
    avg_adverse_selection: float = 0.0
    total_fees: float = 0.0
    total_rebates: float = 0.0
    net_cost: float = 0.0


@dataclass
class RoutingAudit:
    """Audit record for routing decisions."""

    audit_id: str
    order_id: str
    symbol: str
    side: str
    quantity: int
    strategy: str
    venues_considered: int = 0
    venues_selected: int = 0
    nbbo_at_decision: Dict[str, float] = field(default_factory=dict)
    routing_scores: List[Dict[str, Any]] = field(default_factory=list)
    decision_rationale: str = ""
    reg_nms_compliant: bool = True
    decided_at: datetime = field(default_factory=datetime.now)
