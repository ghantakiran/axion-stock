"""Slippage tracking and forecasting."""

from datetime import datetime, timezone, timedelta
from typing import Optional
from collections import defaultdict
import math

from src.liquidity.config import OrderSide
from src.liquidity.models import SlippageRecord


class SlippageTracker:
    """Tracks and forecasts execution slippage."""

    def __init__(self):
        # symbol -> list of records
        self._records: dict[str, list[SlippageRecord]] = defaultdict(list)

    def record_slippage(
        self,
        symbol: str,
        side: OrderSide,
        order_size: int,
        expected_price: float,
        executed_price: float,
        market_volume: Optional[int] = None,
        spread_at_entry: Optional[float] = None,
        volatility_at_entry: Optional[float] = None,
    ) -> SlippageRecord:
        """Record an actual slippage event."""
        participation_rate = None
        if market_volume and market_volume > 0:
            participation_rate = order_size / market_volume

        record = SlippageRecord(
            symbol=symbol,
            side=side,
            order_size=order_size,
            expected_price=expected_price,
            executed_price=executed_price,
            market_volume=market_volume,
            participation_rate=participation_rate,
            spread_at_entry=spread_at_entry,
            volatility_at_entry=volatility_at_entry,
        )

        self._records[symbol].append(record)
        return record

    def forecast_slippage(
        self,
        symbol: str,
        order_size: int,
        price: float,
        side: OrderSide,
        avg_daily_volume: int = 0,
    ) -> dict:
        """Forecast slippage based on historical data."""
        history = self._records.get(symbol, [])

        if not history:
            # No history, use a simple model
            participation = order_size / avg_daily_volume if avg_daily_volume > 0 else 0.01
            estimated_bps = math.sqrt(participation) * 10  # Basic sqrt model
            return {
                "symbol": symbol,
                "estimated_slippage_bps": estimated_bps,
                "estimated_cost": abs(estimated_bps / 10_000 * price * order_size),
                "confidence": 0.3,
                "model": "default",
                "sample_size": 0,
            }

        # Filter relevant records (same side, similar size)
        same_side = [r for r in history if r.side == side]
        if not same_side:
            same_side = history

        # Calculate historical slippage statistics
        slippages_bps = [r.slippage_bps for r in same_side]
        avg_slippage = sum(slippages_bps) / len(slippages_bps)

        # Size-adjusted forecast
        avg_size = sum(r.order_size for r in same_side) / len(same_side)
        size_ratio = order_size / avg_size if avg_size > 0 else 1.0

        # Slippage scales with sqrt of size
        estimated_bps = avg_slippage * math.sqrt(size_ratio)

        # Confidence based on sample size and size similarity
        confidence = min(0.9, 0.3 + len(same_side) * 0.02)
        if size_ratio > 3 or size_ratio < 0.3:
            confidence *= 0.7  # Reduce confidence for very different sizes

        return {
            "symbol": symbol,
            "estimated_slippage_bps": estimated_bps,
            "estimated_cost": abs(estimated_bps / 10_000 * price * order_size),
            "confidence": confidence,
            "model": "historical",
            "sample_size": len(same_side),
            "avg_historical_slippage_bps": avg_slippage,
            "size_ratio": size_ratio,
        }

    def get_slippage_history(
        self,
        symbol: str,
        side: Optional[OrderSide] = None,
        limit: int = 100,
    ) -> list[SlippageRecord]:
        """Get slippage history for a symbol."""
        records = self._records.get(symbol, [])
        if side:
            records = [r for r in records if r.side == side]
        return records[-limit:]

    def get_slippage_statistics(
        self,
        symbol: Optional[str] = None,
    ) -> dict:
        """Get slippage statistics."""
        if symbol:
            records = self._records.get(symbol, [])
        else:
            records = [r for recs in self._records.values() for r in recs]

        if not records:
            return {"total_records": 0}

        slippages_bps = [r.slippage_bps for r in records]
        costs = [r.slippage_cost for r in records]

        avg_bps = sum(slippages_bps) / len(slippages_bps)
        variance = sum((s - avg_bps) ** 2 for s in slippages_bps) / len(slippages_bps)

        return {
            "total_records": len(records),
            "avg_slippage_bps": avg_bps,
            "median_slippage_bps": sorted(slippages_bps)[len(slippages_bps) // 2],
            "max_slippage_bps": max(slippages_bps),
            "min_slippage_bps": min(slippages_bps),
            "std_slippage_bps": variance ** 0.5,
            "total_slippage_cost": sum(costs),
            "avg_slippage_cost": sum(costs) / len(costs),
            "positive_slippage_pct": sum(1 for s in slippages_bps if s > 0) / len(slippages_bps),
        }

    def get_cost_attribution(
        self,
        symbol: str,
        spread_cost_bps: float = 5.0,
    ) -> dict:
        """Break down total trading costs."""
        records = self._records.get(symbol, [])
        if not records:
            return {"symbol": symbol, "total_records": 0}

        slippages = [r.slippage_bps for r in records]
        avg_slippage = sum(slippages) / len(slippages)

        # Decompose costs
        spread_component = spread_cost_bps  # Half-spread cost
        impact_component = max(0, avg_slippage - spread_component)
        timing_component = max(0, avg_slippage * 0.1)  # Rough timing cost estimate

        total = spread_component + impact_component + timing_component

        return {
            "symbol": symbol,
            "total_cost_bps": total,
            "spread_cost_bps": spread_component,
            "impact_cost_bps": impact_component,
            "timing_cost_bps": timing_component,
            "spread_pct": spread_component / total * 100 if total > 0 else 0,
            "impact_pct": impact_component / total * 100 if total > 0 else 0,
            "timing_pct": timing_component / total * 100 if total > 0 else 0,
            "sample_size": len(records),
        }

    def get_portfolio_slippage(
        self,
        holdings: dict[str, int],
        prices: dict[str, float],
    ) -> dict:
        """Estimate portfolio-level slippage."""
        results = {}
        total_cost = 0.0
        total_value = 0.0

        for symbol, shares in holdings.items():
            price = prices.get(symbol, 0)
            value = shares * price
            total_value += value

            forecast = self.forecast_slippage(
                symbol=symbol,
                order_size=shares,
                price=price,
                side=OrderSide.SELL,
            )

            results[symbol] = {
                "shares": shares,
                "value": value,
                "estimated_slippage_bps": forecast["estimated_slippage_bps"],
                "estimated_cost": forecast["estimated_cost"],
            }
            total_cost += forecast["estimated_cost"]

        return {
            "portfolio_value": total_value,
            "total_estimated_cost": total_cost,
            "portfolio_slippage_bps": (total_cost / total_value * 10_000) if total_value > 0 else 0,
            "holdings": results,
        }

    def get_stats(self) -> dict:
        """Get tracker statistics."""
        total = sum(len(recs) for recs in self._records.values())
        return {
            "total_records": total,
            "symbols_tracked": len(self._records),
        }
