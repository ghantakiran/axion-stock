"""Macro Factor Model.

Constructs macro factors, estimates exposures,
decomposes returns, and computes regime-conditional behavior.
"""

import logging
from typing import Optional

import numpy as np

from src.macro.config import FactorConfig, MacroFactor, RegimeType, DEFAULT_FACTOR_CONFIG
from src.macro.models import MacroFactorResult

logger = logging.getLogger(__name__)


class MacroFactorModel:
    """Builds and analyzes macro factor models."""

    def __init__(self, config: Optional[FactorConfig] = None) -> None:
        self.config = config or DEFAULT_FACTOR_CONFIG

    def compute_factors(
        self,
        factor_series: dict[str, list[float]],
        regime: Optional[RegimeType] = None,
    ) -> MacroFactorResult:
        """Compute macro factor returns and exposures.

        Args:
            factor_series: Dict of factor_name -> time series of values.
            regime: Optional current regime for conditional analysis.

        Returns:
            MacroFactorResult with returns, exposures, momentum.
        """
        if not factor_series:
            return self._empty_result()

        factor_returns = {}
        factor_exposures = {}
        factor_momentum = {}

        for name, series in factor_series.items():
            arr = np.array(series, dtype=float)
            if len(arr) < 2:
                factor_returns[name] = 0.0
                factor_exposures[name] = 0.0
                factor_momentum[name] = 0.0
                continue

            # Recent return (latest period)
            factor_returns[name] = round(float(arr[-1] - arr[-2]), 6)

            # Exposure: z-score of current value
            factor_exposures[name] = round(self._zscore_latest(arr), 4)

            # Momentum: trend over momentum window
            factor_momentum[name] = round(self._compute_momentum(arr), 4)

        # Dominant factor: highest absolute exposure
        dominant = max(factor_exposures, key=lambda k: abs(factor_exposures[k]))

        # Regime-conditional returns
        regime_conditional = {}
        if regime is not None:
            regime_conditional[regime.value] = factor_returns.copy()

        return MacroFactorResult(
            factor_returns=factor_returns,
            factor_exposures=factor_exposures,
            factor_momentum=factor_momentum,
            regime_conditional=regime_conditional,
            dominant_factor=dominant,
        )

    def decompose_returns(
        self,
        asset_returns: np.ndarray,
        factor_matrix: np.ndarray,
    ) -> dict[str, float]:
        """Decompose asset returns into factor contributions.

        Args:
            asset_returns: Array of asset returns.
            factor_matrix: Matrix of factor returns (n_periods x n_factors).

        Returns:
            Dict of factor_name -> contribution.
        """
        if len(asset_returns) < self.config.min_observations:
            return {}
        if factor_matrix.shape[0] != len(asset_returns):
            return {}

        # OLS regression: r_asset = alpha + beta @ factors + epsilon
        n_factors = factor_matrix.shape[1]
        X = np.column_stack([np.ones(len(asset_returns)), factor_matrix])

        try:
            beta, _, _, _ = np.linalg.lstsq(X, asset_returns, rcond=None)
        except np.linalg.LinAlgError:
            return {}

        # Factor contributions = beta * mean_factor_return
        contributions = {}
        factor_names = self.config.factors[:n_factors]
        for i, name in enumerate(factor_names):
            mean_return = float(np.mean(factor_matrix[:, i]))
            contributions[name] = round(beta[i + 1] * mean_return, 6)

        contributions["alpha"] = round(float(beta[0]), 6)
        return contributions

    def regime_factor_profile(
        self,
        factor_series: dict[str, list[float]],
        regime_labels: list[RegimeType],
    ) -> dict[str, dict[str, float]]:
        """Compute average factor returns per regime.

        Args:
            factor_series: Factor time series.
            regime_labels: Regime label per period.

        Returns:
            Dict of regime -> {factor -> avg_return}.
        """
        result: dict[str, dict[str, float]] = {}

        for regime in RegimeType:
            regime_returns: dict[str, float] = {}
            for name, series in factor_series.items():
                arr = np.array(series, dtype=float)
                n = min(len(arr), len(regime_labels))
                mask = [regime_labels[i] == regime for i in range(n)]
                if any(mask):
                    regime_returns[name] = round(float(np.mean(arr[:n][mask])), 6)
                else:
                    regime_returns[name] = 0.0
            result[regime.value] = regime_returns

        return result

    def _zscore_latest(self, arr: np.ndarray) -> float:
        """Z-score of latest value relative to full history."""
        if len(arr) < 2:
            return 0.0
        std = np.std(arr)
        if std == 0:
            return 0.0
        return float((arr[-1] - np.mean(arr)) / std)

    def _compute_momentum(self, arr: np.ndarray) -> float:
        """Compute factor momentum via linear regression slope."""
        window = min(self.config.momentum_window, len(arr))
        recent = arr[-window:]
        if len(recent) < 2:
            return 0.0

        x = np.arange(len(recent), dtype=float)
        x_mean = np.mean(x)
        y_mean = np.mean(recent)

        num = np.sum((x - x_mean) * (recent - y_mean))
        den = np.sum((x - x_mean) ** 2)

        if den == 0:
            return 0.0
        slope = num / den
        if y_mean != 0:
            return float(slope / abs(y_mean))
        return float(slope)

    def _empty_result(self) -> MacroFactorResult:
        return MacroFactorResult(
            factor_returns={},
            factor_exposures={},
            factor_momentum={},
        )
