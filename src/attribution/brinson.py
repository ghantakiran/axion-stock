"""Brinson-Fachler Attribution Model.

Decomposes active return into allocation, selection, and interaction effects.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.attribution.models import BrinsonAttribution, SectorAttribution

logger = logging.getLogger(__name__)


class BrinsonAnalyzer:
    """Brinson-Fachler attribution analysis.

    Decomposes the active return (portfolio - benchmark) into:
    - Allocation effect: over/underweighting outperforming sectors
    - Selection effect: stock picking within sectors
    - Interaction effect: combined allocation + selection

    Formulas:
        Allocation = (wp - wb) × (Rb_s - Rb)
        Selection  = wb × (Rp_s - Rb_s)
        Interaction = (wp - wb) × (Rp_s - Rb_s)

    Where:
        wp = portfolio sector weight
        wb = benchmark sector weight
        Rp_s = portfolio return in sector
        Rb_s = benchmark return in sector
        Rb = total benchmark return
    """

    def analyze(
        self,
        portfolio_weights: dict[str, float],
        benchmark_weights: dict[str, float],
        portfolio_returns: dict[str, float],
        benchmark_returns: dict[str, float],
    ) -> BrinsonAttribution:
        """Perform Brinson-Fachler attribution.

        Args:
            portfolio_weights: Sector -> portfolio weight.
            benchmark_weights: Sector -> benchmark weight.
            portfolio_returns: Sector -> portfolio return within sector.
            benchmark_returns: Sector -> benchmark return within sector.

        Returns:
            BrinsonAttribution with per-sector breakdown.
        """
        all_sectors = sorted(
            set(portfolio_weights) | set(benchmark_weights)
        )

        # Total benchmark return
        total_bm_return = sum(
            benchmark_weights.get(s, 0) * benchmark_returns.get(s, 0)
            for s in all_sectors
        )

        sectors: list[SectorAttribution] = []
        total_allocation = 0.0
        total_selection = 0.0
        total_interaction = 0.0

        for sector in all_sectors:
            wp = portfolio_weights.get(sector, 0.0)
            wb = benchmark_weights.get(sector, 0.0)
            rp = portfolio_returns.get(sector, 0.0)
            rb = benchmark_returns.get(sector, 0.0)

            allocation = (wp - wb) * (rb - total_bm_return)
            selection = wb * (rp - rb)
            interaction = (wp - wb) * (rp - rb)
            total_effect = allocation + selection + interaction

            sa = SectorAttribution(
                sector=sector,
                portfolio_weight=wp,
                benchmark_weight=wb,
                portfolio_return=rp,
                benchmark_return=rb,
                allocation_effect=allocation,
                selection_effect=selection,
                interaction_effect=interaction,
                total_effect=total_effect,
            )
            sectors.append(sa)

            total_allocation += allocation
            total_selection += selection
            total_interaction += interaction

        # Total portfolio return
        total_port_return = sum(
            portfolio_weights.get(s, 0) * portfolio_returns.get(s, 0)
            for s in all_sectors
        )

        return BrinsonAttribution(
            portfolio_return=total_port_return,
            benchmark_return=total_bm_return,
            active_return=total_port_return - total_bm_return,
            total_allocation=total_allocation,
            total_selection=total_selection,
            total_interaction=total_interaction,
            sectors=sectors,
        )

    def analyze_from_holdings(
        self,
        portfolio_holdings: pd.DataFrame,
        benchmark_holdings: pd.DataFrame,
        sector_column: str = "sector",
        weight_column: str = "weight",
        return_column: str = "return",
    ) -> BrinsonAttribution:
        """Perform attribution from holdings DataFrames.

        Args:
            portfolio_holdings: DataFrame with sector, weight, return columns.
            benchmark_holdings: DataFrame with sector, weight, return columns.
            sector_column: Column name for sector.
            weight_column: Column name for weight.
            return_column: Column name for return.

        Returns:
            BrinsonAttribution.
        """
        # Aggregate to sector level
        port_by_sector = (
            portfolio_holdings
            .groupby(sector_column)
            .apply(
                lambda g: pd.Series({
                    "weight": g[weight_column].sum(),
                    "return": (
                        (g[weight_column] * g[return_column]).sum()
                        / g[weight_column].sum()
                    ) if g[weight_column].sum() > 0 else 0.0,
                }),
                include_groups=False,
            )
        )

        bm_by_sector = (
            benchmark_holdings
            .groupby(sector_column)
            .apply(
                lambda g: pd.Series({
                    "weight": g[weight_column].sum(),
                    "return": (
                        (g[weight_column] * g[return_column]).sum()
                        / g[weight_column].sum()
                    ) if g[weight_column].sum() > 0 else 0.0,
                }),
                include_groups=False,
            )
        )

        return self.analyze(
            portfolio_weights=port_by_sector["weight"].to_dict(),
            benchmark_weights=bm_by_sector["weight"].to_dict(),
            portfolio_returns=port_by_sector["return"].to_dict(),
            benchmark_returns=bm_by_sector["return"].to_dict(),
        )
