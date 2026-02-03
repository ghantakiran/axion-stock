"""Tail Dependence Analyzer.

Measures co-movement in the tails of return distributions,
detecting when assets crash together more than normal
correlations would suggest.
"""

import logging
from typing import Optional

import numpy as np

from src.tailrisk.config import DependenceConfig
from src.tailrisk.models import TailDependence

logger = logging.getLogger(__name__)


class TailDependenceAnalyzer:
    """Analyzes tail dependence between assets."""

    def __init__(self, config: Optional[DependenceConfig] = None) -> None:
        self.config = config or DependenceConfig()

    def compute(
        self,
        returns_a: list[float],
        returns_b: list[float],
        asset_a: str = "A",
        asset_b: str = "B",
    ) -> TailDependence:
        """Compute tail dependence coefficients between two assets.

        Lower tail: P(B < q_B | A < q_A) — crash-together probability.
        Upper tail: P(B > q_B | A > q_A) — rally-together probability.

        Args:
            returns_a: Return series for asset A.
            returns_b: Return series for asset B.
            asset_a: Asset A label.
            asset_b: Asset B label.

        Returns:
            TailDependence.
        """
        min_len = min(len(returns_a), len(returns_b))
        if min_len < self.config.min_observations:
            return TailDependence(asset_a=asset_a, asset_b=asset_b)

        a = np.array(returns_a[-min_len:])
        b = np.array(returns_b[-min_len:])

        q = self.config.tail_threshold

        # Lower tail dependence
        qa_low = np.percentile(a, q * 100)
        qb_low = np.percentile(b, q * 100)
        a_in_tail = a <= qa_low
        both_in_lower = (a <= qa_low) & (b <= qb_low)
        lower_tail = both_in_lower.sum() / a_in_tail.sum() if a_in_tail.sum() > 0 else 0.0

        # Upper tail dependence
        qa_high = np.percentile(a, (1 - q) * 100)
        qb_high = np.percentile(b, (1 - q) * 100)
        a_in_upper = a >= qa_high
        both_in_upper = (a >= qa_high) & (b >= qb_high)
        upper_tail = both_in_upper.sum() / a_in_upper.sum() if a_in_upper.sum() > 0 else 0.0

        # Normal (full-sample) correlation
        normal_corr = float(np.corrcoef(a, b)[0, 1])

        # Tail correlation (correlation conditional on both being in extreme quantile)
        extreme_q = self.config.extreme_quantile
        qa_ext = np.percentile(a, extreme_q * 100)
        qb_ext = np.percentile(b, extreme_q * 100)
        extreme_mask = (a <= qa_ext) | (b <= qb_ext)
        if extreme_mask.sum() > 5:
            tail_corr = float(np.corrcoef(a[extreme_mask], b[extreme_mask])[0, 1])
            if np.isnan(tail_corr):
                tail_corr = normal_corr
        else:
            tail_corr = normal_corr

        # Contagion score: how much tail dependence exceeds expectation
        expected_joint = q  # Under independence, P(B<q|A<q) = q
        contagion = (lower_tail - expected_joint) / (1 - expected_joint) if expected_joint < 1 else 0.0
        contagion = max(0.0, contagion)

        return TailDependence(
            asset_a=asset_a,
            asset_b=asset_b,
            lower_tail=round(float(lower_tail), 4),
            upper_tail=round(float(upper_tail), 4),
            normal_correlation=round(normal_corr, 4),
            tail_correlation=round(tail_corr, 4),
            contagion_score=round(float(contagion), 4),
        )

    def compute_all_pairs(
        self, returns: dict[str, list[float]]
    ) -> list[TailDependence]:
        """Compute tail dependence for all asset pairs.

        Args:
            returns: Dict of {asset: return_series}.

        Returns:
            List of TailDependence, sorted by lower_tail descending.
        """
        assets = list(returns.keys())
        results = []

        for i in range(len(assets)):
            for j in range(i + 1, len(assets)):
                td = self.compute(
                    returns[assets[i]], returns[assets[j]],
                    assets[i], assets[j],
                )
                results.append(td)

        results.sort(key=lambda x: x.lower_tail, reverse=True)
        return results

    def contagion_matrix(
        self, returns: dict[str, list[float]]
    ) -> dict[str, dict[str, float]]:
        """Build contagion score matrix.

        Returns:
            Nested dict of {asset_a: {asset_b: contagion_score}}.
        """
        assets = list(returns.keys())
        matrix: dict[str, dict[str, float]] = {a: {} for a in assets}

        for i in range(len(assets)):
            matrix[assets[i]][assets[i]] = 1.0
            for j in range(i + 1, len(assets)):
                td = self.compute(
                    returns[assets[i]], returns[assets[j]],
                    assets[i], assets[j],
                )
                matrix[assets[i]][assets[j]] = td.contagion_score
                matrix[assets[j]][assets[i]] = td.contagion_score

        return matrix
