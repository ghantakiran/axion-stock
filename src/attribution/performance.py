"""Performance Contribution Analysis.

Position-level return contribution, top/bottom contributor ranking,
cumulative contribution tracking, and relative contribution vs benchmark.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PositionContribution:
    """Single-position contribution to portfolio return."""
    symbol: str
    weight: float = 0.0
    return_: float = 0.0
    contribution: float = 0.0
    pct_of_total: float = 0.0
    sector: str = ""


@dataclass
class ContributionSummary:
    """Summary of contribution analysis."""
    total_return: float = 0.0
    positions: list[PositionContribution] = field(default_factory=list)
    top_contributors: list[PositionContribution] = field(default_factory=list)
    bottom_contributors: list[PositionContribution] = field(default_factory=list)
    n_positive: int = 0
    n_negative: int = 0

    @property
    def hit_rate(self) -> float:
        """Fraction of positions with positive contribution."""
        total = self.n_positive + self.n_negative
        return self.n_positive / total if total > 0 else 0.0

    @property
    def concentration(self) -> float:
        """How much of total return comes from top 5 contributors."""
        if not self.top_contributors or abs(self.total_return) < 1e-10:
            return 0.0
        top5_sum = sum(
            abs(p.contribution) for p in self.top_contributors[:5]
        )
        return top5_sum / abs(self.total_return)


class PerformanceContributor:
    """Computes position-level contributions to portfolio returns."""

    def __init__(self, top_n: int = 10) -> None:
        self.top_n = top_n

    def analyze(
        self,
        weights: dict[str, float],
        returns: dict[str, float],
        sector_map: Optional[dict[str, str]] = None,
    ) -> ContributionSummary:
        """Compute contribution for each position.

        Args:
            weights: Symbol -> portfolio weight.
            returns: Symbol -> return in period.
            sector_map: Optional symbol -> sector mapping.

        Returns:
            ContributionSummary with sorted contributors.
        """
        positions: list[PositionContribution] = []
        total_return = 0.0

        for symbol in sorted(weights.keys()):
            w = weights[symbol]
            r = returns.get(symbol, 0.0)
            contrib = w * r
            total_return += contrib

            positions.append(PositionContribution(
                symbol=symbol,
                weight=w,
                return_=r,
                contribution=contrib,
                sector=sector_map.get(symbol, "") if sector_map else "",
            ))

        # Compute pct_of_total
        for p in positions:
            if abs(total_return) > 1e-10:
                p.pct_of_total = p.contribution / total_return
            else:
                p.pct_of_total = 0.0

        # Sort
        sorted_desc = sorted(positions, key=lambda p: p.contribution, reverse=True)
        sorted_asc = sorted(positions, key=lambda p: p.contribution)

        n_pos = sum(1 for p in positions if p.contribution > 0)
        n_neg = sum(1 for p in positions if p.contribution < 0)

        return ContributionSummary(
            total_return=total_return,
            positions=sorted_desc,
            top_contributors=sorted_desc[:self.top_n],
            bottom_contributors=sorted_asc[:self.top_n],
            n_positive=n_pos,
            n_negative=n_neg,
        )

    def relative_contributions(
        self,
        portfolio_weights: dict[str, float],
        portfolio_returns: dict[str, float],
        benchmark_weights: dict[str, float],
        benchmark_returns: dict[str, float],
    ) -> ContributionSummary:
        """Compute relative (active) contributions.

        For each position: active_contribution =
            w_p * r_p - w_b * r_b

        Args:
            portfolio_weights: Portfolio symbol -> weight.
            portfolio_returns: Portfolio symbol -> return.
            benchmark_weights: Benchmark symbol -> weight.
            benchmark_returns: Benchmark symbol -> return.

        Returns:
            ContributionSummary with active contributions.
        """
        all_symbols = sorted(
            set(portfolio_weights) | set(benchmark_weights)
        )

        positions: list[PositionContribution] = []
        total_active = 0.0

        for symbol in all_symbols:
            wp = portfolio_weights.get(symbol, 0.0)
            rp = portfolio_returns.get(symbol, 0.0)
            wb = benchmark_weights.get(symbol, 0.0)
            rb = benchmark_returns.get(symbol, 0.0)

            port_contrib = wp * rp
            bm_contrib = wb * rb
            active_contrib = port_contrib - bm_contrib
            total_active += active_contrib

            positions.append(PositionContribution(
                symbol=symbol,
                weight=wp - wb,  # active weight
                return_=rp - rb,  # active return
                contribution=active_contrib,
            ))

        for p in positions:
            if abs(total_active) > 1e-10:
                p.pct_of_total = p.contribution / total_active
            else:
                p.pct_of_total = 0.0

        sorted_desc = sorted(positions, key=lambda p: p.contribution, reverse=True)
        sorted_asc = sorted(positions, key=lambda p: p.contribution)

        n_pos = sum(1 for p in positions if p.contribution > 0)
        n_neg = sum(1 for p in positions if p.contribution < 0)

        return ContributionSummary(
            total_return=total_active,
            positions=sorted_desc,
            top_contributors=sorted_desc[:self.top_n],
            bottom_contributors=sorted_asc[:self.top_n],
            n_positive=n_pos,
            n_negative=n_neg,
        )

    def cumulative_contributions(
        self,
        daily_weights: pd.DataFrame,
        daily_returns: pd.DataFrame,
    ) -> pd.DataFrame:
        """Compute cumulative contribution over time.

        Args:
            daily_weights: DataFrame with dates as index, symbols as columns.
            daily_returns: DataFrame with dates as index, symbols as columns.

        Returns:
            DataFrame with cumulative contribution per symbol.
        """
        common_cols = sorted(
            set(daily_weights.columns) & set(daily_returns.columns)
        )
        common_idx = daily_weights.index.intersection(daily_returns.index)

        if not common_cols or len(common_idx) < 1:
            return pd.DataFrame()

        w = daily_weights.loc[common_idx, common_cols]
        r = daily_returns.loc[common_idx, common_cols]

        # Daily contribution = weight * return
        daily_contrib = w * r

        # Cumulative
        return daily_contrib.cumsum()

    def sector_contributions(
        self,
        weights: dict[str, float],
        returns: dict[str, float],
        sector_map: dict[str, str],
    ) -> list[dict]:
        """Aggregate contributions by sector.

        Args:
            weights: Symbol -> weight.
            returns: Symbol -> return.
            sector_map: Symbol -> sector.

        Returns:
            List of dicts with sector, weight, contribution, pct_of_total.
        """
        summary = self.analyze(weights, returns, sector_map)

        sector_agg: dict[str, dict] = {}
        for p in summary.positions:
            sector = p.sector or "Other"
            if sector not in sector_agg:
                sector_agg[sector] = {
                    "sector": sector,
                    "weight": 0.0,
                    "contribution": 0.0,
                }
            sector_agg[sector]["weight"] += p.weight
            sector_agg[sector]["contribution"] += p.contribution

        total = summary.total_return
        for s in sector_agg.values():
            s["pct_of_total"] = (
                s["contribution"] / total if abs(total) > 1e-10 else 0.0
            )

        return sorted(
            sector_agg.values(),
            key=lambda x: x["contribution"],
            reverse=True,
        )
