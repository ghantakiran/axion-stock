"""Performance Attribution Analysis.

Implements:
- Brinson Attribution (allocation, selection, interaction effects)
- Factor Attribution (market, value, momentum, quality, growth)
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BrinsonAttribution:
    """Brinson-style performance attribution results."""

    total_return: float = 0.0
    benchmark_return: float = 0.0
    active_return: float = 0.0

    # Attribution components
    allocation_effect: float = 0.0  # Return from sector weight decisions
    selection_effect: float = 0.0  # Return from stock picking
    interaction_effect: float = 0.0  # Combined effect

    # Sector-level attribution
    sector_attribution: dict[str, dict] = field(default_factory=dict)
    # {sector: {allocation, selection, interaction, total}}


@dataclass
class FactorAttribution:
    """Factor-based performance attribution results."""

    total_return: float = 0.0

    # Factor contributions
    market_contribution: float = 0.0  # Beta
    value_contribution: float = 0.0
    momentum_contribution: float = 0.0
    quality_contribution: float = 0.0
    growth_contribution: float = 0.0
    volatility_contribution: float = 0.0
    technical_contribution: float = 0.0

    # Residual (alpha)
    residual: float = 0.0

    # Factor exposures (betas to each factor)
    factor_exposures: dict[str, float] = field(default_factory=dict)

    # Factor returns during period
    factor_returns: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for display."""
        contributions = {
            "Market (Beta)": self.market_contribution,
            "Value": self.value_contribution,
            "Momentum": self.momentum_contribution,
            "Quality": self.quality_contribution,
            "Growth": self.growth_contribution,
            "Residual (Alpha)": self.residual,
        }

        total = sum(contributions.values())

        return {
            "total_return": self.total_return,
            "contributions": contributions,
            "contribution_pct": {
                k: v / total * 100 if total != 0 else 0
                for k, v in contributions.items()
            },
        }


class AttributionAnalyzer:
    """Analyze portfolio performance attribution.

    Example:
        analyzer = AttributionAnalyzer()

        # Brinson attribution
        brinson = analyzer.brinson_attribution(
            portfolio_weights=port_weights,
            benchmark_weights=bench_weights,
            portfolio_returns=port_returns,
            benchmark_returns=bench_returns,
        )

        # Factor attribution
        factor_attr = analyzer.factor_attribution(
            portfolio_return=0.12,
            factor_exposures=exposures,
            factor_returns=factor_ret,
        )
    """

    # Standard factor names
    FACTORS = ["market", "value", "momentum", "quality", "growth", "volatility", "technical"]

    def __init__(self):
        """Initialize analyzer."""
        pass

    # =========================================================================
    # Brinson Attribution
    # =========================================================================

    def brinson_attribution(
        self,
        portfolio_weights: dict[str, float],  # {sector: weight}
        benchmark_weights: dict[str, float],  # {sector: weight}
        portfolio_returns: dict[str, float],  # {sector: return}
        benchmark_returns: dict[str, float],  # {sector: return}
    ) -> BrinsonAttribution:
        """Calculate Brinson attribution by sector.

        Decomposes active return into:
        - Allocation Effect: value added from being over/underweight sectors
        - Selection Effect: value added from stock selection within sectors
        - Interaction Effect: combined effect

        Args:
            portfolio_weights: Portfolio sector weights.
            benchmark_weights: Benchmark sector weights.
            portfolio_returns: Portfolio returns by sector.
            benchmark_returns: Benchmark returns by sector.

        Returns:
            BrinsonAttribution with all attribution components.
        """
        result = BrinsonAttribution()

        # Get all sectors
        all_sectors = set(portfolio_weights.keys()) | set(benchmark_weights.keys())

        total_allocation = 0.0
        total_selection = 0.0
        total_interaction = 0.0
        portfolio_total = 0.0
        benchmark_total = 0.0

        sector_attr = {}

        for sector in all_sectors:
            wp = portfolio_weights.get(sector, 0)  # Portfolio weight
            wb = benchmark_weights.get(sector, 0)  # Benchmark weight
            rp = portfolio_returns.get(sector, 0)  # Portfolio return in sector
            rb = benchmark_returns.get(sector, 0)  # Benchmark return in sector

            # Calculate total returns
            portfolio_total += wp * rp
            benchmark_total += wb * rb

            # Allocation effect: (Wp - Wb) * (Rb - RB_total)
            # Being overweight in sectors that outperform the benchmark
            allocation = (wp - wb) * rb

            # Selection effect: Wb * (Rp - Rb)
            # Picking better stocks within each sector
            selection = wb * (rp - rb)

            # Interaction effect: (Wp - Wb) * (Rp - Rb)
            # Combined effect of both decisions
            interaction = (wp - wb) * (rp - rb)

            total_allocation += allocation
            total_selection += selection
            total_interaction += interaction

            sector_attr[sector] = {
                "allocation": allocation,
                "selection": selection,
                "interaction": interaction,
                "total": allocation + selection + interaction,
                "portfolio_weight": wp,
                "benchmark_weight": wb,
                "portfolio_return": rp,
                "benchmark_return": rb,
            }

        result.total_return = portfolio_total
        result.benchmark_return = benchmark_total
        result.active_return = portfolio_total - benchmark_total
        result.allocation_effect = total_allocation
        result.selection_effect = total_selection
        result.interaction_effect = total_interaction
        result.sector_attribution = sector_attr

        return result

    def brinson_attribution_from_positions(
        self,
        positions: list[dict],  # [{symbol, weight, return, sector}]
        benchmark_positions: list[dict],  # Same format
    ) -> BrinsonAttribution:
        """Calculate Brinson attribution from position-level data.

        Aggregates positions to sectors and then calculates attribution.

        Args:
            positions: Portfolio positions with returns and sectors.
            benchmark_positions: Benchmark positions.

        Returns:
            BrinsonAttribution.
        """
        # Aggregate to sector level
        def aggregate_by_sector(pos_list):
            sector_data: dict[str, dict] = {}
            for pos in pos_list:
                sector = pos.get("sector", "Unknown")
                weight = pos.get("weight", 0)
                ret = pos.get("return", 0)

                if sector not in sector_data:
                    sector_data[sector] = {"weight": 0, "weighted_return": 0}

                sector_data[sector]["weight"] += weight
                sector_data[sector]["weighted_return"] += weight * ret

            # Calculate sector returns
            result_weights = {}
            result_returns = {}
            for sector, data in sector_data.items():
                result_weights[sector] = data["weight"]
                if data["weight"] > 0:
                    result_returns[sector] = data["weighted_return"] / data["weight"]
                else:
                    result_returns[sector] = 0

            return result_weights, result_returns

        port_weights, port_returns = aggregate_by_sector(positions)
        bench_weights, bench_returns = aggregate_by_sector(benchmark_positions)

        return self.brinson_attribution(
            port_weights, bench_weights, port_returns, bench_returns
        )

    # =========================================================================
    # Factor Attribution
    # =========================================================================

    def factor_attribution(
        self,
        portfolio_return: float,
        factor_exposures: dict[str, float],  # {factor: exposure/beta}
        factor_returns: dict[str, float],  # {factor: return during period}
    ) -> FactorAttribution:
        """Calculate factor-based performance attribution.

        Decomposes portfolio return into factor contributions:
        R_portfolio = sum(exposure_i * factor_return_i) + alpha

        Args:
            portfolio_return: Total portfolio return.
            factor_exposures: Portfolio exposure to each factor.
            factor_returns: Factor returns during the period.

        Returns:
            FactorAttribution with contributions from each factor.
        """
        result = FactorAttribution(total_return=portfolio_return)
        result.factor_exposures = factor_exposures
        result.factor_returns = factor_returns

        # Calculate contribution from each factor
        explained_return = 0.0

        for factor in self.FACTORS:
            exposure = factor_exposures.get(factor, 0)
            factor_ret = factor_returns.get(factor, 0)
            contribution = exposure * factor_ret

            explained_return += contribution

            # Map to result attributes
            if factor == "market":
                result.market_contribution = contribution
            elif factor == "value":
                result.value_contribution = contribution
            elif factor == "momentum":
                result.momentum_contribution = contribution
            elif factor == "quality":
                result.quality_contribution = contribution
            elif factor == "growth":
                result.growth_contribution = contribution
            elif factor == "volatility":
                result.volatility_contribution = contribution
            elif factor == "technical":
                result.technical_contribution = contribution

        # Residual (alpha) is unexplained return
        result.residual = portfolio_return - explained_return

        return result

    def factor_attribution_regression(
        self,
        portfolio_returns: pd.Series,
        factor_returns: pd.DataFrame,  # Columns are factor names
    ) -> FactorAttribution:
        """Calculate factor attribution using regression.

        Runs multiple regression of portfolio returns on factor returns
        to estimate factor exposures and attribute returns.

        Args:
            portfolio_returns: Time series of portfolio returns.
            factor_returns: DataFrame with factor return time series.

        Returns:
            FactorAttribution with regression-based estimates.
        """
        import statsmodels.api as sm

        # Align data
        aligned = pd.concat([portfolio_returns, factor_returns], axis=1).dropna()
        if len(aligned) < 30:
            logger.warning("Insufficient data for factor regression")
            return FactorAttribution()

        Y = aligned.iloc[:, 0]  # Portfolio returns
        X = aligned.iloc[:, 1:]  # Factor returns
        X = sm.add_constant(X)

        # Run regression
        try:
            model = sm.OLS(Y, X).fit()
        except Exception as e:
            logger.error(f"Factor regression failed: {e}")
            return FactorAttribution()

        # Extract results
        result = FactorAttribution()
        result.total_return = Y.sum()

        # Factor exposures (betas)
        for factor in X.columns:
            if factor != "const":
                result.factor_exposures[factor] = model.params.get(factor, 0)

        # Calculate contributions over the period
        for factor in factor_returns.columns:
            exposure = result.factor_exposures.get(factor, 0)
            factor_ret = factor_returns[factor].sum()
            result.factor_returns[factor] = factor_ret
            contribution = exposure * factor_ret

            if factor == "market":
                result.market_contribution = contribution
            elif factor == "value":
                result.value_contribution = contribution
            elif factor == "momentum":
                result.momentum_contribution = contribution
            elif factor == "quality":
                result.quality_contribution = contribution
            elif factor == "growth":
                result.growth_contribution = contribution

        # Alpha (intercept * number of periods)
        result.residual = model.params.get("const", 0) * len(Y)

        return result

    def calculate_factor_exposures(
        self,
        positions: list[dict],  # [{symbol, weight, factor_scores}]
    ) -> dict[str, float]:
        """Calculate portfolio factor exposures from position factor scores.

        Portfolio exposure to factor = sum(weight * position_score)

        Args:
            positions: Positions with factor scores.

        Returns:
            Dict of factor exposures.
        """
        exposures = {factor: 0.0 for factor in self.FACTORS}

        total_weight = sum(p.get("weight", 0) for p in positions)
        if total_weight == 0:
            return exposures

        for pos in positions:
            weight = pos.get("weight", 0)
            scores = pos.get("factor_scores", {})

            for factor in self.FACTORS:
                score = scores.get(factor, 0.5)  # Default neutral score
                # Convert percentile score to exposure (-0.5 to 0.5 scale)
                exposure = score - 0.5
                exposures[factor] += weight * exposure

        return exposures

    # =========================================================================
    # Utilities
    # =========================================================================

    def format_attribution_report(
        self,
        brinson: Optional[BrinsonAttribution] = None,
        factor: Optional[FactorAttribution] = None,
    ) -> str:
        """Format attribution results as a report.

        Args:
            brinson: Brinson attribution results.
            factor: Factor attribution results.

        Returns:
            Formatted string report.
        """
        lines = ["=" * 50, "PERFORMANCE ATTRIBUTION REPORT", "=" * 50, ""]

        if brinson:
            lines.append("BRINSON ATTRIBUTION")
            lines.append("-" * 30)
            lines.append(f"Total Return:      {brinson.total_return:+.2%}")
            lines.append(f"Benchmark Return:  {brinson.benchmark_return:+.2%}")
            lines.append(f"Active Return:     {brinson.active_return:+.2%}")
            lines.append("")
            lines.append("Attribution:")
            lines.append(f"  Allocation Effect:   {brinson.allocation_effect:+.2%}")
            lines.append(f"  Selection Effect:    {brinson.selection_effect:+.2%}")
            lines.append(f"  Interaction Effect:  {brinson.interaction_effect:+.2%}")
            lines.append("")

            if brinson.sector_attribution:
                lines.append("By Sector:")
                for sector, data in sorted(
                    brinson.sector_attribution.items(),
                    key=lambda x: x[1]["total"],
                    reverse=True,
                ):
                    lines.append(
                        f"  {sector:20} {data['total']:+.2%} "
                        f"(A:{data['allocation']:+.2%} S:{data['selection']:+.2%})"
                    )
            lines.append("")

        if factor:
            lines.append("FACTOR ATTRIBUTION")
            lines.append("-" * 30)
            lines.append(f"Total Return: {factor.total_return:+.2%}")
            lines.append("")

            contributions = [
                ("Market (Beta)", factor.market_contribution),
                ("Value", factor.value_contribution),
                ("Momentum", factor.momentum_contribution),
                ("Quality", factor.quality_contribution),
                ("Growth", factor.growth_contribution),
                ("Residual (Alpha)", factor.residual),
            ]

            total = sum(c[1] for c in contributions)

            for name, contrib in contributions:
                pct = contrib / total * 100 if total != 0 else 0
                lines.append(f"  {name:20} {contrib:+.2%}  ({pct:+.0f}%)")

        return "\n".join(lines)
