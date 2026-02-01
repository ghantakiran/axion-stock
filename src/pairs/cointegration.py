"""Cointegration Testing for Pairs Trading.

Implements Engle-Granger two-step cointegration test,
hedge ratio estimation, and ADF stationarity testing.
"""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from src.pairs.config import (
    CointegrationConfig,
    PairStatus,
    DEFAULT_COINTEGRATION_CONFIG,
)
from src.pairs.models import CointegrationResult

logger = logging.getLogger(__name__)


# Critical values for ADF test (approximations for n>250)
# 1%, 5%, 10% significance levels
_ADF_CRITICAL = {0.01: -3.43, 0.05: -2.86, 0.10: -2.57}


class CointegrationTester:
    """Tests cointegration between asset pairs."""

    def __init__(self, config: Optional[CointegrationConfig] = None) -> None:
        self.config = config or DEFAULT_COINTEGRATION_CONFIG

    def test_pair(
        self,
        prices_a: pd.Series,
        prices_b: pd.Series,
        asset_a: str = "",
        asset_b: str = "",
    ) -> CointegrationResult:
        """Test cointegration between two price series.

        Uses Engle-Granger two-step method:
        1. Regress A on B to get hedge ratio
        2. Test residuals for stationarity via ADF

        Args:
            prices_a: Price series for asset A.
            prices_b: Price series for asset B.
            asset_a: Asset A symbol.
            asset_b: Asset B symbol.

        Returns:
            CointegrationResult with test statistics.
        """
        n = min(len(prices_a), len(prices_b))
        if n < self.config.lookback_window:
            window = n
        else:
            window = self.config.lookback_window

        a = prices_a.values[-window:].astype(float)
        b = prices_b.values[-window:].astype(float)

        # Correlation check
        corr = float(np.corrcoef(a, b)[0, 1])

        if abs(corr) < self.config.min_correlation:
            return CointegrationResult(
                asset_a=asset_a,
                asset_b=asset_b,
                correlation=round(corr, 4),
                status=PairStatus.NOT_COINTEGRATED,
                pvalue=1.0,
            )

        # Step 1: OLS regression A = beta * B + alpha + epsilon
        hedge_ratio, intercept = self._compute_hedge_ratio(a, b)

        # Step 2: Compute residuals (spread)
        residuals = a - hedge_ratio * b - intercept

        # Step 3: ADF test on residuals
        adf_stat, pvalue = self._adf_test(residuals)

        # Classify
        status = self._classify(pvalue)

        return CointegrationResult(
            asset_a=asset_a,
            asset_b=asset_b,
            test_statistic=round(adf_stat, 4),
            pvalue=round(pvalue, 4),
            hedge_ratio=round(hedge_ratio, 6),
            intercept=round(intercept, 6),
            correlation=round(corr, 4),
            status=status,
        )

    def test_universe(
        self,
        prices: pd.DataFrame,
    ) -> list[CointegrationResult]:
        """Test all pairs in a price universe.

        Args:
            prices: DataFrame with columns as asset symbols, rows as dates.

        Returns:
            List of CointegrationResult for all pairs tested.
        """
        symbols = list(prices.columns)
        results: list[CointegrationResult] = []

        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                result = self.test_pair(
                    prices[symbols[i]], prices[symbols[j]],
                    asset_a=symbols[i], asset_b=symbols[j],
                )
                results.append(result)

        return results

    def _compute_hedge_ratio(
        self,
        a: np.ndarray,
        b: np.ndarray,
    ) -> tuple[float, float]:
        """OLS hedge ratio: A = beta * B + alpha."""
        n = len(a)
        b_mean = b.mean()
        a_mean = a.mean()

        cov = np.sum((b - b_mean) * (a - a_mean))
        var = np.sum((b - b_mean) ** 2)

        if var == 0:
            return 1.0, 0.0

        beta = cov / var
        alpha = a_mean - beta * b_mean
        return float(beta), float(alpha)

    def _adf_test(self, residuals: np.ndarray) -> tuple[float, float]:
        """Augmented Dickey-Fuller test on residuals.

        Tests H0: unit root (non-stationary) vs H1: stationary.
        Uses OLS: delta_y = gamma * y_{t-1} + sum(phi_i * delta_y_{t-i}) + eps

        Returns:
            (test_statistic, approximate_pvalue)
        """
        n = len(residuals)
        max_lags = min(self.config.adf_max_lags, n // 4)

        # Best lag by AIC
        best_stat = 0.0
        best_aic = float("inf")

        for lags in range(0, max_lags + 1):
            stat, aic = self._adf_regression(residuals, lags)
            if aic < best_aic:
                best_aic = aic
                best_stat = stat

        # Approximate p-value from critical values
        pvalue = self._adf_pvalue(best_stat)

        return best_stat, pvalue

    def _adf_regression(
        self,
        y: np.ndarray,
        lags: int,
    ) -> tuple[float, float]:
        """Run single ADF regression with given lag count."""
        n = len(y)
        dy = np.diff(y)

        # Build regressors
        start = lags + 1
        if start >= n - 1:
            return 0.0, float("inf")

        Y = dy[start - 1:]
        X_cols = [y[start - 1: n - 1]]  # y_{t-1}

        for lag in range(1, lags + 1):
            X_cols.append(dy[start - 1 - lag: n - 1 - lag])

        # Add constant
        T = len(Y)
        X = np.column_stack([np.ones(T)] + X_cols)

        # OLS
        try:
            XtX_inv = np.linalg.inv(X.T @ X)
            beta = XtX_inv @ X.T @ Y
            residuals = Y - X @ beta
            sse = float(np.sum(residuals ** 2))
            sigma2 = sse / (T - X.shape[1])

            # t-statistic for gamma (coefficient on y_{t-1}, index 1)
            se_gamma = float(np.sqrt(sigma2 * XtX_inv[1, 1]))
            if se_gamma == 0:
                return 0.0, float("inf")

            t_stat = float(beta[1]) / se_gamma

            # AIC
            k = X.shape[1]
            aic = T * np.log(sse / T) + 2 * k

            return t_stat, float(aic)
        except np.linalg.LinAlgError:
            return 0.0, float("inf")

    def _adf_pvalue(self, stat: float) -> float:
        """Approximate p-value from ADF statistic using critical values."""
        if stat <= _ADF_CRITICAL[0.01]:
            return 0.005
        elif stat <= _ADF_CRITICAL[0.05]:
            # Linear interpolation between 1% and 5%
            frac = (stat - _ADF_CRITICAL[0.01]) / (_ADF_CRITICAL[0.05] - _ADF_CRITICAL[0.01])
            return 0.01 + frac * 0.04
        elif stat <= _ADF_CRITICAL[0.10]:
            frac = (stat - _ADF_CRITICAL[0.05]) / (_ADF_CRITICAL[0.10] - _ADF_CRITICAL[0.05])
            return 0.05 + frac * 0.05
        else:
            # Above 10% critical value
            return min(1.0, 0.10 + (stat - _ADF_CRITICAL[0.10]) * 0.2)

    def _classify(self, pvalue: float) -> PairStatus:
        """Classify pair status from p-value."""
        if pvalue <= self.config.pvalue_threshold:
            return PairStatus.COINTEGRATED
        elif pvalue <= self.config.pvalue_threshold * 2:
            return PairStatus.WEAK
        return PairStatus.NOT_COINTEGRATED
