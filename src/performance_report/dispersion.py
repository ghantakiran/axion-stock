"""Internal dispersion calculations for GIPS composites."""

import math
from typing import List, Optional

from .config import DispersionMethod, MIN_PORTFOLIOS_DISPERSION
from .models import DispersionResult, PerformanceRecord


class DispersionCalculator:
    """Calculates internal dispersion for GIPS composite presentations."""

    def __init__(self, method: DispersionMethod = DispersionMethod.ASSET_WEIGHTED_STD):
        self.method = method

    def calculate(
        self,
        records: List[PerformanceRecord],
        method: Optional[DispersionMethod] = None,
    ) -> DispersionResult:
        """Calculate dispersion across portfolio returns within a composite."""
        use_method = method or self.method
        returns = [r.gross_return for r in records]
        n = len(returns)

        is_meaningful = n >= MIN_PORTFOLIOS_DISPERSION

        if n < 2:
            return DispersionResult(
                method=use_method.value,
                value=0.0,
                n_portfolios=n,
                is_meaningful=False,
            )

        sorted_returns = sorted(returns)
        high = sorted_returns[-1]
        low = sorted_returns[0]
        median = sorted_returns[n // 2] if n % 2 else (sorted_returns[n // 2 - 1] + sorted_returns[n // 2]) / 2

        if use_method == DispersionMethod.HIGH_LOW_RANGE:
            value = high - low
        elif use_method == DispersionMethod.INTERQUARTILE:
            q1_idx = n // 4
            q3_idx = 3 * n // 4
            value = sorted_returns[q3_idx] - sorted_returns[q1_idx]
        elif use_method == DispersionMethod.EQUAL_WEIGHTED_STD:
            value = self._equal_weighted_std(returns)
        else:  # ASSET_WEIGHTED_STD
            value = self._asset_weighted_std(records)

        return DispersionResult(
            method=use_method.value,
            value=value,
            n_portfolios=n,
            high=high,
            low=low,
            median=median,
            is_meaningful=is_meaningful,
        )

    def _equal_weighted_std(self, returns: List[float]) -> float:
        n = len(returns)
        if n < 2:
            return 0.0
        mean = sum(returns) / n
        variance = sum((r - mean) ** 2 for r in returns) / (n - 1)
        return math.sqrt(variance)

    def _asset_weighted_std(self, records: List[PerformanceRecord]) -> float:
        total_weight = sum(r.beginning_value for r in records)
        if total_weight <= 0 or len(records) < 2:
            return 0.0

        weighted_mean = sum(r.gross_return * r.beginning_value for r in records) / total_weight

        weighted_var = sum(
            r.beginning_value * (r.gross_return - weighted_mean) ** 2
            for r in records
        ) / total_weight

        return math.sqrt(weighted_var)

    def compare_methods(
        self, records: List[PerformanceRecord]
    ) -> List[DispersionResult]:
        """Calculate dispersion using all available methods."""
        results = []
        for method in DispersionMethod:
            results.append(self.calculate(records, method=method))
        return results
