"""Factor Shock Propagation.

Models how shocks to macro factors cascade through a portfolio
via factor exposures and cross-factor correlations.
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
class FactorShock:
    """A shock to a single factor."""
    factor: str = ""
    shock_magnitude: float = 0.0  # e.g., -0.10 for 10% decline
    confidence: float = 0.5  # Confidence in the shock estimate

    @property
    def is_negative(self) -> bool:
        return self.shock_magnitude < 0

    @property
    def severity(self) -> str:
        mag = abs(self.shock_magnitude)
        if mag > 0.20:
            return "severe"
        elif mag > 0.10:
            return "moderate"
        elif mag > 0.05:
            return "mild"
        return "minimal"


@dataclass
class PropagatedShock:
    """Result of shock propagation to a position."""
    symbol: str = ""
    direct_impact: float = 0.0  # From direct factor exposure
    indirect_impact: float = 0.0  # From correlated factors
    total_impact: float = 0.0
    contributing_factors: dict = field(default_factory=dict)  # factor -> impact

    @property
    def amplification_ratio(self) -> float:
        """How much indirect effects amplified the shock."""
        if abs(self.direct_impact) < 0.0001:
            return 1.0
        return abs(self.total_impact) / abs(self.direct_impact)


@dataclass
class PortfolioShockResult:
    """Aggregated shock propagation result for portfolio."""
    total_impact_pct: float = 0.0
    total_impact_usd: float = 0.0
    position_impacts: list[PropagatedShock] = field(default_factory=list)
    factor_contributions: dict = field(default_factory=dict)
    amplification_factor: float = 1.0
    worst_position: str = ""
    worst_impact: float = 0.0

    @property
    def n_positions_affected(self) -> int:
        return sum(1 for p in self.position_impacts if abs(p.total_impact) > 0.001)

    @property
    def is_systemic(self) -> bool:
        """Shock affects > 80% of positions."""
        if not self.position_impacts:
            return False
        return self.n_positions_affected / len(self.position_impacts) > 0.8


@dataclass
class ContagionPath:
    """Path of shock propagation between factors."""
    source_factor: str = ""
    target_factor: str = ""
    correlation: float = 0.0
    transmitted_shock: float = 0.0

    @property
    def transmission_efficiency(self) -> float:
        return abs(self.correlation)


# ---------------------------------------------------------------------------
# Default factor correlations (can be overridden)
# ---------------------------------------------------------------------------
DEFAULT_FACTOR_CORRELATIONS = {
    ("market", "growth"): 0.6,
    ("market", "value"): 0.4,
    ("market", "momentum"): 0.3,
    ("market", "quality"): 0.2,
    ("market", "size"): 0.5,
    ("market", "volatility"): -0.7,
    ("growth", "value"): -0.4,
    ("growth", "momentum"): 0.5,
    ("growth", "quality"): 0.3,
    ("value", "quality"): 0.2,
    ("momentum", "volatility"): -0.3,
    ("quality", "volatility"): -0.4,
    ("size", "value"): 0.3,
    ("size", "momentum"): -0.2,
    ("interest_rate", "growth"): -0.5,
    ("interest_rate", "value"): 0.3,
    ("interest_rate", "real_estate"): -0.6,
    ("credit_spread", "market"): -0.5,
    ("credit_spread", "quality"): -0.4,
    ("oil", "energy"): 0.8,
    ("oil", "consumer"): -0.3,
    ("dollar", "emerging"): -0.5,
    ("dollar", "commodities"): -0.4,
}


# ---------------------------------------------------------------------------
# Shock Propagation Engine
# ---------------------------------------------------------------------------
class ShockPropagationEngine:
    """Models how factor shocks cascade through a portfolio.

    Uses factor exposures and cross-factor correlations to
    estimate total impact including second-order effects.
    """

    def __init__(
        self,
        factor_correlations: Optional[dict] = None,
        correlation_decay: float = 0.5,
    ) -> None:
        self.factor_correlations = factor_correlations or dict(DEFAULT_FACTOR_CORRELATIONS)
        self.correlation_decay = correlation_decay
        self._build_correlation_matrix()

    def _build_correlation_matrix(self) -> None:
        """Build symmetric correlation lookup."""
        self._corr_lookup: dict[tuple[str, str], float] = {}
        for (f1, f2), corr in self.factor_correlations.items():
            self._corr_lookup[(f1, f2)] = corr
            self._corr_lookup[(f2, f1)] = corr

    def get_correlation(self, factor1: str, factor2: str) -> float:
        """Get correlation between two factors."""
        if factor1 == factor2:
            return 1.0
        return self._corr_lookup.get((factor1, factor2), 0.0)

    def propagate_shock(
        self,
        initial_shocks: list[FactorShock],
        position_exposures: dict[str, dict[str, float]],
        position_values: dict[str, float],
        portfolio_value: float,
        max_hops: int = 2,
    ) -> PortfolioShockResult:
        """Propagate factor shocks through portfolio.

        Args:
            initial_shocks: List of factor shocks.
            position_exposures: {symbol: {factor: exposure}}.
            position_values: {symbol: market_value}.
            portfolio_value: Total portfolio value.
            max_hops: Maximum propagation hops.

        Returns:
            PortfolioShockResult with total impact.
        """
        # Build factor shock map including propagated shocks
        factor_shocks = {s.factor: s.shock_magnitude for s in initial_shocks}

        # Propagate shocks through correlations
        propagated = dict(factor_shocks)
        for hop in range(max_hops):
            decay = self.correlation_decay ** (hop + 1)
            new_shocks: dict[str, float] = {}

            for source_factor, shock in factor_shocks.items():
                for (f1, f2), corr in self.factor_correlations.items():
                    if f1 == source_factor and f2 not in propagated:
                        transmitted = shock * corr * decay
                        if f2 in new_shocks:
                            new_shocks[f2] += transmitted
                        else:
                            new_shocks[f2] = transmitted
                    elif f2 == source_factor and f1 not in propagated:
                        transmitted = shock * corr * decay
                        if f1 in new_shocks:
                            new_shocks[f1] += transmitted
                        else:
                            new_shocks[f1] = transmitted

            for f, s in new_shocks.items():
                if f not in propagated:
                    propagated[f] = s

        # Calculate position impacts
        position_impacts = []
        total_impact = 0.0
        factor_contributions: dict[str, float] = {}

        for symbol, exposures in position_exposures.items():
            pos_value = position_values.get(symbol, 0.0)
            weight = pos_value / portfolio_value if portfolio_value > 0 else 0.0

            direct = 0.0
            indirect = 0.0
            contrib: dict[str, float] = {}

            for factor, exposure in exposures.items():
                if factor in factor_shocks:
                    impact = factor_shocks[factor] * exposure
                    direct += impact
                    contrib[factor] = impact
                elif factor in propagated:
                    impact = propagated[factor] * exposure
                    indirect += impact
                    contrib[factor] = impact

            total_pos = direct + indirect
            position_impacts.append(PropagatedShock(
                symbol=symbol,
                direct_impact=round(direct, 6),
                indirect_impact=round(indirect, 6),
                total_impact=round(total_pos, 6),
                contributing_factors=contrib,
            ))

            total_impact += weight * total_pos

            # Aggregate factor contributions
            for f, c in contrib.items():
                if f not in factor_contributions:
                    factor_contributions[f] = 0.0
                factor_contributions[f] += weight * c

        # Find worst position
        worst = min(position_impacts, key=lambda p: p.total_impact) if position_impacts else None

        # Amplification: total vs sum of direct
        direct_sum = sum(
            p.direct_impact * (position_values.get(p.symbol, 0) / portfolio_value)
            for p in position_impacts
        ) if portfolio_value > 0 else 0.0
        amplification = abs(total_impact) / abs(direct_sum) if abs(direct_sum) > 0.0001 else 1.0

        return PortfolioShockResult(
            total_impact_pct=round(total_impact, 6),
            total_impact_usd=round(total_impact * portfolio_value, 2),
            position_impacts=position_impacts,
            factor_contributions={k: round(v, 6) for k, v in factor_contributions.items()},
            amplification_factor=round(amplification, 4),
            worst_position=worst.symbol if worst else "",
            worst_impact=worst.total_impact if worst else 0.0,
        )

    def trace_contagion(
        self,
        source_factor: str,
        shock_magnitude: float,
        max_hops: int = 3,
    ) -> list[ContagionPath]:
        """Trace how a shock spreads through factor network.

        Args:
            source_factor: Initial shocked factor.
            shock_magnitude: Size of initial shock.
            max_hops: Maximum propagation depth.

        Returns:
            List of ContagionPath showing transmission.
        """
        paths = []
        visited = {source_factor}
        current_level = [(source_factor, shock_magnitude)]

        for hop in range(max_hops):
            decay = self.correlation_decay ** (hop + 1)
            next_level = []

            for factor, shock in current_level:
                for (f1, f2), corr in self.factor_correlations.items():
                    target = None
                    if f1 == factor and f2 not in visited:
                        target = f2
                    elif f2 == factor and f1 not in visited:
                        target = f1

                    if target:
                        transmitted = shock * corr * decay
                        paths.append(ContagionPath(
                            source_factor=factor,
                            target_factor=target,
                            correlation=corr,
                            transmitted_shock=round(transmitted, 6),
                        ))
                        visited.add(target)
                        next_level.append((target, transmitted))

            current_level = next_level
            if not current_level:
                break

        return paths

    def sensitivity_analysis(
        self,
        position_exposures: dict[str, dict[str, float]],
        position_values: dict[str, float],
        portfolio_value: float,
        shock_range: tuple[float, float] = (-0.20, 0.20),
        n_points: int = 5,
    ) -> dict:
        """Analyze portfolio sensitivity to factor shocks.

        Args:
            position_exposures: {symbol: {factor: exposure}}.
            position_values: {symbol: market_value}.
            portfolio_value: Total portfolio value.
            shock_range: Range of shocks to test.
            n_points: Number of shock levels to test.

        Returns:
            Dict with sensitivity by factor.
        """
        # Find all factors
        factors = set()
        for exposures in position_exposures.values():
            factors.update(exposures.keys())

        shocks = np.linspace(shock_range[0], shock_range[1], n_points)
        sensitivities: dict[str, list[tuple[float, float]]] = {}

        for factor in factors:
            sensitivities[factor] = []
            for shock_mag in shocks:
                result = self.propagate_shock(
                    [FactorShock(factor=factor, shock_magnitude=shock_mag)],
                    position_exposures,
                    position_values,
                    portfolio_value,
                )
                sensitivities[factor].append((
                    round(shock_mag, 4),
                    round(result.total_impact_pct, 6),
                ))

        # Rank by sensitivity (slope)
        factor_betas = {}
        for factor, points in sensitivities.items():
            if len(points) >= 2:
                x = [p[0] for p in points]
                y = [p[1] for p in points]
                beta = (y[-1] - y[0]) / (x[-1] - x[0]) if x[-1] != x[0] else 0.0
                factor_betas[factor] = round(beta, 4)

        return {
            "sensitivities": sensitivities,
            "factor_betas": factor_betas,
            "most_sensitive": max(factor_betas, key=lambda f: abs(factor_betas[f])) if factor_betas else "",
            "least_sensitive": min(factor_betas, key=lambda f: abs(factor_betas[f])) if factor_betas else "",
        }
