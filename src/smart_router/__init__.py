"""PRD-98: Smart Order Router."""

from .config import (
    VenueType,
    RoutingStrategy,
    OrderPriority,
    FeeModel,
    VenueConfig,
    RoutingConfig,
)
from .models import (
    Venue,
    RouteDecision,
    RoutingScore,
    FillProbability,
    VenueMetrics,
    RoutingAudit,
    CostEstimate,
    RouteSplit,
)
from .venue import VenueManager
from .router import SmartRouter
from .scoring import RouteScorer
from .cost import CostOptimizer

__all__ = [
    # Config
    "VenueType",
    "RoutingStrategy",
    "OrderPriority",
    "FeeModel",
    "VenueConfig",
    "RoutingConfig",
    # Models
    "Venue",
    "RouteDecision",
    "RoutingScore",
    "FillProbability",
    "VenueMetrics",
    "RoutingAudit",
    "CostEstimate",
    "RouteSplit",
    # Core
    "VenueManager",
    "SmartRouter",
    "RouteScorer",
    "CostOptimizer",
]
