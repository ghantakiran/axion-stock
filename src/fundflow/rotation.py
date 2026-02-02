"""Sector Rotation Detection.

Aggregates sector-level flows, ranks relative strength,
and identifies rotation patterns across market phases.
"""

import logging
from typing import Optional

import numpy as np

from src.fundflow.config import (
    RotationConfig,
    RotationPhase,
    DEFAULT_ROTATION_CONFIG,
)
from src.fundflow.models import FlowSummary, SectorRotation

logger = logging.getLogger(__name__)


class RotationDetector:
    """Detects sector rotation from fund flows."""

    def __init__(self, config: Optional[RotationConfig] = None) -> None:
        self.config = config or DEFAULT_ROTATION_CONFIG

    def analyze(
        self, sector_flows: dict[str, list[float]]
    ) -> list[SectorRotation]:
        """Detect rotation from sector flow data.

        Args:
            sector_flows: Dict mapping sector name to list of
                daily net flows (most recent last).

        Returns:
            Ranked list of SectorRotation results.
        """
        if not sector_flows:
            return []

        results: list[SectorRotation] = []

        # Compute flow score and momentum for each sector
        scores = {}
        momentums = {}
        for sector, flows in sector_flows.items():
            arr = np.array(flows, dtype=float)
            scores[sector] = self._flow_score(arr)
            momentums[sector] = self._flow_momentum(arr)

        # Normalize scores to z-scores across sectors
        all_scores = np.array(list(scores.values()))
        if len(all_scores) > 1 and np.std(all_scores) > 0:
            mean_s = np.mean(all_scores)
            std_s = np.std(all_scores)
            norm_scores = {s: (v - mean_s) / std_s for s, v in scores.items()}
        else:
            norm_scores = {s: 0.0 for s in scores}

        all_moms = np.array(list(momentums.values()))
        if len(all_moms) > 1 and np.std(all_moms) > 0:
            mean_m = np.mean(all_moms)
            std_m = np.std(all_moms)
            norm_moms = {s: (v - mean_m) / std_m for s, v in momentums.items()}
        else:
            norm_moms = {s: 0.0 for s in momentums}

        # Detect rotation phase
        phase = self._detect_phase(scores, momentums)

        for sector in sector_flows:
            rotation = SectorRotation(
                sector=sector,
                flow_score=round(norm_scores.get(sector, 0.0), 4),
                momentum_score=round(norm_moms.get(sector, 0.0), 4),
                phase=phase,
                relative_strength=round(
                    norm_scores.get(sector, 0.0) + norm_moms.get(sector, 0.0), 4
                ),
            )
            results.append(rotation)

        # Sort and rank by composite score
        results.sort(key=lambda r: r.composite_score, reverse=True)
        for i, r in enumerate(results):
            r.rank = i + 1

        return results

    def _flow_score(self, flows: np.ndarray) -> float:
        """Compute flow score from recent flows.

        Uses exponentially-weighted mean for recency bias.
        """
        if len(flows) == 0:
            return 0.0

        window = min(self.config.momentum_window, len(flows))
        recent = flows[-window:]

        # Exponential weights
        weights = np.exp(np.linspace(-1, 0, len(recent)))
        weights /= weights.sum()

        return float(np.sum(recent * weights))

    def _flow_momentum(self, flows: np.ndarray) -> float:
        """Compute flow momentum (acceleration).

        Compares recent flow average to prior period.
        """
        w = self.config.ranking_window
        if len(flows) < 2:
            return 0.0

        if len(flows) >= 2 * w:
            recent = float(np.mean(flows[-w:]))
            prior = float(np.mean(flows[-2 * w:-w]))
        else:
            half = len(flows) // 2
            recent = float(np.mean(flows[half:]))
            prior = float(np.mean(flows[:half]))

        if prior == 0:
            return 1.0 if recent > 0 else (-1.0 if recent < 0 else 0.0)

        return (recent - prior) / abs(prior)

    def _detect_phase(
        self,
        scores: dict[str, float],
        momentums: dict[str, float],
    ) -> RotationPhase:
        """Detect market rotation phase from sector flow patterns.

        Simplified heuristic:
        - Early cycle: Financials + Consumer Disc leading
        - Mid cycle: Tech + Industrials leading
        - Late cycle: Energy + Materials leading
        - Recession: Utilities + Staples leading
        """
        early_sectors = {"Financials", "Consumer Discretionary"}
        mid_sectors = {"Technology", "Industrials"}
        late_sectors = {"Energy", "Materials"}
        defensive_sectors = {"Utilities", "Consumer Staples", "Healthcare"}

        def avg_score(sector_set: set[str]) -> float:
            vals = [scores.get(s, 0) for s in sector_set if s in scores]
            return float(np.mean(vals)) if vals else 0.0

        phase_scores = {
            RotationPhase.EARLY_CYCLE: avg_score(early_sectors),
            RotationPhase.MID_CYCLE: avg_score(mid_sectors),
            RotationPhase.LATE_CYCLE: avg_score(late_sectors),
            RotationPhase.RECESSION: avg_score(defensive_sectors),
        }

        return max(phase_scores, key=phase_scores.get)

    def detect_divergence(
        self, sector_flows: dict[str, list[float]]
    ) -> dict[str, float]:
        """Detect cross-sector flow divergence.

        Returns dict of sector -> divergence score (std devs from mean).
        """
        if not sector_flows:
            return {}

        totals = {
            s: float(np.sum(flows[-self.config.momentum_window:]))
            for s, flows in sector_flows.items()
            if len(flows) > 0
        }

        if not totals:
            return {}

        values = np.array(list(totals.values()))
        mean_v = np.mean(values)
        std_v = np.std(values)

        if std_v == 0:
            return {s: 0.0 for s in totals}

        return {s: round((v - mean_v) / std_v, 4) for s, v in totals.items()}
