"""Sector Breadth Analyzer.

Computes breadth metrics per GICS sector and ranks
sectors by internal strength.
"""

import logging
from typing import Optional

from src.breadth.config import GICS_SECTORS
from src.breadth.models import SectorBreadth

logger = logging.getLogger(__name__)


class SectorBreadthAnalyzer:
    """Analyzes market breadth broken down by sector.

    Tracks per-sector advancing/declining counts and
    computes sector rankings by breadth strength.
    """

    def __init__(self) -> None:
        self._history: dict[str, list[SectorBreadth]] = {}

    def compute_sector_breadth(
        self,
        sector_data: dict[str, dict[str, int]],
    ) -> list[SectorBreadth]:
        """Compute breadth metrics per sector.

        Args:
            sector_data: Dict mapping sector name to
                {"advancing": int, "declining": int, "unchanged": int}.

        Returns:
            List of SectorBreadth sorted by breadth_score descending.
        """
        results: list[SectorBreadth] = []

        for sector, data in sector_data.items():
            adv = data.get("advancing", 0)
            dec = data.get("declining", 0)
            unch = data.get("unchanged", 0)
            total = adv + dec
            pct_adv = (adv / total * 100) if total > 0 else 50.0

            # Breadth score: map pct_advancing to 0-100
            breadth_score = pct_adv

            # Momentum: compare to previous
            momentum = "flat"
            if sector in self._history and self._history[sector]:
                prev = self._history[sector][-1]
                if breadth_score > prev.breadth_score + 5:
                    momentum = "improving"
                elif breadth_score < prev.breadth_score - 5:
                    momentum = "deteriorating"

            sb = SectorBreadth(
                sector=sector,
                advancing=adv,
                declining=dec,
                unchanged=unch,
                pct_advancing=round(pct_adv, 1),
                net_advances=adv - dec,
                breadth_score=round(breadth_score, 1),
                momentum=momentum,
            )
            results.append(sb)

            # Record history
            self._history.setdefault(sector, [])
            self._history[sector].append(sb)
            # Keep last 20
            if len(self._history[sector]) > 20:
                self._history[sector] = self._history[sector][-20:]

        # Sort by score descending
        results.sort(key=lambda s: s.breadth_score, reverse=True)
        return results

    def rank_sectors(
        self,
        sector_breadth: list[SectorBreadth],
    ) -> list[tuple[str, float, str]]:
        """Rank sectors by breadth strength.

        Args:
            sector_breadth: List of SectorBreadth objects.

        Returns:
            List of (sector, score, momentum) tuples, ranked.
        """
        sorted_sectors = sorted(sector_breadth, key=lambda s: s.breadth_score, reverse=True)
        return [(s.sector, s.breadth_score, s.momentum) for s in sorted_sectors]

    def get_strongest_sectors(
        self,
        sector_breadth: list[SectorBreadth],
        n: int = 3,
    ) -> list[SectorBreadth]:
        """Get the N strongest sectors by breadth.

        Args:
            sector_breadth: Breadth data.
            n: Number of top sectors.

        Returns:
            Top N sectors.
        """
        sorted_sectors = sorted(sector_breadth, key=lambda s: s.breadth_score, reverse=True)
        return sorted_sectors[:n]

    def get_weakest_sectors(
        self,
        sector_breadth: list[SectorBreadth],
        n: int = 3,
    ) -> list[SectorBreadth]:
        """Get the N weakest sectors by breadth.

        Args:
            sector_breadth: Breadth data.
            n: Number of bottom sectors.

        Returns:
            Bottom N sectors.
        """
        sorted_sectors = sorted(sector_breadth, key=lambda s: s.breadth_score)
        return sorted_sectors[:n]

    def get_improving_sectors(
        self,
        sector_breadth: list[SectorBreadth],
    ) -> list[SectorBreadth]:
        """Get sectors with improving breadth momentum."""
        return [s for s in sector_breadth if s.momentum == "improving"]

    def get_deteriorating_sectors(
        self,
        sector_breadth: list[SectorBreadth],
    ) -> list[SectorBreadth]:
        """Get sectors with deteriorating breadth momentum."""
        return [s for s in sector_breadth if s.momentum == "deteriorating"]

    def clear_history(self) -> None:
        """Clear sector history."""
        self._history.clear()
