"""Fill Quality Analysis.

Evaluates order fill quality including effective spread,
price improvement, adverse selection, and fill distribution.
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
class FillMetrics:
    """Fill quality metrics for a single order."""
    symbol: str = ""
    side: str = "buy"
    quantity: float = 0.0
    filled_quantity: float = 0.0
    limit_price: float = 0.0
    fill_price: float = 0.0
    midpoint: float = 0.0
    bid: float = 0.0
    ask: float = 0.0

    # Derived metrics
    fill_rate: float = 0.0
    effective_spread_bps: float = 0.0
    realized_spread_bps: float = 0.0
    price_improvement_bps: float = 0.0
    adverse_selection_bps: float = 0.0

    @property
    def has_price_improvement(self) -> bool:
        return self.price_improvement_bps > 0

    @property
    def effective_spread_pct(self) -> float:
        return self.effective_spread_bps / 10_000

    @property
    def is_fully_filled(self) -> bool:
        return self.fill_rate >= 0.999


@dataclass
class FillDistribution:
    """Distribution of fill quality across trades."""
    n_fills: int = 0
    avg_fill_rate: float = 0.0
    avg_effective_spread_bps: float = 0.0
    avg_price_improvement_bps: float = 0.0
    avg_adverse_selection_bps: float = 0.0
    pct_with_improvement: float = 0.0
    pct_fully_filled: float = 0.0

    # Percentiles of effective spread
    spread_p25_bps: float = 0.0
    spread_p50_bps: float = 0.0
    spread_p75_bps: float = 0.0
    spread_p95_bps: float = 0.0

    @property
    def quality_score(self) -> float:
        """Composite fill quality score (0-100)."""
        fill_component = self.avg_fill_rate * 40
        spread_component = max(0, 30 - self.avg_effective_spread_bps * 0.3)
        improvement_component = self.pct_with_improvement * 30
        return round(min(100, fill_component + spread_component + improvement_component), 1)


@dataclass
class SymbolFillProfile:
    """Fill quality profile for a specific symbol."""
    symbol: str = ""
    n_orders: int = 0
    avg_fill_rate: float = 0.0
    avg_effective_spread_bps: float = 0.0
    avg_price_improvement_bps: float = 0.0
    avg_adverse_selection_bps: float = 0.0
    avg_fill_time_ms: float = 0.0
    quality_score: float = 0.0


# ---------------------------------------------------------------------------
# Fill Quality Analyzer
# ---------------------------------------------------------------------------
class FillQualityAnalyzer:
    """Analyzes order fill quality."""

    def __init__(
        self,
        post_trade_window_ms: float = 5000.0,
    ) -> None:
        self.post_trade_window_ms = post_trade_window_ms

    def analyze_fill(
        self,
        symbol: str,
        side: str,
        quantity: float,
        filled_quantity: float,
        fill_price: float,
        bid: float,
        ask: float,
        post_trade_mid: Optional[float] = None,
        limit_price: float = 0.0,
    ) -> FillMetrics:
        """Analyze fill quality for a single order.

        Args:
            symbol: Ticker symbol.
            side: 'buy' or 'sell'.
            quantity: Original order quantity.
            filled_quantity: Quantity filled.
            fill_price: Average fill price.
            bid: Best bid at time of order.
            ask: Best ask at time of order.
            post_trade_mid: Midpoint after trade (for adverse selection).
            limit_price: Limit price if applicable.

        Returns:
            FillMetrics with quality assessment.
        """
        if bid <= 0 or ask <= 0 or fill_price <= 0:
            return FillMetrics(symbol=symbol, side=side, quantity=quantity)

        midpoint = (bid + ask) / 2
        quoted_spread = ask - bid
        sign = 1 if side == "buy" else -1

        # Fill rate
        fill_rate = filled_quantity / quantity if quantity > 0 else 0.0

        # Effective spread: 2 * |fill_price - midpoint| / midpoint
        effective_spread = 2 * abs(fill_price - midpoint) / midpoint * 10_000

        # Price improvement: how much better than NBBO
        if side == "buy":
            # Improvement = ask - fill_price (positive = buyer got better price)
            improvement = (ask - fill_price) / midpoint * 10_000
        else:
            # Improvement = fill_price - bid (positive = seller got better price)
            improvement = (fill_price - bid) / midpoint * 10_000

        # Adverse selection: post-trade price movement against the fill
        adverse = 0.0
        if post_trade_mid is not None and post_trade_mid > 0:
            adverse = sign * (post_trade_mid - midpoint) / midpoint * 10_000

        # Realized spread = effective spread - adverse selection
        realized = effective_spread - abs(adverse)

        return FillMetrics(
            symbol=symbol,
            side=side,
            quantity=round(quantity, 2),
            filled_quantity=round(filled_quantity, 2),
            limit_price=round(limit_price, 4),
            fill_price=round(fill_price, 4),
            midpoint=round(midpoint, 4),
            bid=round(bid, 4),
            ask=round(ask, 4),
            fill_rate=round(fill_rate, 4),
            effective_spread_bps=round(effective_spread, 2),
            realized_spread_bps=round(realized, 2),
            price_improvement_bps=round(improvement, 2),
            adverse_selection_bps=round(adverse, 2),
        )

    def compute_distribution(
        self,
        fills: list[FillMetrics],
    ) -> FillDistribution:
        """Compute fill quality distribution across trades.

        Args:
            fills: List of individual fill metrics.

        Returns:
            FillDistribution summary.
        """
        if not fills:
            return FillDistribution()

        spreads = [f.effective_spread_bps for f in fills]
        improvements = [f.price_improvement_bps for f in fills]
        adverses = [f.adverse_selection_bps for f in fills]
        fill_rates = [f.fill_rate for f in fills]

        n_improved = sum(1 for f in fills if f.has_price_improvement)
        n_fully_filled = sum(1 for f in fills if f.is_fully_filled)

        spread_arr = np.array(spreads)

        return FillDistribution(
            n_fills=len(fills),
            avg_fill_rate=round(float(np.mean(fill_rates)), 4),
            avg_effective_spread_bps=round(float(np.mean(spreads)), 2),
            avg_price_improvement_bps=round(float(np.mean(improvements)), 2),
            avg_adverse_selection_bps=round(float(np.mean(adverses)), 2),
            pct_with_improvement=round(n_improved / len(fills), 4),
            pct_fully_filled=round(n_fully_filled / len(fills), 4),
            spread_p25_bps=round(float(np.percentile(spread_arr, 25)), 2),
            spread_p50_bps=round(float(np.percentile(spread_arr, 50)), 2),
            spread_p75_bps=round(float(np.percentile(spread_arr, 75)), 2),
            spread_p95_bps=round(float(np.percentile(spread_arr, 95)), 2),
        )

    def profile_by_symbol(
        self,
        fills: list[FillMetrics],
    ) -> list[SymbolFillProfile]:
        """Group fill quality by symbol.

        Args:
            fills: List of individual fill metrics.

        Returns:
            List of SymbolFillProfile sorted by quality score.
        """
        if not fills:
            return []

        by_symbol: dict[str, list[FillMetrics]] = {}
        for f in fills:
            by_symbol.setdefault(f.symbol, []).append(f)

        profiles = []
        for symbol, symbol_fills in by_symbol.items():
            dist = self.compute_distribution(symbol_fills)
            profiles.append(SymbolFillProfile(
                symbol=symbol,
                n_orders=len(symbol_fills),
                avg_fill_rate=dist.avg_fill_rate,
                avg_effective_spread_bps=dist.avg_effective_spread_bps,
                avg_price_improvement_bps=dist.avg_price_improvement_bps,
                avg_adverse_selection_bps=dist.avg_adverse_selection_bps,
                quality_score=dist.quality_score,
            ))

        profiles.sort(key=lambda p: p.quality_score, reverse=True)
        return profiles
