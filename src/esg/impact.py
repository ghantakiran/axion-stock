"""ESG Impact Tracking."""

import logging
from typing import Optional
from datetime import datetime

from src.esg.config import ImpactCategory
from src.esg.models import ImpactMetric

logger = logging.getLogger(__name__)

# Industry benchmarks (default values)
DEFAULT_BENCHMARKS = {
    ImpactCategory.CARBON_FOOTPRINT: {"value": 200.0, "unit": "tCO2e/$M"},
    ImpactCategory.RENEWABLE_ENERGY: {"value": 30.0, "unit": "%"},
    ImpactCategory.WATER_INTENSITY: {"value": 50.0, "unit": "m3/$M"},
    ImpactCategory.WASTE_RECYCLED: {"value": 40.0, "unit": "%"},
    ImpactCategory.EMPLOYEE_SATISFACTION: {"value": 70.0, "unit": "score"},
    ImpactCategory.GENDER_PAY_GAP: {"value": 15.0, "unit": "%"},
    ImpactCategory.BOARD_INDEPENDENCE: {"value": 65.0, "unit": "%"},
    ImpactCategory.TAX_TRANSPARENCY: {"value": 60.0, "unit": "score"},
}


class ImpactTracker:
    """Tracks and measures ESG impact metrics.

    Features:
    - Record impact metrics by symbol and category
    - Compare against industry benchmarks
    - Track trends over time
    - Portfolio-level impact aggregation
    """

    def __init__(self, benchmarks: Optional[dict] = None):
        self.benchmarks = benchmarks or DEFAULT_BENCHMARKS
        self._metrics: dict[str, dict[ImpactCategory, list[ImpactMetric]]] = {}

    def record_metric(
        self,
        symbol: str,
        category: ImpactCategory,
        value: float,
        unit: Optional[str] = None,
        trend: str = "stable",
    ) -> ImpactMetric:
        """Record an impact metric for a security.

        Args:
            symbol: Security symbol.
            category: Impact category.
            value: Metric value.
            unit: Unit of measurement.
            trend: Trend direction (improving, stable, declining).

        Returns:
            Created ImpactMetric.
        """
        benchmark_info = self.benchmarks.get(category, {})
        benchmark_val = benchmark_info.get("value")
        default_unit = benchmark_info.get("unit", "")

        metric = ImpactMetric(
            category=category,
            value=value,
            unit=unit or default_unit,
            benchmark=benchmark_val,
            trend=trend,
        )

        if symbol not in self._metrics:
            self._metrics[symbol] = {}
        if category not in self._metrics[symbol]:
            self._metrics[symbol][category] = []
        self._metrics[symbol][category].append(metric)

        return metric

    def get_metrics(
        self,
        symbol: str,
        category: Optional[ImpactCategory] = None,
    ) -> list[ImpactMetric]:
        """Get impact metrics for a security.

        Args:
            symbol: Security symbol.
            category: Optional category filter.

        Returns:
            List of ImpactMetric.
        """
        if symbol not in self._metrics:
            return []

        if category:
            return self._metrics[symbol].get(category, [])

        result = []
        for cat_metrics in self._metrics[symbol].values():
            result.extend(cat_metrics)
        return result

    def get_latest_metrics(self, symbol: str) -> dict[ImpactCategory, ImpactMetric]:
        """Get most recent metric for each category.

        Args:
            symbol: Security symbol.

        Returns:
            Dict of category -> latest ImpactMetric.
        """
        latest = {}
        if symbol not in self._metrics:
            return latest

        for category, metrics_list in self._metrics[symbol].items():
            if metrics_list:
                latest[category] = metrics_list[-1]

        return latest

    def portfolio_impact(
        self,
        holdings: dict[str, float],
    ) -> dict[ImpactCategory, ImpactMetric]:
        """Compute weighted portfolio impact metrics.

        Args:
            holdings: Dict of symbol -> weight.

        Returns:
            Dict of category -> weighted ImpactMetric.
        """
        total_weight = sum(holdings.values())
        if total_weight == 0:
            return {}

        category_values: dict[ImpactCategory, list[tuple[float, float]]] = {}

        for symbol, weight in holdings.items():
            norm_weight = weight / total_weight
            latest = self.get_latest_metrics(symbol)

            for category, metric in latest.items():
                if category not in category_values:
                    category_values[category] = []
                category_values[category].append((metric.value, norm_weight))

        result = {}
        for category, values_weights in category_values.items():
            weighted_sum = sum(v * w for v, w in values_weights)
            benchmark_info = self.benchmarks.get(category, {})

            result[category] = ImpactMetric(
                category=category,
                value=round(weighted_sum, 2),
                unit=benchmark_info.get("unit", ""),
                benchmark=benchmark_info.get("value"),
            )

        return result

    def get_tracked_symbols(self) -> list[str]:
        """Get all symbols with impact metrics."""
        return list(self._metrics.keys())
