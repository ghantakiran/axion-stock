"""Lead-Lag Detector.

Identifies predictive relationships between asset return series
using cross-correlation analysis and stability assessment.
"""

import logging
from typing import Optional

import numpy as np

from src.crossasset.config import LeadLagConfig
from src.crossasset.models import LeadLagResult

logger = logging.getLogger(__name__)


class LeadLagDetector:
    """Detects lead-lag relationships between assets."""

    def __init__(self, config: Optional[LeadLagConfig] = None) -> None:
        self.config = config or LeadLagConfig()

    def detect(
        self,
        returns_a: list[float],
        returns_b: list[float],
        asset_a: str = "A",
        asset_b: str = "B",
    ) -> LeadLagResult:
        """Detect lead-lag relationship between two return series.

        Positive optimal_lag means A leads B by that many periods.
        Negative optimal_lag means B leads A.

        Args:
            returns_a: Return series for asset A.
            returns_b: Return series for asset B.
            asset_a: Asset A label.
            asset_b: Asset B label.

        Returns:
            LeadLagResult.
        """
        min_len = min(len(returns_a), len(returns_b))
        max_lag = self.config.max_lag

        if min_len < max_lag * 3:
            return LeadLagResult(leader=asset_a, lagger=asset_b)

        a = np.array(returns_a[-min_len:])
        b = np.array(returns_b[-min_len:])

        # Normalize
        a_norm = (a - np.mean(a)) / (np.std(a, ddof=1) + 1e-10)
        b_norm = (b - np.mean(b)) / (np.std(b, ddof=1) + 1e-10)

        # Cross-correlation at various lags
        best_lag = 0
        best_corr = 0.0
        lag_corrs = {}

        for lag in range(-max_lag, max_lag + 1):
            if lag > 0:
                # A leads: correlate a[:-lag] with b[lag:]
                corr = np.mean(a_norm[:-lag] * b_norm[lag:])
            elif lag < 0:
                # B leads: correlate a[-lag:] with b[:lag]
                corr = np.mean(a_norm[-lag:] * b_norm[:lag])
            else:
                corr = np.mean(a_norm * b_norm)

            lag_corrs[lag] = float(corr)

            if abs(corr) > abs(best_corr):
                best_corr = corr
                best_lag = lag

        # Significance: compare best lag correlation to zero-lag
        zero_corr = lag_corrs.get(0, 0.0)
        is_significant = (
            abs(best_corr) > self.config.min_correlation
            and abs(best_corr) > abs(zero_corr) + 0.02
            and best_lag != 0
        )

        # Determine leader/lagger
        if best_lag > 0:
            leader, lagger = asset_a, asset_b
        elif best_lag < 0:
            leader, lagger = asset_b, asset_a
            best_lag = abs(best_lag)
        else:
            leader, lagger = asset_a, asset_b

        # Stability: check consistency over sub-periods
        stability = self._compute_stability(a, b, best_lag, min_len)

        return LeadLagResult(
            leader=leader,
            lagger=lagger,
            optimal_lag=best_lag,
            correlation_at_lag=round(float(best_corr), 4),
            is_significant=is_significant,
            stability=round(stability, 4),
        )

    def detect_all_pairs(
        self, returns: dict[str, list[float]]
    ) -> list[LeadLagResult]:
        """Detect lead-lag for all asset pairs.

        Args:
            returns: Dict of {asset: return_series}.

        Returns:
            List of LeadLagResult for significant pairs, sorted by correlation.
        """
        assets = list(returns.keys())
        results = []

        for i in range(len(assets)):
            for j in range(i + 1, len(assets)):
                result = self.detect(
                    returns[assets[i]],
                    returns[assets[j]],
                    assets[i],
                    assets[j],
                )
                if result.is_significant:
                    results.append(result)

        results.sort(key=lambda x: abs(x.correlation_at_lag), reverse=True)
        return results

    def extract_signal(
        self,
        leader_returns: list[float],
        lag: int,
    ) -> float:
        """Extract directional signal from a leading indicator.

        Uses the leader's recent return as a signal for the lagger.

        Args:
            leader_returns: Return series for the leading asset.
            lag: Number of periods the leader leads by.

        Returns:
            Signal value (positive = bullish for lagger).
        """
        if not leader_returns or lag <= 0:
            return 0.0

        # Use the average of the last `lag` returns as the signal
        recent = leader_returns[-lag:]
        return round(float(np.mean(recent)), 6)

    def _compute_stability(
        self, a: np.ndarray, b: np.ndarray, lag: int, total_len: int
    ) -> float:
        """Compute stability of lead-lag relationship over sub-periods."""
        if lag == 0:
            return 0.0

        window = self.config.stability_window
        if total_len < window * 2:
            return 0.5

        # Split into non-overlapping chunks
        n_chunks = total_len // window
        if n_chunks < 2:
            return 0.5

        consistent = 0
        for chunk in range(n_chunks):
            start = chunk * window
            end = start + window
            a_chunk = a[start:end]
            b_chunk = b[start:end]

            if len(a_chunk) <= lag:
                continue

            if lag > 0:
                corr = np.corrcoef(a_chunk[:-lag], b_chunk[lag:])[0, 1]
            else:
                corr = np.corrcoef(a_chunk, b_chunk)[0, 1]

            if not np.isnan(corr) and abs(corr) > self.config.min_correlation:
                consistent += 1

        return consistent / n_chunks if n_chunks > 0 else 0.0
