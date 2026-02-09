"""Order Router -- intelligent order routing across brokers (PRD-146).

Scores available brokers on fee, speed, and fill quality, applies user-defined
routing rules, and returns the best RouteDecision for each order. Includes
smart defaults: crypto -> Coinbase, stocks -> cheapest (Alpaca default),
options -> Schwab, fractional shares -> Robinhood.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import logging
import uuid

from src.multi_broker.registry import BrokerInfo, BrokerRegistry, BrokerStatus

logger = logging.getLogger(__name__)


# =====================================================================
# Enums & Dataclasses
# =====================================================================


class RoutingCriteria(str, Enum):
    """Criteria for broker scoring."""
    COST = "cost"
    SPEED = "speed"
    FILL_QUALITY = "fill_quality"


# Default scoring weights
DEFAULT_WEIGHTS: dict[str, float] = {
    "cost": 0.4,
    "speed": 0.3,
    "fill_quality": 0.3,
}

# Smart routing defaults: asset_type -> preferred broker
SMART_DEFAULTS: dict[str, str] = {
    "crypto": "coinbase",
    "stock": "alpaca",
    "options": "schwab",
    "mutual_funds": "schwab",
    "fractional": "robinhood",
}


@dataclass
class RoutingRule:
    """User-defined routing rule for a specific asset type.

    Attributes:
        asset_type: Asset type this rule applies to.
        preferred_broker: Name of the preferred broker.
        fallback_brokers: Ordered list of fallback brokers.
        criteria: Primary scoring criteria.
    """
    asset_type: str = "stock"
    preferred_broker: str = ""
    fallback_brokers: list[str] = field(default_factory=list)
    criteria: RoutingCriteria = RoutingCriteria.COST

    def to_dict(self) -> dict:
        return {
            "asset_type": self.asset_type,
            "preferred_broker": self.preferred_broker,
            "fallback_brokers": self.fallback_brokers,
            "criteria": self.criteria.value,
        }


@dataclass
class RouteDecision:
    """The result of a routing decision.

    Attributes:
        broker_name: Selected broker for execution.
        reason: Human-readable explanation for the routing choice.
        estimated_fee: Estimated fee for this execution.
        estimated_latency: Estimated latency in milliseconds.
        fallback_chain: Ordered list of fallback brokers if primary fails.
        route_id: Unique identifier for this routing decision.
        timestamp: When the decision was made.
    """
    broker_name: str
    reason: str = ""
    estimated_fee: float = 0.0
    estimated_latency: float = 0.0
    fallback_chain: list[str] = field(default_factory=list)
    route_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "route_id": self.route_id,
            "broker_name": self.broker_name,
            "reason": self.reason,
            "estimated_fee": self.estimated_fee,
            "estimated_latency": self.estimated_latency,
            "fallback_chain": self.fallback_chain,
            "timestamp": self.timestamp.isoformat(),
        }


# =====================================================================
# Order Router
# =====================================================================


class OrderRouter:
    """Intelligent order routing engine.

    Routes orders to the best available broker by:
    1. Matching asset type to connected brokers
    2. Applying user-defined routing rules
    3. Scoring brokers (fee 0.4, speed 0.3, fill_quality 0.3)
    4. Returning the best RouteDecision with fallback chain

    Smart defaults:
        - crypto -> Coinbase
        - stocks -> cheapest (Alpaca default)
        - options -> Schwab
        - fractional shares -> Robinhood

    Example:
        router = OrderRouter(registry)
        router.add_rule(RoutingRule(asset_type="crypto", preferred_broker="coinbase"))
        decision = router.route({"symbol": "BTC-USD", "asset_type": "crypto", "qty": 0.5})
    """

    def __init__(
        self,
        registry: BrokerRegistry,
        weights: Optional[dict[str, float]] = None,
    ) -> None:
        self._registry = registry
        self._weights = weights or dict(DEFAULT_WEIGHTS)
        self._rules: dict[str, RoutingRule] = {}
        self._route_history: list[RouteDecision] = []

    @property
    def rules(self) -> dict[str, RoutingRule]:
        """Active routing rules by asset type."""
        return dict(self._rules)

    @property
    def route_history(self) -> list[RouteDecision]:
        """Recent routing decisions."""
        return list(self._route_history)

    def add_rule(self, rule: RoutingRule) -> None:
        """Add or replace a routing rule for an asset type."""
        self._rules[rule.asset_type] = rule
        logger.info(f"Routing rule set: {rule.asset_type} -> {rule.preferred_broker}")

    def remove_rule(self, asset_type: str) -> bool:
        """Remove a routing rule. Returns True if rule existed."""
        if asset_type in self._rules:
            del self._rules[asset_type]
            return True
        return False

    def route(self, order: dict) -> RouteDecision:
        """Route a single order to the best broker.

        Args:
            order: Dict with keys: symbol, asset_type, side, qty, order_type,
                   and optionally: fractional (bool), limit_price, etc.

        Returns:
            RouteDecision with selected broker, reason, and fallback chain.
        """
        asset_type = order.get("asset_type", "stock")
        symbol = order.get("symbol", "")
        is_fractional = order.get("fractional", False)

        # Step 1: Determine effective asset type
        effective_type = asset_type
        if is_fractional:
            effective_type = "fractional"

        # Step 2: Check user rules first
        rule = self._rules.get(effective_type) or self._rules.get(asset_type)

        if rule and rule.preferred_broker:
            broker_info = self._registry.get(rule.preferred_broker)
            if broker_info and broker_info.status == BrokerStatus.CONNECTED:
                fallbacks = self._build_fallback_chain(asset_type, rule.preferred_broker, rule.fallback_brokers)
                decision = RouteDecision(
                    broker_name=rule.preferred_broker,
                    reason=f"User rule: {asset_type} -> {rule.preferred_broker}",
                    estimated_fee=self._estimate_fee(broker_info, order),
                    estimated_latency=broker_info.latency_ms,
                    fallback_chain=fallbacks,
                )
                self._route_history.append(decision)
                return decision

        # Step 3: Check smart defaults
        smart_broker = SMART_DEFAULTS.get(effective_type) or SMART_DEFAULTS.get(asset_type)
        if smart_broker:
            broker_info = self._registry.get(smart_broker)
            if broker_info and broker_info.status == BrokerStatus.CONNECTED and asset_type in broker_info.supported_assets:
                fallbacks = self._build_fallback_chain(asset_type, smart_broker)
                decision = RouteDecision(
                    broker_name=smart_broker,
                    reason=f"Smart default: {effective_type} -> {smart_broker}",
                    estimated_fee=self._estimate_fee(broker_info, order),
                    estimated_latency=broker_info.latency_ms,
                    fallback_chain=fallbacks,
                )
                self._route_history.append(decision)
                return decision

        # Step 4: Score all connected brokers for this asset type
        candidates = self._registry.get_by_asset(asset_type)
        if not candidates:
            decision = RouteDecision(
                broker_name="",
                reason=f"No connected broker supports asset type '{asset_type}'",
            )
            self._route_history.append(decision)
            return decision

        scored = self._score_brokers(candidates, order)
        best_name, best_score, best_info = scored[0]
        fallbacks = [name for name, _, _ in scored[1:]]

        decision = RouteDecision(
            broker_name=best_name,
            reason=f"Scored best ({best_score:.2f}): cost={self._weights['cost']:.0%}, speed={self._weights['speed']:.0%}, fill={self._weights['fill_quality']:.0%}",
            estimated_fee=self._estimate_fee(best_info, order),
            estimated_latency=best_info.latency_ms,
            fallback_chain=fallbacks,
        )
        self._route_history.append(decision)
        return decision

    def route_batch(self, orders: list[dict]) -> list[RouteDecision]:
        """Route multiple orders.

        Args:
            orders: List of order dicts.

        Returns:
            List of RouteDecision, one per order.
        """
        return [self.route(order) for order in orders]

    # -- Internal Helpers --------------------------------------------------

    def _score_brokers(
        self,
        candidates: list[BrokerInfo],
        order: dict,
    ) -> list[tuple[str, float, BrokerInfo]]:
        """Score candidate brokers and return sorted list (best first).

        Scoring formula:
            score = w_cost * (1 - norm_fee) + w_speed * (1 - norm_latency) + w_fill * fill_score
        """
        if not candidates:
            return []

        # Compute raw metrics
        fees = [self._estimate_fee(b, order) for b in candidates]
        latencies = [b.latency_ms for b in candidates]

        max_fee = max(fees) if max(fees) > 0 else 1.0
        max_latency = max(latencies) if max(latencies) > 0 else 1.0

        scored = []
        for i, broker in enumerate(candidates):
            norm_fee = fees[i] / max_fee if max_fee > 0 else 0.0
            norm_latency = latencies[i] / max_latency if max_latency > 0 else 0.0
            # Fill quality: inversely proportional to priority (lower priority = better)
            fill_score = 1.0 / (1.0 + broker.priority)

            score = (
                self._weights["cost"] * (1.0 - norm_fee)
                + self._weights["speed"] * (1.0 - norm_latency)
                + self._weights["fill_quality"] * fill_score
            )
            scored.append((broker.broker_name, score, broker))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def _estimate_fee(self, broker: BrokerInfo, order: dict) -> float:
        """Estimate the fee for executing an order on a broker."""
        asset_type = order.get("asset_type", "stock")
        qty = float(order.get("qty", 1))
        price = float(order.get("limit_price", order.get("price", 100.0)))
        fees = broker.fee_schedule

        if asset_type == "stock":
            return fees.get("stock_commission", 0.0) + fees.get("base_fee", 0.0)
        elif asset_type == "options":
            return fees.get("options_per_contract", 0.65) * qty + fees.get("base_fee", 0.0)
        elif asset_type == "crypto":
            crypto_pct = fees.get("crypto_fee_pct", fees.get("advanced_fee_pct", 0.40))
            return (crypto_pct / 100.0) * qty * price + fees.get("base_fee", 0.0)
        elif asset_type == "mutual_funds":
            return fees.get("mutual_fund_fee", 0.0) + fees.get("base_fee", 0.0)
        else:
            return fees.get("base_fee", 0.0)

    def _build_fallback_chain(
        self,
        asset_type: str,
        primary: str,
        explicit_fallbacks: Optional[list[str]] = None,
    ) -> list[str]:
        """Build a fallback chain of broker names, excluding the primary."""
        if explicit_fallbacks:
            return [f for f in explicit_fallbacks if f != primary]

        # Auto-build from all connected brokers supporting this asset
        candidates = self._registry.get_by_asset(asset_type)
        return [b.broker_name for b in candidates if b.broker_name != primary]
