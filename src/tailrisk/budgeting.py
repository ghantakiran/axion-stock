"""Drawdown Risk Budgeting.

Estimates maximum drawdowns, computes Conditional Drawdown-at-Risk
(CDaR), allocates risk budgets across assets, and recommends
position sizes based on drawdown constraints.
"""

import logging
from typing import Optional

import numpy as np

from src.tailrisk.config import BudgetingConfig, RiskBudgetMethod
from src.tailrisk.models import DrawdownStats, DrawdownBudget

logger = logging.getLogger(__name__)


class DrawdownRiskBudgeter:
    """Manages drawdown-based risk budgets."""

    def __init__(self, config: Optional[BudgetingConfig] = None) -> None:
        self.config = config or BudgetingConfig()

    def compute_drawdown_stats(
        self, returns: list[float]
    ) -> DrawdownStats:
        """Compute drawdown statistics from a return series.

        Args:
            returns: Historical returns.

        Returns:
            DrawdownStats.
        """
        if not returns:
            return DrawdownStats()

        arr = np.array(returns)
        cumulative = np.cumprod(1 + arr)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = cumulative / running_max - 1

        max_dd = float(np.min(drawdowns))
        avg_dd = float(np.mean(drawdowns[drawdowns < 0])) if (drawdowns < 0).any() else 0.0
        current_dd = float(drawdowns[-1])

        # Drawdown duration (current)
        duration = 0
        for i in range(len(drawdowns) - 1, -1, -1):
            if drawdowns[i] < -0.001:
                duration += 1
            else:
                break

        # Recovery days from last max drawdown
        max_dd_idx = int(np.argmin(drawdowns))
        recovery = 0
        for i in range(max_dd_idx + 1, len(drawdowns)):
            if drawdowns[i] >= -0.001:
                recovery = i - max_dd_idx
                break
        if recovery == 0 and max_dd_idx < len(drawdowns) - 1:
            recovery = len(drawdowns) - max_dd_idx  # Still recovering

        # CDaR: average of worst drawdowns beyond confidence threshold
        sorted_dd = np.sort(drawdowns)
        n_tail = max(1, int(len(sorted_dd) * (1 - self.config.confidence)))
        cdar = float(np.mean(sorted_dd[:n_tail]))

        return DrawdownStats(
            max_drawdown=round(max_dd, 6),
            avg_drawdown=round(avg_dd, 6),
            current_drawdown=round(current_dd, 6),
            drawdown_duration=duration,
            recovery_days=recovery,
            cdar=round(cdar, 6),
        )

    def allocate_budget(
        self,
        asset_returns: dict[str, list[float]],
        current_weights: dict[str, float],
        max_portfolio_dd: Optional[float] = None,
    ) -> list[DrawdownBudget]:
        """Allocate drawdown risk budget across assets.

        Args:
            asset_returns: Dict of {asset: return_series}.
            current_weights: Dict of {asset: current_weight}.
            max_portfolio_dd: Max allowed portfolio drawdown.

        Returns:
            List of DrawdownBudget per asset.
        """
        max_dd = max_portfolio_dd or self.config.max_portfolio_drawdown
        assets = list(asset_returns.keys())

        if not assets:
            return []

        # Compute per-asset drawdown stats
        stats: dict[str, DrawdownStats] = {}
        for asset in assets:
            stats[asset] = self.compute_drawdown_stats(asset_returns[asset])

        # Allocate budget based on method
        budgets = self._allocate_by_method(assets, stats, current_weights, max_dd)

        return budgets

    def recommend_weights(
        self,
        asset_returns: dict[str, list[float]],
        max_portfolio_dd: Optional[float] = None,
    ) -> dict[str, float]:
        """Recommend portfolio weights based on drawdown budgets.

        Uses inverse-drawdown weighting: assets with lower max drawdown
        get higher weights.

        Args:
            asset_returns: Dict of {asset: return_series}.
            max_portfolio_dd: Max allowed portfolio drawdown.

        Returns:
            Dict of {asset: recommended_weight}.
        """
        assets = list(asset_returns.keys())
        if not assets:
            return {}

        stats = {}
        for asset in assets:
            stats[asset] = self.compute_drawdown_stats(asset_returns[asset])

        # Inverse max-drawdown weighting
        inv_dd = {}
        for asset in assets:
            dd = abs(stats[asset].max_drawdown)
            inv_dd[asset] = 1.0 / dd if dd > 0.001 else 100.0

        total = sum(inv_dd.values())
        weights = {a: round(v / total, 4) for a, v in inv_dd.items()} if total > 0 else {}

        return weights

    def _allocate_by_method(
        self,
        assets: list[str],
        stats: dict[str, DrawdownStats],
        weights: dict[str, float],
        max_dd: float,
    ) -> list[DrawdownBudget]:
        """Allocate budget using configured method."""
        n = len(assets)
        method = self.config.method

        if method == RiskBudgetMethod.EQUAL:
            budget_shares = {a: 1.0 / n for a in assets}
        elif method == RiskBudgetMethod.PROPORTIONAL:
            total_w = sum(weights.get(a, 0) for a in assets)
            budget_shares = {
                a: weights.get(a, 0) / total_w if total_w > 0 else 1.0 / n
                for a in assets
            }
        else:  # INVERSE_VOL
            inv_dd = {}
            for a in assets:
                dd = abs(stats[a].max_drawdown)
                inv_dd[a] = 1.0 / dd if dd > 0.001 else 100.0
            total_inv = sum(inv_dd.values())
            budget_shares = {
                a: inv_dd[a] / total_inv if total_inv > 0 else 1.0 / n
                for a in assets
            }

        results = []
        for asset in assets:
            share = budget_shares[asset]
            allocated = abs(max_dd) * share
            current_usage = abs(stats[asset].max_drawdown) * weights.get(asset, 0)
            remaining = max(0, allocated - current_usage)

            # Recommended weight: scale by budget utilization
            asset_dd = abs(stats[asset].max_drawdown)
            rec_weight = allocated / asset_dd if asset_dd > 0 else 0.0
            rec_weight = min(rec_weight, 0.40)  # Cap single position

            results.append(DrawdownBudget(
                asset=asset,
                weight=round(weights.get(asset, 0), 4),
                max_drawdown=round(float(stats[asset].max_drawdown), 6),
                allocated_budget=round(float(allocated), 6),
                current_usage=round(float(current_usage), 6),
                remaining_budget=round(float(remaining), 6),
                recommended_weight=round(float(rec_weight), 4),
            ))

        results.sort(key=lambda x: x.utilization_pct, reverse=True)
        return results
