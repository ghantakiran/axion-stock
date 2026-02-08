"""Market impact estimation."""

from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict
import math

from src.liquidity.config import (
    ImpactModel,
    OrderSide,
    LiquidityTier,
    IMPACT_COEFFICIENTS,
    LiquidityConfig,
    DEFAULT_LIQUIDITY_CONFIG,
)
from src.liquidity.models import MarketImpactEstimate


class ImpactEstimator:
    """Estimates market impact for orders."""

    def __init__(self, config: LiquidityConfig = DEFAULT_LIQUIDITY_CONFIG):
        self.config = config
        # symbol -> list of estimates
        self._estimates: dict[str, list[MarketImpactEstimate]] = defaultdict(list)

    def estimate_impact(
        self,
        symbol: str,
        order_size_shares: int,
        price: float,
        side: OrderSide,
        avg_daily_volume: int,
        volatility: float = 0.02,
        liquidity_tier: LiquidityTier = LiquidityTier.LIQUID,
        model: Optional[ImpactModel] = None,
    ) -> MarketImpactEstimate:
        """Estimate market impact for an order."""
        model = model or self.config.default_impact_model
        order_value = order_size_shares * price

        # Calculate participation rate
        participation_rate = order_size_shares / avg_daily_volume if avg_daily_volume > 0 else 1.0

        # Get impact coefficients
        coeffs = IMPACT_COEFFICIENTS.get(
            liquidity_tier.value,
            IMPACT_COEFFICIENTS[LiquidityTier.LIQUID.value]
        )

        # Calculate impact based on model
        if model == ImpactModel.LINEAR:
            impact_bps = self._linear_impact(participation_rate, volatility, coeffs)
        elif model == ImpactModel.SQUARE_ROOT:
            impact_bps = self._sqrt_impact(participation_rate, volatility, coeffs)
        elif model == ImpactModel.POWER_LAW:
            impact_bps = self._power_law_impact(participation_rate, volatility, coeffs)
        else:
            impact_bps = self._sqrt_impact(participation_rate, volatility, coeffs)

        # Decompose into temporary and permanent
        temp_impact = impact_bps * (1 - coeffs["perm_fraction"])
        perm_impact = impact_bps * coeffs["perm_fraction"]

        # Estimated cost
        estimated_cost = order_value * impact_bps / 10_000

        # Confidence based on data quality
        confidence = min(0.9, 0.5 + (1 - participation_rate) * 0.4)

        estimate = MarketImpactEstimate(
            symbol=symbol,
            order_size_shares=order_size_shares,
            order_size_value=order_value,
            side=side,
            estimated_impact_bps=impact_bps,
            temporary_impact_bps=temp_impact,
            permanent_impact_bps=perm_impact,
            estimated_cost=estimated_cost,
            participation_rate=participation_rate,
            model_used=model,
            model_params={
                "volatility": volatility,
                "coefficients": coeffs,
            },
            confidence=confidence,
        )

        self._estimates[symbol].append(estimate)
        return estimate

    def _linear_impact(
        self,
        participation_rate: float,
        volatility: float,
        coeffs: dict,
    ) -> float:
        """Linear market impact model."""
        return coeffs["linear_coeff"] * participation_rate * volatility * 10_000

    def _sqrt_impact(
        self,
        participation_rate: float,
        volatility: float,
        coeffs: dict,
    ) -> float:
        """Square-root market impact model (most common)."""
        return coeffs["sqrt_coeff"] * math.sqrt(participation_rate) * volatility * 10_000

    def _power_law_impact(
        self,
        participation_rate: float,
        volatility: float,
        coeffs: dict,
        exponent: float = 0.6,
    ) -> float:
        """Power-law market impact model."""
        return coeffs["sqrt_coeff"] * (participation_rate ** exponent) * volatility * 10_000

    def estimate_optimal_execution(
        self,
        symbol: str,
        total_shares: int,
        price: float,
        avg_daily_volume: int,
        volatility: float = 0.02,
        liquidity_tier: LiquidityTier = LiquidityTier.LIQUID,
        max_slices: int = 10,
    ) -> dict:
        """Estimate optimal execution strategy to minimize impact."""
        # Try different slice counts
        strategies = []

        for n_slices in range(1, max_slices + 1):
            slice_size = total_shares // n_slices
            if slice_size == 0:
                break

            total_impact_bps = 0
            for i in range(n_slices):
                estimate = self.estimate_impact(
                    symbol=symbol,
                    order_size_shares=slice_size,
                    price=price,
                    side=OrderSide.BUY,
                    avg_daily_volume=avg_daily_volume,
                    volatility=volatility,
                    liquidity_tier=liquidity_tier,
                )
                # Each subsequent slice has slightly more impact due to information leakage
                total_impact_bps += estimate.estimated_impact_bps * (1 + 0.05 * i)

            avg_impact = total_impact_bps / n_slices
            total_cost = total_shares * price * total_impact_bps / 10_000

            strategies.append({
                "slices": n_slices,
                "shares_per_slice": slice_size,
                "avg_impact_bps": avg_impact,
                "total_impact_bps": total_impact_bps,
                "total_cost": total_cost,
                "participation_rate": slice_size / avg_daily_volume if avg_daily_volume > 0 else 1.0,
            })

        # Find optimal (minimize total cost)
        if strategies:
            optimal = min(strategies, key=lambda s: s["total_cost"])
        else:
            optimal = strategies[0] if strategies else {}

        return {
            "symbol": symbol,
            "total_shares": total_shares,
            "total_value": total_shares * price,
            "optimal_strategy": optimal,
            "all_strategies": strategies,
        }

    def get_estimate_history(
        self,
        symbol: str,
        limit: int = 50,
    ) -> list[MarketImpactEstimate]:
        """Get estimate history for a symbol."""
        return self._estimates.get(symbol, [])[-limit:]

    def get_stats(self) -> dict:
        """Get estimator statistics."""
        total = sum(len(ests) for ests in self._estimates.values())
        all_impacts = [
            e.estimated_impact_bps
            for ests in self._estimates.values()
            for e in ests
        ]

        return {
            "total_estimates": total,
            "symbols_estimated": len(self._estimates),
            "avg_impact_bps": sum(all_impacts) / len(all_impacts) if all_impacts else 0,
            "max_impact_bps": max(all_impacts) if all_impacts else 0,
        }
