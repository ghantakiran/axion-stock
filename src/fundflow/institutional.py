"""Institutional Position Analysis.

Tracks 13F filings, ownership concentration,
quarter-over-quarter changes, and top holders.
"""

import logging
from typing import Optional

import numpy as np

from src.fundflow.config import InstitutionalConfig, DEFAULT_INSTITUTIONAL_CONFIG
from src.fundflow.models import InstitutionalPosition, InstitutionalSummary

logger = logging.getLogger(__name__)


class InstitutionalAnalyzer:
    """Analyzes institutional ownership and positioning."""

    def __init__(self, config: Optional[InstitutionalConfig] = None) -> None:
        self.config = config or DEFAULT_INSTITUTIONAL_CONFIG

    def analyze(
        self,
        positions: list[InstitutionalPosition],
        symbol: str = "",
    ) -> InstitutionalSummary:
        """Analyze institutional ownership for a symbol.

        Args:
            positions: List of institutional positions.
            symbol: Stock symbol.

        Returns:
            InstitutionalSummary with ownership metrics.
        """
        if not positions:
            return self._empty_summary(symbol)

        # Filter to minimum ownership
        positions = [
            p for p in positions
            if p.ownership_pct >= self.config.min_ownership_pct
        ]

        if not positions:
            return self._empty_summary(symbol)

        # Total institutional ownership
        total_pct = sum(p.ownership_pct for p in positions)

        # Top holder
        top = max(positions, key=lambda p: p.ownership_pct)

        # Concentration (HHI on ownership shares)
        concentration = self._compute_concentration(positions)

        # Position changes
        changes = self._classify_changes(positions)

        # Net aggregate change
        total_shares = sum(p.shares for p in positions)
        total_change = sum(p.change_shares for p in positions)
        net_change_pct = (total_change / (total_shares - total_change) * 100
                          if total_shares != total_change else 0.0)

        return InstitutionalSummary(
            symbol=symbol or top.symbol,
            total_institutional_pct=round(total_pct, 2),
            n_holders=len(positions),
            top_holder=top.holder_name,
            top_holder_pct=round(top.ownership_pct, 2),
            concentration=round(concentration, 4),
            net_change_pct=round(net_change_pct, 2),
            new_positions=changes["new"],
            exits=changes["exits"],
            increases=changes["increases"],
            decreases=changes["decreases"],
        )

    def rank_holders(
        self, positions: list[InstitutionalPosition]
    ) -> list[InstitutionalPosition]:
        """Rank holders by ownership percentage."""
        return sorted(positions, key=lambda p: p.ownership_pct, reverse=True)

    def top_holders(
        self, positions: list[InstitutionalPosition]
    ) -> list[InstitutionalPosition]:
        """Get top N holders."""
        ranked = self.rank_holders(positions)
        return ranked[: self.config.top_holders_count]

    def _compute_concentration(
        self, positions: list[InstitutionalPosition]
    ) -> float:
        """Herfindahl-Hirschman Index on ownership shares.

        HHI = sum(s_i^2) where s_i is each holder's share of
        total institutional ownership.
        """
        total = sum(p.ownership_pct for p in positions)
        if total == 0:
            return 0.0

        shares = [p.ownership_pct / total for p in positions]
        return float(sum(s * s for s in shares))

    def _classify_changes(
        self, positions: list[InstitutionalPosition]
    ) -> dict:
        """Classify position changes."""
        threshold = self.config.change_threshold_pct
        result = {"new": 0, "exits": 0, "increases": 0, "decreases": 0}

        for p in positions:
            if p.is_new_position:
                result["new"] += 1
            elif p.is_exit:
                result["exits"] += 1
            elif p.change_pct >= threshold:
                result["increases"] += 1
            elif p.change_pct <= -threshold:
                result["decreases"] += 1

        return result

    def _empty_summary(self, symbol: str) -> InstitutionalSummary:
        return InstitutionalSummary(
            symbol=symbol,
            total_institutional_pct=0.0,
            n_holders=0,
            top_holder="",
            top_holder_pct=0.0,
            concentration=0.0,
            net_change_pct=0.0,
        )
