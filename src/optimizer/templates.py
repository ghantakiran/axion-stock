"""Portfolio Templates & Strategy Blending.

Pre-built portfolio strategies and blending for combining
multiple strategies with custom allocations.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from src.optimizer.config import OptimizationConfig, ConstraintConfig

logger = logging.getLogger(__name__)


@dataclass
class TemplateSpec:
    """Specification for a portfolio template."""

    name: str = ""
    description: str = ""
    min_positions: int = 10
    max_positions: int = 30
    max_weight: float = 0.10
    rebalance_frequency: str = "monthly"
    factor_preferences: dict = field(default_factory=dict)
    sector_constraints: dict = field(default_factory=dict)
    optimization_method: str = "max_sharpe"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "min_positions": self.min_positions,
            "max_positions": self.max_positions,
            "max_weight": self.max_weight,
            "rebalance_frequency": self.rebalance_frequency,
            "optimization_method": self.optimization_method,
        }


# Pre-built templates per PRD R4.1
TEMPLATES: dict[str, TemplateSpec] = {
    "aggressive_alpha": TemplateSpec(
        name="Aggressive Alpha",
        description="Top factor scores, concentrated positions",
        min_positions=10,
        max_positions=15,
        max_weight=0.15,
        rebalance_frequency="monthly",
        factor_preferences={"momentum": 0.30, "quality": 0.25, "growth": 0.25, "value": 0.20},
        optimization_method="max_sharpe",
    ),
    "balanced_factor": TemplateSpec(
        name="Balanced Factor",
        description="Equal factor exposure, diversified",
        min_positions=25,
        max_positions=30,
        max_weight=0.06,
        rebalance_frequency="monthly",
        factor_preferences={"value": 0.20, "momentum": 0.20, "quality": 0.20, "growth": 0.20, "volatility": 0.20},
        optimization_method="max_sharpe",
    ),
    "quality_income": TemplateSpec(
        name="Quality Income",
        description="High quality + dividend yield focus",
        min_positions=20,
        max_positions=25,
        max_weight=0.08,
        rebalance_frequency="quarterly",
        factor_preferences={"quality": 0.40, "value": 0.30, "volatility": 0.30},
        optimization_method="min_variance",
    ),
    "momentum_rider": TemplateSpec(
        name="Momentum Rider",
        description="Top momentum with trend filters",
        min_positions=10,
        max_positions=15,
        max_weight=0.12,
        rebalance_frequency="biweekly",
        factor_preferences={"momentum": 0.60, "quality": 0.20, "growth": 0.20},
        optimization_method="max_sharpe",
    ),
    "value_contrarian": TemplateSpec(
        name="Value Contrarian",
        description="Deep value with quality floor",
        min_positions=15,
        max_positions=20,
        max_weight=0.10,
        rebalance_frequency="monthly",
        factor_preferences={"value": 0.50, "quality": 0.30, "growth": 0.20},
        optimization_method="max_sharpe",
    ),
    "low_volatility": TemplateSpec(
        name="Low Volatility",
        description="Minimum variance with quality tilt",
        min_positions=25,
        max_positions=30,
        max_weight=0.06,
        rebalance_frequency="quarterly",
        factor_preferences={"volatility": 0.40, "quality": 0.35, "value": 0.25},
        optimization_method="min_variance",
    ),
    "risk_parity": TemplateSpec(
        name="Risk Parity",
        description="Equal risk contribution from each position",
        min_positions=20,
        max_positions=30,
        max_weight=0.10,
        rebalance_frequency="monthly",
        factor_preferences={"quality": 0.30, "value": 0.25, "momentum": 0.25, "volatility": 0.20},
        optimization_method="risk_parity",
    ),
    "all_weather": TemplateSpec(
        name="All-Weather",
        description="Multi-regime stable returns",
        min_positions=10,
        max_positions=20,
        max_weight=0.12,
        rebalance_frequency="quarterly",
        factor_preferences={"quality": 0.30, "volatility": 0.30, "value": 0.20, "momentum": 0.20},
        optimization_method="risk_parity",
    ),
}


class PortfolioTemplate:
    """Construct portfolios from template specifications.

    Scores and filters the universe based on factor preferences,
    then selects top candidates.

    Example:
        template = PortfolioTemplate(TEMPLATES["aggressive_alpha"])
        selected, scores = template.select_universe(factor_scores, 500)
    """

    def __init__(self, spec: TemplateSpec):
        self.spec = spec

    def select_universe(
        self,
        factor_scores: pd.DataFrame,
        universe_size: int = 500,
    ) -> tuple[list[str], pd.Series]:
        """Score and select stocks based on template factor preferences.

        Args:
            factor_scores: DataFrame with factor scores (index=symbols, cols=factors).
            universe_size: Max universe to consider.

        Returns:
            Tuple of (selected symbols, composite scores).
        """
        available_factors = [
            f for f in self.spec.factor_preferences
            if f in factor_scores.columns
        ]

        if not available_factors:
            # No matching factors, return top N by mean score
            mean_scores = factor_scores.mean(axis=1).sort_values(ascending=False)
            selected = mean_scores.head(self.spec.max_positions).index.tolist()
            return selected, mean_scores

        # Weighted composite score
        composite = pd.Series(0.0, index=factor_scores.index)
        total_weight = 0.0

        for factor in available_factors:
            weight = self.spec.factor_preferences[factor]
            composite += factor_scores[factor] * weight
            total_weight += weight

        if total_weight > 0:
            composite /= total_weight

        composite = composite.sort_values(ascending=False)

        # Select top candidates
        n_select = min(self.spec.max_positions, len(composite))
        selected = composite.head(n_select).index.tolist()

        return selected, composite

    def generate_initial_weights(
        self,
        selected: list[str],
        scores: pd.Series,
    ) -> pd.Series:
        """Generate initial weights from scores.

        Args:
            selected: Selected symbols.
            scores: Composite scores.

        Returns:
            Series of weights summing to 1.
        """
        if not selected:
            return pd.Series(dtype=float)

        s = scores.reindex(selected).clip(lower=0)

        total = s.sum()
        if total <= 0:
            # Equal weight fallback
            weights = pd.Series(1.0 / len(selected), index=selected)
        else:
            weights = s / total

        # Iteratively cap and renormalize
        for _ in range(10):
            capped = weights.clip(upper=self.spec.max_weight)
            total = capped.sum()
            if total <= 0:
                break
            weights = capped / total
            if weights.max() <= self.spec.max_weight + 1e-9:
                break

        return weights

    def get_spec(self) -> dict:
        return self.spec.to_dict()


class StrategyBlender:
    """Combine multiple strategy portfolios with custom allocations.

    Example:
        blender = StrategyBlender()
        combined = blender.blend([
            ("aggressive_alpha", weights_aa, 0.60),
            ("quality_income", weights_qi, 0.40),
        ])
    """

    def blend(
        self,
        allocations: list[tuple[str, pd.Series, float]],
    ) -> pd.Series:
        """Blend multiple strategy weight vectors.

        Args:
            allocations: List of (strategy_name, weights, allocation_pct).
                         Allocation pcts should sum to 1.

        Returns:
            Combined portfolio weights.
        """
        combined: dict[str, float] = {}

        for _name, weights, allocation in allocations:
            for symbol, weight in weights.items():
                if symbol not in combined:
                    combined[symbol] = 0.0
                combined[symbol] += weight * allocation

        # Normalize
        total = sum(combined.values())
        if total > 0:
            combined = {s: w / total for s, w in combined.items()}

        return pd.Series(combined).sort_values(ascending=False)

    def blend_from_templates(
        self,
        template_allocations: list[tuple[str, float]],
        factor_scores: pd.DataFrame,
    ) -> pd.Series:
        """Blend using template names and allocations.

        Args:
            template_allocations: List of (template_key, allocation_pct).
            factor_scores: Factor scores for universe selection.

        Returns:
            Combined weights.
        """
        allocations = []

        for template_key, allocation in template_allocations:
            spec = TEMPLATES.get(template_key)
            if spec is None:
                logger.warning("Unknown template: %s", template_key)
                continue

            template = PortfolioTemplate(spec)
            selected, scores = template.select_universe(factor_scores)
            weights = template.generate_initial_weights(selected, scores)
            allocations.append((template_key, weights, allocation))

        if not allocations:
            return pd.Series(dtype=float)

        return self.blend(allocations)

    def analyze_blend(
        self,
        allocations: list[tuple[str, pd.Series, float]],
    ) -> dict:
        """Analyze a blended portfolio.

        Args:
            allocations: Strategy allocations.

        Returns:
            Dict with blend analysis.
        """
        combined = self.blend(allocations)
        n_positions = (combined > 1e-6).sum()
        top5_weight = combined.nlargest(5).sum() if len(combined) >= 5 else combined.sum()

        # HHI (Herfindahl-Hirschman Index)
        hhi = float((combined ** 2).sum()) * 10_000

        return {
            "num_positions": int(n_positions),
            "top5_concentration": float(top5_weight),
            "hhi": hhi,
            "effective_n": 1.0 / float((combined ** 2).sum()) if (combined ** 2).sum() > 0 else 0,
            "max_weight": float(combined.max()) if len(combined) > 0 else 0,
            "strategies": [name for name, _, _ in allocations],
            "allocations": [alloc for _, _, alloc in allocations],
        }
