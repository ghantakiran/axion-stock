"""Tear Sheet Generator.

Assembles comprehensive performance reports combining all attribution
and metrics components.
"""

import logging
from typing import Optional

import pandas as pd

from src.attribution.config import (
    TimePeriod,
    AttributionConfig,
    DEFAULT_ATTRIBUTION_CONFIG,
)
from src.attribution.models import (
    TearSheet,
    BrinsonAttribution,
    FactorAttribution,
    BenchmarkComparison,
)
from src.attribution.brinson import BrinsonAnalyzer
from src.attribution.factor_attribution import FactorAnalyzer
from src.attribution.benchmark import BenchmarkAnalyzer
from src.attribution.metrics import MetricsCalculator

logger = logging.getLogger(__name__)


class TearSheetGenerator:
    """Generates comprehensive performance tear sheets.

    Combines metrics, benchmark comparison, Brinson attribution,
    factor attribution, drawdown analysis, and rolling metrics
    into a single report.
    """

    def __init__(self, config: Optional[AttributionConfig] = None) -> None:
        self.config = config or DEFAULT_ATTRIBUTION_CONFIG
        self._metrics = MetricsCalculator(self.config)
        self._benchmark = BenchmarkAnalyzer(self.config)
        self._brinson = BrinsonAnalyzer()
        self._factor = FactorAnalyzer()

    def generate(
        self,
        portfolio_returns: pd.Series,
        benchmark_returns: Optional[pd.Series] = None,
        benchmark_id: str = "SPY",
        benchmark_name: str = "S&P 500",
        portfolio_weights: Optional[dict[str, float]] = None,
        benchmark_weights: Optional[dict[str, float]] = None,
        portfolio_sector_weights: Optional[dict[str, float]] = None,
        benchmark_sector_weights: Optional[dict[str, float]] = None,
        portfolio_sector_returns: Optional[dict[str, float]] = None,
        benchmark_sector_returns: Optional[dict[str, float]] = None,
        factor_exposures: Optional[dict[str, float]] = None,
        factor_returns_dict: Optional[dict[str, float]] = None,
        name: str = "Performance Report",
        period: TimePeriod = TimePeriod.ONE_YEAR,
    ) -> TearSheet:
        """Generate a complete tear sheet.

        Args:
            portfolio_returns: Daily portfolio returns.
            benchmark_returns: Daily benchmark returns.
            benchmark_id: Benchmark identifier.
            benchmark_name: Benchmark display name.
            portfolio_weights: Security-level portfolio weights (for active share).
            benchmark_weights: Security-level benchmark weights (for active share).
            portfolio_sector_weights: Sector weights for Brinson.
            benchmark_sector_weights: Benchmark sector weights for Brinson.
            portfolio_sector_returns: Portfolio return by sector for Brinson.
            benchmark_sector_returns: Benchmark return by sector for Brinson.
            factor_exposures: Factor exposures for factor attribution.
            factor_returns_dict: Factor returns for factor attribution.
            name: Report name.
            period: Time period label.

        Returns:
            Complete TearSheet.
        """
        sheet = TearSheet(name=name, period=period)

        # 1. Performance metrics
        sheet.metrics = self._metrics.compute(portfolio_returns)

        # 2. Benchmark comparison
        if benchmark_returns is not None:
            sheet.benchmark_comparison = self._benchmark.compare(
                portfolio_returns, benchmark_returns,
                benchmark_id=benchmark_id,
                benchmark_name=benchmark_name,
                portfolio_weights=portfolio_weights,
                benchmark_weights=benchmark_weights,
            )

        # 3. Brinson attribution
        if (
            portfolio_sector_weights
            and benchmark_sector_weights
            and portfolio_sector_returns
            and benchmark_sector_returns
        ):
            sheet.brinson = self._brinson.analyze(
                portfolio_sector_weights,
                benchmark_sector_weights,
                portfolio_sector_returns,
                benchmark_sector_returns,
            )

        # 4. Factor attribution
        if factor_exposures and factor_returns_dict:
            sheet.factor_attribution = self._factor.analyze(
                sheet.metrics.total_return,
                factor_exposures,
                factor_returns_dict,
            )

        # 5. Monthly returns
        sheet.monthly_returns = self._metrics.compute_monthly_returns(
            portfolio_returns, benchmark_returns,
        )

        # 6. Top drawdowns
        sheet.top_drawdowns = self._metrics.compute_drawdowns(portfolio_returns)

        # 7. Rolling metrics
        sheet.rolling_sharpe, sheet.rolling_volatility = (
            self._metrics.compute_rolling(portfolio_returns)
        )

        return sheet

    def generate_summary(self, sheet: TearSheet) -> dict:
        """Generate a summary dict from a tear sheet.

        Args:
            sheet: Completed tear sheet.

        Returns:
            Summary dict suitable for display.
        """
        m = sheet.metrics
        summary = {
            "name": sheet.name,
            "period": sheet.period.value,
            "total_return": f"{m.total_return:.2%}",
            "annualized_return": f"{m.annualized_return:.2%}",
            "volatility": f"{m.volatility:.2%}",
            "sharpe_ratio": f"{m.sharpe_ratio:.2f}",
            "sortino_ratio": f"{m.sortino_ratio:.2f}",
            "max_drawdown": f"{m.max_drawdown:.2%}",
            "calmar_ratio": f"{m.calmar_ratio:.2f}",
            "win_rate": f"{m.win_rate:.1%}",
            "best_day": f"{m.best_day:.2%}",
            "worst_day": f"{m.worst_day:.2%}",
            "total_days": m.total_days,
        }

        if sheet.benchmark_comparison:
            bc = sheet.benchmark_comparison
            summary.update({
                "benchmark": bc.benchmark_name,
                "active_return": f"{bc.active_return:.2%}",
                "tracking_error": f"{bc.tracking_error:.2%}",
                "information_ratio": f"{bc.information_ratio:.2f}",
                "beta": f"{bc.beta:.2f}",
                "alpha": f"{bc.alpha:.2%}",
                "up_capture": f"{bc.up_capture:.2%}",
                "down_capture": f"{bc.down_capture:.2%}",
            })

        if sheet.brinson:
            b = sheet.brinson
            summary.update({
                "brinson_allocation": f"{b.total_allocation:.4f}",
                "brinson_selection": f"{b.total_selection:.4f}",
                "brinson_interaction": f"{b.total_interaction:.4f}",
            })

        return summary
