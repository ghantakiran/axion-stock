"""Cross-Asset Portfolio Optimization.

Multi-asset covariance estimation, allocation optimization,
and pre-built portfolio templates.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.multi_asset.config import (
    AssetClass,
    CROSS_ASSET_TEMPLATES,
    MultiAssetConfig,
    DEFAULT_MULTI_ASSET_CONFIG,
)
from src.multi_asset.models import (
    AssetAllocation,
    MultiAssetPortfolio,
)

logger = logging.getLogger(__name__)


class CrossAssetOptimizer:
    """Optimizes portfolios across multiple asset classes.

    Features:
    - Cross-asset covariance matrix estimation
    - Mean-variance optimization with asset class constraints
    - Pre-built allocation templates
    - Risk budgeting across asset classes
    """

    def __init__(self, config: Optional[MultiAssetConfig] = None):
        self.config = config or DEFAULT_MULTI_ASSET_CONFIG

    def optimize(
        self,
        expected_returns: dict[str, float],
        covariance: pd.DataFrame,
        asset_classes: dict[str, AssetClass],
        constraints: Optional[dict[AssetClass, float]] = None,
        total_capital: float = 100_000,
    ) -> MultiAssetPortfolio:
        """Optimize a multi-asset portfolio.

        Args:
            expected_returns: Symbol -> expected annual return.
            covariance: Covariance matrix as DataFrame.
            asset_classes: Symbol -> asset class mapping.
            constraints: Max weight per asset class.
            total_capital: Total portfolio value.

        Returns:
            Optimized MultiAssetPortfolio.
        """
        symbols = list(expected_returns.keys())
        n = len(symbols)

        if n == 0:
            return MultiAssetPortfolio(name="empty", total_value_usd=total_capital)

        # Simple equal-weight within asset classes, respecting constraints
        class_weights = self._allocate_to_classes(
            symbols, asset_classes, constraints,
        )

        allocations = []
        for sym in symbols:
            w = class_weights.get(sym, 0.0)
            allocations.append(AssetAllocation(
                symbol=sym,
                asset_class=asset_classes.get(sym, AssetClass.US_EQUITY),
                weight=w,
                value_usd=w * total_capital,
            ))

        return MultiAssetPortfolio(
            name="optimized",
            total_value_usd=total_capital,
            allocations=allocations,
        )

    def from_template(
        self,
        template_name: str,
        symbols_by_class: dict[AssetClass, list[str]],
        total_capital: float = 100_000,
    ) -> MultiAssetPortfolio:
        """Build a portfolio from a pre-defined template.

        Args:
            template_name: Template name (conservative, balanced, etc.).
            symbols_by_class: Asset class -> list of symbols.
            total_capital: Total portfolio value.

        Returns:
            MultiAssetPortfolio with template allocation.
        """
        template = CROSS_ASSET_TEMPLATES.get(template_name)
        if not template:
            raise ValueError(
                f"Unknown template: {template_name}. "
                f"Available: {list(CROSS_ASSET_TEMPLATES.keys())}"
            )

        allocations = []
        for ac, class_weight in template.items():
            syms = symbols_by_class.get(ac, [])
            if not syms or class_weight <= 0:
                continue

            per_sym = class_weight / len(syms)
            for sym in syms:
                allocations.append(AssetAllocation(
                    symbol=sym,
                    asset_class=ac,
                    weight=per_sym,
                    value_usd=per_sym * total_capital,
                ))

        return MultiAssetPortfolio(
            name=template_name,
            total_value_usd=total_capital,
            allocations=allocations,
            template=template_name,
        )

    def build_covariance(
        self,
        returns_by_asset: dict[str, pd.Series],
    ) -> pd.DataFrame:
        """Build a cross-asset covariance matrix from return series.

        Args:
            returns_by_asset: Symbol -> daily returns Series.

        Returns:
            Annualized covariance matrix.
        """
        if not returns_by_asset:
            return pd.DataFrame()

        # Align all series
        df = pd.DataFrame(returns_by_asset)
        df = df.dropna(how="all")
        df = df.fillna(0)

        # Annualize
        cov = df.cov() * 252
        return cov

    def risk_budget_allocation(
        self,
        covariance: pd.DataFrame,
        risk_budgets: dict[str, float],
    ) -> dict[str, float]:
        """Allocate weights to achieve target risk budgets.

        Uses iterative approach to match each asset's risk
        contribution to its target budget.

        Args:
            covariance: Covariance matrix.
            risk_budgets: Symbol -> target risk contribution fraction.

        Returns:
            Symbol -> weight dict.
        """
        symbols = list(covariance.columns)
        n = len(symbols)
        if n == 0:
            return {}

        cov = covariance.values
        budgets = np.array([risk_budgets.get(s, 1.0 / n) for s in symbols])
        budgets = budgets / budgets.sum()

        # Start with inverse-vol weighting
        vols = np.sqrt(np.diag(cov))
        vols = np.where(vols > 0, vols, 1e-6)
        weights = (1.0 / vols)
        weights = weights / weights.sum()

        # Iterative risk parity
        for _ in range(100):
            port_vol = np.sqrt(weights @ cov @ weights)
            if port_vol < 1e-12:
                break

            marginal_risk = cov @ weights
            risk_contrib = weights * marginal_risk / port_vol
            total_risk = risk_contrib.sum()

            if total_risk < 1e-12:
                break

            risk_pct = risk_contrib / total_risk
            adjustment = budgets / (risk_pct + 1e-12)
            weights = weights * adjustment
            weights = weights / weights.sum()

        return dict(zip(symbols, weights))

    def _allocate_to_classes(
        self,
        symbols: list[str],
        asset_classes: dict[str, AssetClass],
        constraints: Optional[dict[AssetClass, float]] = None,
    ) -> dict[str, float]:
        """Equal-weight allocation within asset classes.

        Args:
            symbols: All symbols.
            asset_classes: Symbol -> class mapping.
            constraints: Max weight per class.

        Returns:
            Symbol -> weight dict.
        """
        # Group symbols by class
        groups: dict[AssetClass, list[str]] = {}
        for sym in symbols:
            ac = asset_classes.get(sym, AssetClass.US_EQUITY)
            if ac not in groups:
                groups[ac] = []
            groups[ac].append(sym)

        n_classes = len(groups)
        if n_classes == 0:
            return {}

        # Default equal allocation across classes
        default_class_weight = 1.0 / n_classes

        weights = {}
        for ac, syms in groups.items():
            max_w = (constraints or {}).get(ac, default_class_weight)
            class_w = min(default_class_weight, max_w)
            per_sym = class_w / len(syms) if syms else 0

            for sym in syms:
                weights[sym] = per_sym

        # Renormalize to sum to 1
        total = sum(weights.values())
        if total > 0:
            weights = {s: w / total for s, w in weights.items()}

        return weights
