"""Market Depth Analysis.

Order book depth measurement, depth resilience scoring,
top-of-book imbalance, and depth decay analysis.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class DepthLevel:
    """Single price level in the order book."""
    price: float = 0.0
    quantity: int = 0
    side: str = ""  # bid, ask
    cumulative_quantity: int = 0
    distance_from_mid_bps: float = 0.0

    @property
    def notional(self) -> float:
        return self.price * self.quantity


@dataclass
class DepthSnapshot:
    """Aggregate depth metrics at a point in time."""
    symbol: str = ""
    mid_price: float = 0.0
    bid_depth_5bps: float = 0.0  # Dollar depth within 5 bps
    ask_depth_5bps: float = 0.0
    bid_depth_10bps: float = 0.0
    ask_depth_10bps: float = 0.0
    bid_depth_25bps: float = 0.0
    ask_depth_25bps: float = 0.0
    total_bid_depth: float = 0.0
    total_ask_depth: float = 0.0
    n_bid_levels: int = 0
    n_ask_levels: int = 0

    @property
    def total_depth(self) -> float:
        return self.total_bid_depth + self.total_ask_depth

    @property
    def depth_imbalance(self) -> float:
        total = self.total_bid_depth + self.total_ask_depth
        if total <= 0:
            return 0.0
        return (self.total_bid_depth - self.total_ask_depth) / total

    @property
    def is_bid_heavy(self) -> bool:
        return self.depth_imbalance > 0.2

    @property
    def is_ask_heavy(self) -> bool:
        return self.depth_imbalance < -0.2


@dataclass
class DepthResilience:
    """How quickly the order book recovers after a large trade."""
    symbol: str = ""
    recovery_time_seconds: float = 0.0
    depth_before: float = 0.0
    depth_after: float = 0.0
    depth_recovery_pct: float = 0.0
    resilience_score: float = 0.0  # 0-100

    @property
    def is_resilient(self) -> bool:
        return self.resilience_score >= 60.0

    @property
    def depth_drop_pct(self) -> float:
        if self.depth_before <= 0:
            return 0.0
        return (self.depth_before - self.depth_after) / self.depth_before


@dataclass
class TopOfBookImbalance:
    """Imbalance at the best bid/ask level."""
    symbol: str = ""
    best_bid_size: int = 0
    best_ask_size: int = 0
    imbalance_ratio: float = 0.0  # -1 to +1
    predicted_direction: str = "neutral"  # up, down, neutral
    signal_strength: float = 0.0  # 0-1

    @property
    def is_strong_signal(self) -> bool:
        return abs(self.imbalance_ratio) > 0.4


@dataclass
class DepthProfile:
    """Summary depth profile for a symbol."""
    symbol: str = ""
    avg_depth_5bps: float = 0.0
    avg_depth_10bps: float = 0.0
    avg_depth_25bps: float = 0.0
    depth_stability: float = 0.0  # 0-1, higher = more stable
    avg_imbalance: float = 0.0
    avg_resilience_score: float = 0.0
    depth_score: float = 0.0  # 0-100 composite

    @property
    def is_deep_market(self) -> bool:
        return self.depth_score >= 70.0


# ---------------------------------------------------------------------------
# Depth Analyzer
# ---------------------------------------------------------------------------
class MarketDepthAnalyzer:
    """Analyzes order book depth, imbalance, and resilience."""

    def __init__(self, mid_price_default: float = 100.0) -> None:
        self.mid_price_default = mid_price_default

    def compute_depth(
        self,
        bids: list[dict],
        asks: list[dict],
        mid_price: float = 0.0,
        symbol: str = "",
    ) -> DepthSnapshot:
        """Compute depth at various distance thresholds.

        Args:
            bids: List of {price, quantity} dicts, descending by price.
            asks: List of {price, quantity} dicts, ascending by price.
            mid_price: Mid-market price.
            symbol: Ticker symbol.

        Returns:
            DepthSnapshot with depth at 5/10/25 bps thresholds.
        """
        if not bids and not asks:
            return DepthSnapshot(symbol=symbol)

        if mid_price <= 0:
            if bids and asks:
                mid_price = (bids[0]["price"] + asks[0]["price"]) / 2
            elif bids:
                mid_price = bids[0]["price"]
            elif asks:
                mid_price = asks[0]["price"]
            else:
                mid_price = self.mid_price_default

        def depth_within(levels: list[dict], threshold_bps: float, is_bid: bool) -> float:
            total = 0.0
            for lvl in levels:
                dist = abs(lvl["price"] - mid_price) / mid_price * 10_000
                if dist <= threshold_bps:
                    total += lvl["price"] * lvl["quantity"]
            return total

        bid_5 = depth_within(bids, 5, True)
        bid_10 = depth_within(bids, 10, True)
        bid_25 = depth_within(bids, 25, True)
        ask_5 = depth_within(asks, 5, False)
        ask_10 = depth_within(asks, 10, False)
        ask_25 = depth_within(asks, 25, False)

        total_bid = sum(b["price"] * b["quantity"] for b in bids)
        total_ask = sum(a["price"] * a["quantity"] for a in asks)

        return DepthSnapshot(
            symbol=symbol,
            mid_price=round(mid_price, 4),
            bid_depth_5bps=round(bid_5, 2),
            ask_depth_5bps=round(ask_5, 2),
            bid_depth_10bps=round(bid_10, 2),
            ask_depth_10bps=round(ask_10, 2),
            bid_depth_25bps=round(bid_25, 2),
            ask_depth_25bps=round(ask_25, 2),
            total_bid_depth=round(total_bid, 2),
            total_ask_depth=round(total_ask, 2),
            n_bid_levels=len(bids),
            n_ask_levels=len(asks),
        )

    def compute_resilience(
        self,
        depth_before: float,
        depth_after: float,
        recovery_depth: float,
        recovery_time_seconds: float = 60.0,
        symbol: str = "",
    ) -> DepthResilience:
        """Measure order book resilience after a large trade.

        Args:
            depth_before: Dollar depth before trade.
            depth_after: Dollar depth immediately after trade.
            recovery_depth: Dollar depth after recovery period.
            recovery_time_seconds: Time for recovery measurement.
            symbol: Ticker symbol.

        Returns:
            DepthResilience with recovery metrics.
        """
        if depth_before <= 0:
            return DepthResilience(symbol=symbol)

        depth_lost = depth_before - depth_after
        depth_recovered = recovery_depth - depth_after

        recovery_pct = (
            depth_recovered / depth_lost if depth_lost > 0 else 1.0
        )
        recovery_pct = max(0.0, min(1.0, recovery_pct))

        # Score: higher recovery in shorter time = better
        time_factor = max(0.1, 1.0 - recovery_time_seconds / 300.0)
        score = recovery_pct * 80 + time_factor * 20

        return DepthResilience(
            symbol=symbol,
            recovery_time_seconds=round(recovery_time_seconds, 1),
            depth_before=round(depth_before, 2),
            depth_after=round(depth_after, 2),
            depth_recovery_pct=round(recovery_pct, 4),
            resilience_score=round(min(100, score), 1),
        )

    def top_of_book_imbalance(
        self,
        best_bid_size: int,
        best_ask_size: int,
        symbol: str = "",
    ) -> TopOfBookImbalance:
        """Compute top-of-book imbalance signal.

        Order imbalance at the best bid/ask predicts short-term
        price direction.

        Args:
            best_bid_size: Size at best bid.
            best_ask_size: Size at best ask.
            symbol: Ticker symbol.

        Returns:
            TopOfBookImbalance with directional signal.
        """
        total = best_bid_size + best_ask_size
        if total == 0:
            return TopOfBookImbalance(symbol=symbol)

        imbalance = (best_bid_size - best_ask_size) / total

        if imbalance > 0.3:
            direction = "up"
        elif imbalance < -0.3:
            direction = "down"
        else:
            direction = "neutral"

        strength = min(1.0, abs(imbalance) / 0.6)

        return TopOfBookImbalance(
            symbol=symbol,
            best_bid_size=best_bid_size,
            best_ask_size=best_ask_size,
            imbalance_ratio=round(imbalance, 4),
            predicted_direction=direction,
            signal_strength=round(strength, 4),
        )

    def depth_profile(
        self,
        snapshots: list[DepthSnapshot],
        resilience_scores: Optional[list[float]] = None,
        symbol: str = "",
    ) -> DepthProfile:
        """Build aggregate depth profile from multiple snapshots.

        Args:
            snapshots: List of DepthSnapshot observations.
            resilience_scores: Optional list of resilience scores.
            symbol: Ticker symbol.

        Returns:
            DepthProfile with composite depth score.
        """
        if not snapshots:
            return DepthProfile(symbol=symbol)

        avg_5 = float(np.mean([
            s.bid_depth_5bps + s.ask_depth_5bps for s in snapshots
        ]))
        avg_10 = float(np.mean([
            s.bid_depth_10bps + s.ask_depth_10bps for s in snapshots
        ]))
        avg_25 = float(np.mean([
            s.bid_depth_25bps + s.ask_depth_25bps for s in snapshots
        ]))

        # Stability: 1 - coefficient of variation of total depth
        depths = [s.total_depth for s in snapshots]
        mean_depth = float(np.mean(depths))
        std_depth = float(np.std(depths))
        stability = max(0.0, min(1.0, 1.0 - (std_depth / mean_depth if mean_depth > 0 else 1.0)))

        avg_imb = float(np.mean([s.depth_imbalance for s in snapshots]))

        avg_res = 0.0
        if resilience_scores:
            avg_res = float(np.mean(resilience_scores))

        # Composite score: depth quantity + stability + resilience
        depth_qty_score = min(50, avg_10 / 50_000)  # Normalized by $50k
        stability_score = stability * 25
        resilience_score_part = avg_res * 0.25 if avg_res > 0 else 12.5

        composite = min(100, depth_qty_score + stability_score + resilience_score_part)

        return DepthProfile(
            symbol=symbol,
            avg_depth_5bps=round(avg_5, 2),
            avg_depth_10bps=round(avg_10, 2),
            avg_depth_25bps=round(avg_25, 2),
            depth_stability=round(stability, 4),
            avg_imbalance=round(avg_imb, 4),
            avg_resilience_score=round(avg_res, 1),
            depth_score=round(composite, 1),
        )
