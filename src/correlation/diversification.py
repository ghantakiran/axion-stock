"""Diversification Analysis.

Scores portfolio diversification quality using correlation-based
metrics: diversification ratio, effective number of bets,
and concentrated pair identification.
"""

import logging
from datetime import date
from typing import Optional

import numpy as np

from src.correlation.config import (
    DiversificationConfig,
    DiversificationLevel,
    DEFAULT_DIVERSIFICATION_CONFIG,
)
from src.correlation.models import (
    CorrelationMatrix,
    CorrelationPair,
    DiversificationScore,
)

logger = logging.getLogger(__name__)


class DiversificationAnalyzer:
    """Analyzes portfolio diversification quality.

    Computes diversification ratio, effective number of bets,
    and identifies concentrated correlation risks.
    """

    def __init__(self, config: Optional[DiversificationConfig] = None) -> None:
        self.config = config or DEFAULT_DIVERSIFICATION_CONFIG

    def score(
        self,
        matrix: CorrelationMatrix,
        weights: Optional[dict[str, float]] = None,
        volatilities: Optional[dict[str, float]] = None,
    ) -> DiversificationScore:
        """Compute diversification score for a portfolio.

        Args:
            matrix: Correlation matrix.
            weights: Portfolio weights by symbol. Defaults to equal weight.
            volatilities: Asset volatilities by symbol. Defaults to equal.

        Returns:
            DiversificationScore assessment.
        """
        n = matrix.n_assets
        if n < 2 or matrix.values is None:
            return DiversificationScore(n_assets=n)

        symbols = matrix.symbols

        # Default to equal weights
        if weights is None:
            w = np.ones(n) / n
        else:
            w = np.array([weights.get(s, 1.0 / n) for s in symbols])
            w = w / w.sum()  # Normalize

        # Default to equal volatilities
        if volatilities is None:
            vols = np.ones(n) * 0.20  # 20% default
        else:
            vols = np.array([volatilities.get(s, 0.20) for s in symbols])

        # Diversification ratio = weighted avg vol / portfolio vol
        weighted_avg_vol = float(np.dot(w, vols))
        cov_matrix = np.outer(vols, vols) * matrix.values
        port_var = float(w @ cov_matrix @ w)
        port_vol = np.sqrt(max(0, port_var))

        div_ratio = weighted_avg_vol / port_vol if port_vol > 0 else 1.0

        # Effective number of bets (ENB)
        # Based on eigenvalue decomposition of weighted correlation
        eigenvalues = np.linalg.eigvalsh(matrix.values)
        eigenvalues = eigenvalues[eigenvalues > 0]
        if len(eigenvalues) > 0:
            p = eigenvalues / eigenvalues.sum()
            enb = float(np.exp(-np.sum(p * np.log(p + 1e-10))))
        else:
            enb = 1.0

        # Pair analysis
        avg_corr = matrix.avg_correlation
        max_corr = matrix.max_correlation

        # Find max pair
        max_pair = ("", "")
        max_pair_val = 0.0
        highly_correlated: list[CorrelationPair] = []

        for i in range(n):
            for j in range(i + 1, n):
                corr = float(matrix.values[i, j])
                if abs(corr) > abs(max_pair_val):
                    max_pair_val = corr
                    max_pair = (symbols[i], symbols[j])

                if abs(corr) >= self.config.max_pair_correlation:
                    highly_correlated.append(CorrelationPair(
                        symbol_a=symbols[i],
                        symbol_b=symbols[j],
                        correlation=round(corr, 4),
                        method=matrix.method,
                    ))

        highly_correlated.sort(key=lambda p: abs(p.correlation), reverse=True)

        # Classify
        level = self._classify(div_ratio)

        return DiversificationScore(
            date=matrix.end_date or date.today(),
            diversification_ratio=round(div_ratio, 3),
            effective_n_bets=round(enb, 1),
            avg_pair_correlation=round(avg_corr, 4),
            max_pair_correlation=round(max_pair_val, 4),
            max_pair=max_pair,
            level=level,
            n_assets=n,
            highly_correlated_pairs=highly_correlated,
        )

    def _classify(self, div_ratio: float) -> DiversificationLevel:
        """Classify diversification ratio into level."""
        if div_ratio >= self.config.excellent_threshold:
            return DiversificationLevel.EXCELLENT
        elif div_ratio >= self.config.good_threshold:
            return DiversificationLevel.GOOD
        elif div_ratio >= self.config.fair_threshold:
            return DiversificationLevel.FAIR
        else:
            return DiversificationLevel.POOR

    def compare_portfolios(
        self,
        scores: dict[str, DiversificationScore],
    ) -> dict[str, dict]:
        """Compare diversification across multiple portfolios.

        Args:
            scores: Dict mapping portfolio name to DiversificationScore.

        Returns:
            Comparison summary with rankings.
        """
        if not scores:
            return {}

        ranked = sorted(
            scores.items(),
            key=lambda x: x[1].diversification_ratio,
            reverse=True,
        )

        return {
            "ranking": [(name, s.diversification_ratio) for name, s in ranked],
            "best": ranked[0][0] if ranked else "",
            "worst": ranked[-1][0] if ranked else "",
            "portfolios": {name: s.to_dict() for name, s in scores.items()},
        }
