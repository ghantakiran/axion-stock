"""Liquidity-Adjusted Value-at-Risk (LaVaR).

Computes standard VaR, adds liquidity cost components (bid-ask spread
and market impact), applies holding-period adjustment, and decomposes
LaVaR by position.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class VaRResult:
    """Standard VaR result."""
    confidence: float = 0.95
    horizon_days: int = 1
    portfolio_value: float = 0.0
    var_pct: float = 0.0
    var_dollar: float = 0.0
    method: str = "historical"

    @property
    def var_bps(self) -> float:
        return round(self.var_pct * 10000, 2)


@dataclass
class LiquidityCost:
    """Liquidity cost component."""
    spread_cost_pct: float = 0.0
    impact_cost_pct: float = 0.0
    total_cost_pct: float = 0.0

    @property
    def total_bps(self) -> float:
        return round(self.total_cost_pct * 10000, 2)


@dataclass
class PositionLaVaR:
    """Per-position LaVaR decomposition."""
    symbol: str = ""
    weight: float = 0.0
    position_value: float = 0.0
    var_contribution_pct: float = 0.0
    liquidity_cost_pct: float = 0.0
    lavar_pct: float = 0.0
    lavar_dollar: float = 0.0
    days_to_liquidate: float = 0.0


@dataclass
class LaVaR:
    """Liquidity-adjusted VaR result."""
    confidence: float = 0.95
    horizon_days: int = 1
    portfolio_value: float = 0.0
    var_pct: float = 0.0
    var_dollar: float = 0.0
    liquidity_cost_pct: float = 0.0
    liquidity_cost_dollar: float = 0.0
    lavar_pct: float = 0.0
    lavar_dollar: float = 0.0
    method: str = "historical"
    positions: list[PositionLaVaR] = field(default_factory=list)

    @property
    def liquidity_share(self) -> float:
        """Fraction of LaVaR attributable to liquidity cost."""
        return self.liquidity_cost_pct / self.lavar_pct if self.lavar_pct > 0 else 0.0

    @property
    def lavar_bps(self) -> float:
        return round(self.lavar_pct * 10000, 2)


class LaVaRCalculator:
    """Computes Liquidity-Adjusted Value-at-Risk.

    LaVaR = VaR + Liquidity Cost, where:
    - VaR: standard parametric or historical VaR
    - Liquidity Cost: half-spread + market impact, holding-period adjusted
    """

    def __init__(
        self,
        max_participation: float = 0.10,
        impact_coefficient: float = 0.10,
    ) -> None:
        self.max_participation = max_participation
        self.impact_coefficient = impact_coefficient

    def historical_var(
        self,
        returns: list[float],
        portfolio_value: float,
        confidence: float = 0.95,
        horizon_days: int = 1,
    ) -> VaRResult:
        """Compute historical VaR.

        Args:
            returns: Historical portfolio returns (daily).
            portfolio_value: Current portfolio value.
            confidence: Confidence level (e.g. 0.95, 0.99).
            horizon_days: Holding period in days.

        Returns:
            VaRResult.
        """
        if not returns or len(returns) < 2:
            return VaRResult(
                confidence=confidence,
                horizon_days=horizon_days,
                portfolio_value=portfolio_value,
            )

        arr = np.array(returns)
        quantile = np.percentile(arr, (1 - confidence) * 100)
        # Scale by sqrt-T for multi-day horizon
        var_pct = abs(quantile) * np.sqrt(horizon_days)
        var_dollar = var_pct * portfolio_value

        return VaRResult(
            confidence=confidence,
            horizon_days=horizon_days,
            portfolio_value=portfolio_value,
            var_pct=round(var_pct, 6),
            var_dollar=round(var_dollar, 2),
            method="historical",
        )

    def parametric_var(
        self,
        returns: list[float],
        portfolio_value: float,
        confidence: float = 0.95,
        horizon_days: int = 1,
    ) -> VaRResult:
        """Compute parametric (Gaussian) VaR.

        Args:
            returns: Historical portfolio returns (daily).
            portfolio_value: Current portfolio value.
            confidence: Confidence level.
            horizon_days: Holding period in days.

        Returns:
            VaRResult.
        """
        if not returns or len(returns) < 2:
            return VaRResult(
                confidence=confidence,
                horizon_days=horizon_days,
                portfolio_value=portfolio_value,
                method="parametric",
            )

        arr = np.array(returns)
        mu = np.mean(arr)
        sigma = np.std(arr, ddof=1)
        z = stats.norm.ppf(1 - confidence)  # negative
        var_pct = abs(mu + z * sigma) * np.sqrt(horizon_days)
        var_dollar = var_pct * portfolio_value

        return VaRResult(
            confidence=confidence,
            horizon_days=horizon_days,
            portfolio_value=portfolio_value,
            var_pct=round(var_pct, 6),
            var_dollar=round(var_dollar, 2),
            method="parametric",
        )

    def compute_liquidity_cost(
        self,
        positions: list[dict],
        portfolio_value: float,
        horizon_days: int = 1,
    ) -> LiquidityCost:
        """Compute portfolio-level liquidity cost.

        Each position dict: {symbol, value, adv_usd, spread_bps}.

        Args:
            positions: List of position dicts.
            portfolio_value: Total portfolio value.
            horizon_days: Holding period for impact scaling.

        Returns:
            LiquidityCost.
        """
        if not positions or portfolio_value <= 0:
            return LiquidityCost()

        total_spread_cost = 0.0
        total_impact_cost = 0.0

        for pos in positions:
            value = pos.get("value", 0.0)
            adv = pos.get("adv_usd", 0.0)
            spread_bps = pos.get("spread_bps", 5.0)
            weight = value / portfolio_value if portfolio_value > 0 else 0.0

            # Half-spread cost (one-way)
            spread_cost = (spread_bps / 10000) * 0.5
            total_spread_cost += weight * spread_cost

            # Market impact: coefficient * sqrt(value / (adv * horizon))
            if adv > 0:
                participation = value / (adv * max(horizon_days, 1))
                impact = self.impact_coefficient * np.sqrt(participation)
            else:
                impact = 0.01  # 1% default for zero-ADV
            total_impact_cost += weight * impact

        # Scale by sqrt(horizon) for multi-day
        scale = np.sqrt(horizon_days)
        total_spread_cost *= scale
        total_impact_cost *= scale
        total = total_spread_cost + total_impact_cost

        return LiquidityCost(
            spread_cost_pct=round(total_spread_cost, 6),
            impact_cost_pct=round(total_impact_cost, 6),
            total_cost_pct=round(total, 6),
        )

    def compute_lavar(
        self,
        returns: list[float],
        positions: list[dict],
        portfolio_value: float,
        confidence: float = 0.95,
        horizon_days: int = 1,
        method: str = "historical",
    ) -> LaVaR:
        """Compute Liquidity-Adjusted VaR.

        LaVaR = VaR + Liquidity Cost.

        Args:
            returns: Historical portfolio returns.
            positions: List of {symbol, value, adv_usd, spread_bps}.
            portfolio_value: Total portfolio value.
            confidence: Confidence level.
            horizon_days: Holding period.
            method: "historical" or "parametric".

        Returns:
            LaVaR result.
        """
        # Standard VaR
        if method == "parametric":
            var_result = self.parametric_var(returns, portfolio_value, confidence, horizon_days)
        else:
            var_result = self.historical_var(returns, portfolio_value, confidence, horizon_days)

        # Liquidity cost
        liq_cost = self.compute_liquidity_cost(positions, portfolio_value, horizon_days)

        # LaVaR = VaR + liquidity cost
        lavar_pct = var_result.var_pct + liq_cost.total_cost_pct
        lavar_dollar = lavar_pct * portfolio_value

        # Position-level decomposition
        pos_lavars = self._decompose_positions(
            positions, portfolio_value, var_result.var_pct, horizon_days
        )

        return LaVaR(
            confidence=confidence,
            horizon_days=horizon_days,
            portfolio_value=portfolio_value,
            var_pct=var_result.var_pct,
            var_dollar=var_result.var_dollar,
            liquidity_cost_pct=liq_cost.total_cost_pct,
            liquidity_cost_dollar=round(liq_cost.total_cost_pct * portfolio_value, 2),
            lavar_pct=round(lavar_pct, 6),
            lavar_dollar=round(lavar_dollar, 2),
            method=method,
            positions=pos_lavars,
        )

    def _decompose_positions(
        self,
        positions: list[dict],
        portfolio_value: float,
        var_pct: float,
        horizon_days: int,
    ) -> list[PositionLaVaR]:
        """Decompose LaVaR by position.

        Each position's contribution = weight * var_pct + position liquidity cost.
        """
        results = []

        for pos in positions:
            value = pos.get("value", 0.0)
            adv = pos.get("adv_usd", 0.0)
            spread_bps = pos.get("spread_bps", 5.0)
            weight = value / portfolio_value if portfolio_value > 0 else 0.0

            # VaR contribution (proportional to weight)
            var_contrib = weight * var_pct

            # Position liquidity cost
            spread_cost = (spread_bps / 10000) * 0.5
            if adv > 0:
                participation = value / (adv * max(horizon_days, 1))
                impact = self.impact_coefficient * np.sqrt(participation)
            else:
                impact = 0.01

            liq_cost = (spread_cost + impact) * np.sqrt(horizon_days)
            pos_lavar_pct = var_contrib + weight * liq_cost

            # Days to liquidate
            max_daily = adv * self.max_participation if adv > 0 else 0.0
            dtl = value / max_daily if max_daily > 0 else 999.0

            results.append(PositionLaVaR(
                symbol=pos.get("symbol", ""),
                weight=round(weight, 4),
                position_value=value,
                var_contribution_pct=round(var_contrib, 6),
                liquidity_cost_pct=round(weight * liq_cost, 6),
                lavar_pct=round(pos_lavar_pct, 6),
                lavar_dollar=round(pos_lavar_pct * portfolio_value, 2),
                days_to_liquidate=round(dtl, 1),
            ))

        # Sort by LaVaR contribution descending
        results.sort(key=lambda x: x.lavar_pct, reverse=True)
        return results
