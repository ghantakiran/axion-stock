"""Intermarket Relationship Analyzer.

Computes rolling correlations, detects correlation regimes,
measures relative strength, and identifies divergences between
asset classes.
"""

import logging
from typing import Optional

import numpy as np

from src.crossasset.config import IntermarketConfig, CorrelationRegime
from src.crossasset.models import AssetPairCorrelation, RelativeStrength

logger = logging.getLogger(__name__)


class IntermarketAnalyzer:
    """Analyzes relationships between asset classes."""

    def __init__(self, config: Optional[IntermarketConfig] = None) -> None:
        self.config = config or IntermarketConfig()

    def rolling_correlation(
        self,
        returns_a: list[float],
        returns_b: list[float],
        asset_a: str = "A",
        asset_b: str = "B",
    ) -> AssetPairCorrelation:
        """Compute rolling correlation between two return series.

        Args:
            returns_a: Return series for asset A.
            returns_b: Return series for asset B.
            asset_a: Asset A label.
            asset_b: Asset B label.

        Returns:
            AssetPairCorrelation.
        """
        min_len = min(len(returns_a), len(returns_b))
        if min_len < self.config.correlation_window:
            return AssetPairCorrelation(asset_a=asset_a, asset_b=asset_b)

        a = np.array(returns_a[-min_len:])
        b = np.array(returns_b[-min_len:])

        # Short-term rolling correlation
        w = self.config.correlation_window
        short_corr = np.corrcoef(a[-w:], b[-w:])[0, 1]

        # Long-term correlation
        lw = min(self.config.long_window, min_len)
        long_corr = np.corrcoef(a[-lw:], b[-lw:])[0, 1]

        # Z-score of current vs long-term
        # Compute rolling correlations for z-score
        corrs = []
        for i in range(w, min_len + 1):
            c = np.corrcoef(a[i - w : i], b[i - w : i])[0, 1]
            if not np.isnan(c):
                corrs.append(c)

        z_score = 0.0
        if len(corrs) > 1:
            mean_c = np.mean(corrs)
            std_c = np.std(corrs, ddof=1)
            if std_c > 0:
                z_score = (short_corr - mean_c) / std_c

        # Correlation regime
        regime = self._classify_regime(short_corr, long_corr)

        # Beta: cov(a,b) / var(b)
        cov_ab = np.cov(a[-w:], b[-w:])[0, 1]
        var_b = np.var(b[-w:], ddof=1)
        beta = cov_ab / var_b if var_b > 0 else 0.0

        return AssetPairCorrelation(
            asset_a=asset_a,
            asset_b=asset_b,
            correlation=round(float(short_corr), 4),
            long_term_correlation=round(float(long_corr), 4),
            z_score=round(float(z_score), 4),
            regime=regime,
            beta=round(float(beta), 4),
        )

    def relative_strength(
        self,
        prices: dict[str, list[float]],
        benchmark: str = "",
        window: int = 63,
    ) -> list[RelativeStrength]:
        """Compute relative strength across assets.

        Args:
            prices: Dict of {asset_name: price_series}.
            benchmark: Benchmark asset name (if empty, uses equal-weighted).
            window: Lookback window for ratio change.

        Returns:
            List of RelativeStrength, sorted by rank.
        """
        if not prices:
            return []

        # Compute returns over window
        changes = {}
        for name, px in prices.items():
            if len(px) > window:
                change = (px[-1] / px[-window - 1]) - 1 if px[-window - 1] != 0 else 0.0
                changes[name] = change
            elif len(px) >= 2:
                change = (px[-1] / px[0]) - 1 if px[0] != 0 else 0.0
                changes[name] = change

        if not changes:
            return []

        # Benchmark return
        if benchmark and benchmark in changes:
            bm_return = changes[benchmark]
        else:
            bm_return = np.mean(list(changes.values()))
            benchmark = "equal_weighted"

        # Rank by return
        sorted_assets = sorted(changes.items(), key=lambda x: x[1], reverse=True)

        results = []
        for rank, (name, ret) in enumerate(sorted_assets, 1):
            ratio = (1 + ret) / (1 + bm_return) if (1 + bm_return) != 0 else 1.0
            ratio_change = ret - bm_return

            if ratio_change > 0.02:
                trend = "outperforming"
            elif ratio_change < -0.02:
                trend = "underperforming"
            else:
                trend = "neutral"

            results.append(RelativeStrength(
                asset=name,
                benchmark=benchmark,
                ratio=round(ratio, 4),
                ratio_change_pct=round(ratio_change * 100, 2),
                trend=trend,
                rank=rank,
            ))

        return results

    def detect_divergence(
        self,
        returns_a: list[float],
        returns_b: list[float],
        asset_a: str = "A",
        asset_b: str = "B",
    ) -> dict:
        """Detect correlation divergence between two assets.

        Returns:
            Dict with divergence info.
        """
        corr_result = self.rolling_correlation(returns_a, returns_b, asset_a, asset_b)

        is_diverging = abs(corr_result.z_score) > self.config.divergence_threshold
        direction = "weakening" if corr_result.z_score < 0 else "strengthening"

        return {
            "asset_a": asset_a,
            "asset_b": asset_b,
            "is_diverging": is_diverging,
            "direction": direction if is_diverging else "stable",
            "z_score": corr_result.z_score,
            "current_correlation": corr_result.correlation,
            "long_term_correlation": corr_result.long_term_correlation,
        }

    def correlation_matrix(
        self, returns: dict[str, list[float]], window: Optional[int] = None
    ) -> dict[str, dict[str, float]]:
        """Compute correlation matrix across all assets.

        Args:
            returns: Dict of {asset: return_series}.
            window: Optional window (default: config.correlation_window).

        Returns:
            Nested dict of correlations.
        """
        w = window or self.config.correlation_window
        assets = list(returns.keys())
        matrix: dict[str, dict[str, float]] = {}

        for a in assets:
            matrix[a] = {}
            for b in assets:
                if a == b:
                    matrix[a][b] = 1.0
                    continue
                ra = returns[a]
                rb = returns[b]
                min_len = min(len(ra), len(rb))
                if min_len >= w:
                    c = np.corrcoef(ra[-w:], rb[-w:])[0, 1]
                    matrix[a][b] = round(float(c), 4)
                else:
                    matrix[a][b] = 0.0

        return matrix

    def _classify_regime(self, short_corr: float, long_corr: float) -> str:
        """Classify correlation regime."""
        if abs(short_corr) >= self.config.crisis_correlation_threshold:
            return CorrelationRegime.CRISIS.value
        if abs(short_corr) <= self.config.decoupled_correlation_threshold:
            return CorrelationRegime.DECOUPLED.value
        return CorrelationRegime.NORMAL.value
