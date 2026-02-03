"""Advanced Risk-Adjusted Return Metrics.

Computes M-squared, Omega ratio, Gain-Loss ratio, Sterling ratio,
Burke ratio, Kappa ratios, and other advanced risk-adjusted metrics
beyond Sharpe/Sortino.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.attribution.config import (
    AttributionConfig,
    DEFAULT_ATTRIBUTION_CONFIG,
    TRADING_DAYS_PER_YEAR,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class RiskAdjustedMetrics:
    """Advanced risk-adjusted return metrics."""
    # Standard
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    treynor_ratio: float = 0.0

    # Advanced
    m_squared: float = 0.0
    m_squared_excess: float = 0.0
    omega_ratio: float = 0.0
    gain_loss_ratio: float = 0.0
    sterling_ratio: float = 0.0
    burke_ratio: float = 0.0
    kappa_3: float = 0.0
    tail_ratio: float = 0.0
    prospect_ratio: float = 0.0

    # Drawdown-based
    ulcer_index: float = 0.0
    pain_ratio: float = 0.0
    martin_ratio: float = 0.0

    @property
    def composite_score(self) -> float:
        """Composite risk-adjusted score (0-100)."""
        # Weighted combination of normalized metrics
        sharpe_component = min(30, max(0, (self.sharpe_ratio + 1) * 15))
        omega_component = min(25, max(0, (self.omega_ratio - 0.5) * 25))
        pain_component = min(25, max(0, (self.pain_ratio + 1) * 12.5))
        tail_component = min(20, max(0, self.tail_ratio * 10))
        return round(
            sharpe_component + omega_component + pain_component + tail_component,
            1,
        )


@dataclass
class MetricComparison:
    """Compare risk-adjusted metrics across strategies."""
    strategy_name: str = ""
    metrics: RiskAdjustedMetrics = field(default_factory=RiskAdjustedMetrics)
    rank: int = 0
    composite_score: float = 0.0


@dataclass
class RiskAdjustedReport:
    """Report comparing multiple strategies."""
    strategies: list[MetricComparison] = field(default_factory=list)
    best_strategy: str = ""
    best_score: float = 0.0

    @property
    def n_strategies(self) -> int:
        return len(self.strategies)


# ---------------------------------------------------------------------------
# Risk-Adjusted Analyzer
# ---------------------------------------------------------------------------
class RiskAdjustedAnalyzer:
    """Computes advanced risk-adjusted return metrics."""

    def __init__(self, config: Optional[AttributionConfig] = None) -> None:
        self.config = config or DEFAULT_ATTRIBUTION_CONFIG

    def compute(
        self,
        returns: list[float],
        benchmark_returns: Optional[list[float]] = None,
        risk_free_rate: Optional[float] = None,
        threshold: float = 0.0,
    ) -> RiskAdjustedMetrics:
        """Compute all risk-adjusted metrics.

        Args:
            returns: Daily portfolio returns.
            benchmark_returns: Daily benchmark returns (for beta-based metrics).
            risk_free_rate: Annualized risk-free rate.
            threshold: Minimum acceptable return for Omega/Kappa (daily).

        Returns:
            RiskAdjustedMetrics with all computed values.
        """
        if len(returns) < 10:
            return RiskAdjustedMetrics()

        arr = np.array(returns)
        rf = risk_free_rate if risk_free_rate is not None else self.config.risk_free_rate
        rf_daily = rf / self.config.trading_days_per_year
        tdy = self.config.trading_days_per_year
        excess = arr - rf_daily

        ann_return = float((np.prod(1 + arr) ** (tdy / len(arr))) - 1)
        ann_vol = float(np.std(arr) * np.sqrt(tdy))

        # Standard ratios
        sharpe = self._sharpe(excess, arr, tdy)
        sortino = self._sortino(excess, arr, rf_daily, tdy)
        calmar = self._calmar(ann_return, arr)
        treynor = self._treynor(ann_return, rf, arr, benchmark_returns)

        # M-squared
        m2, m2_excess = self._m_squared(arr, benchmark_returns, rf_daily, tdy)

        # Omega ratio
        omega = self._omega(arr, threshold)

        # Gain-loss ratio
        gain_loss = self._gain_loss(arr)

        # Sterling ratio
        sterling = self._sterling(ann_return, arr, rf)

        # Burke ratio
        burke = self._burke(ann_return, arr, rf, tdy)

        # Kappa 3 (lower partial moment order 3)
        kappa3 = self._kappa(arr, threshold, 3, tdy)

        # Tail ratio
        tail = self._tail_ratio(arr)

        # Prospect ratio
        prospect = self._prospect_ratio(arr)

        # Drawdown-based
        ulcer = self._ulcer_index(arr)
        pain = self._pain_ratio(ann_return, rf, arr)
        martin = self._martin_ratio(ann_return, rf, arr)

        return RiskAdjustedMetrics(
            sharpe_ratio=round(sharpe, 4),
            sortino_ratio=round(sortino, 4),
            calmar_ratio=round(calmar, 4),
            treynor_ratio=round(treynor, 4),
            m_squared=round(m2, 4),
            m_squared_excess=round(m2_excess, 4),
            omega_ratio=round(omega, 4),
            gain_loss_ratio=round(gain_loss, 4),
            sterling_ratio=round(sterling, 4),
            burke_ratio=round(burke, 4),
            kappa_3=round(kappa3, 4),
            tail_ratio=round(tail, 4),
            prospect_ratio=round(prospect, 4),
            ulcer_index=round(ulcer, 4),
            pain_ratio=round(pain, 4),
            martin_ratio=round(martin, 4),
        )

    def compare_strategies(
        self,
        strategy_returns: dict[str, list[float]],
        benchmark_returns: Optional[list[float]] = None,
    ) -> RiskAdjustedReport:
        """Compare risk-adjusted metrics across multiple strategies.

        Args:
            strategy_returns: {strategy_name: returns_list}.
            benchmark_returns: Common benchmark returns.

        Returns:
            RiskAdjustedReport with ranked strategies.
        """
        if not strategy_returns:
            return RiskAdjustedReport()

        comparisons = []
        for name, rets in strategy_returns.items():
            metrics = self.compute(rets, benchmark_returns)
            comparisons.append(MetricComparison(
                strategy_name=name,
                metrics=metrics,
                composite_score=metrics.composite_score,
            ))

        # Rank by composite score
        comparisons.sort(key=lambda c: c.composite_score, reverse=True)
        for i, c in enumerate(comparisons):
            c.rank = i + 1

        best = comparisons[0] if comparisons else MetricComparison()

        return RiskAdjustedReport(
            strategies=comparisons,
            best_strategy=best.strategy_name,
            best_score=best.composite_score,
        )

    # --- Private computation methods ---

    def _sharpe(self, excess: np.ndarray, arr: np.ndarray, tdy: int) -> float:
        std = float(np.std(arr))
        if std < 1e-10:
            return 0.0
        return float(np.mean(excess)) / std * np.sqrt(tdy)

    def _sortino(
        self, excess: np.ndarray, arr: np.ndarray, rf_daily: float, tdy: int
    ) -> float:
        downside = arr[arr < rf_daily] - rf_daily
        if len(downside) == 0:
            return 0.0
        dd_vol = float(np.sqrt(np.mean(downside ** 2)))
        if dd_vol < 1e-10:
            return 0.0
        return float(np.mean(excess)) / dd_vol * np.sqrt(tdy)

    def _calmar(self, ann_return: float, arr: np.ndarray) -> float:
        cum = np.cumprod(1 + arr)
        running_max = np.maximum.accumulate(cum)
        dd = (cum - running_max) / running_max
        max_dd = abs(float(np.min(dd)))
        if max_dd < 1e-10:
            return 0.0
        return ann_return / max_dd

    def _treynor(
        self,
        ann_return: float,
        rf: float,
        arr: np.ndarray,
        benchmark: Optional[list[float]],
    ) -> float:
        if benchmark is None or len(benchmark) != len(arr):
            return 0.0
        bm = np.array(benchmark)
        cov = float(np.cov(arr, bm)[0, 1])
        var_bm = float(np.var(bm))
        if var_bm < 1e-10:
            return 0.0
        beta = cov / var_bm
        if abs(beta) < 1e-10:
            return 0.0
        return (ann_return - rf) / beta

    def _m_squared(
        self,
        arr: np.ndarray,
        benchmark: Optional[list[float]],
        rf_daily: float,
        tdy: int,
    ) -> tuple[float, float]:
        """M-squared: portfolio return adjusted to benchmark volatility."""
        port_vol = float(np.std(arr))
        if benchmark is None or len(benchmark) == 0:
            return 0.0, 0.0
        bm = np.array(benchmark[:len(arr)])
        bm_vol = float(np.std(bm))
        if port_vol < 1e-10:
            return 0.0, 0.0

        excess_return = float(np.mean(arr - rf_daily))
        m2 = rf_daily + excess_return * (bm_vol / port_vol)
        m2_ann = m2 * tdy
        bm_ann = float(np.mean(bm)) * tdy
        m2_excess = m2_ann - bm_ann
        return m2_ann, m2_excess

    def _omega(self, arr: np.ndarray, threshold: float = 0.0) -> float:
        """Omega ratio: probability-weighted gain/loss ratio."""
        gains = arr[arr > threshold] - threshold
        losses = threshold - arr[arr <= threshold]
        total_loss = float(np.sum(losses))
        if total_loss < 1e-10:
            return 10.0  # Cap at 10 if no losses
        return float(np.sum(gains)) / total_loss

    def _gain_loss(self, arr: np.ndarray) -> float:
        """Gain-loss ratio: mean positive / mean negative return."""
        pos = arr[arr > 0]
        neg = arr[arr < 0]
        if len(neg) == 0:
            return 10.0
        mean_neg = abs(float(np.mean(neg)))
        if mean_neg < 1e-10:
            return 10.0
        return float(np.mean(pos)) / mean_neg if len(pos) > 0 else 0.0

    def _sterling(self, ann_return: float, arr: np.ndarray, rf: float) -> float:
        """Sterling ratio: excess return / average drawdown."""
        cum = np.cumprod(1 + arr)
        running_max = np.maximum.accumulate(cum)
        dd = (cum - running_max) / running_max
        avg_dd = abs(float(np.mean(dd[dd < 0]))) if (dd < 0).any() else 0.0
        if avg_dd < 1e-10:
            return 0.0
        return (ann_return - rf) / avg_dd

    def _burke(
        self, ann_return: float, arr: np.ndarray, rf: float, tdy: int
    ) -> float:
        """Burke ratio: excess return / sqrt(sum of squared drawdowns)."""
        cum = np.cumprod(1 + arr)
        running_max = np.maximum.accumulate(cum)
        dd = (cum - running_max) / running_max
        neg_dd = dd[dd < 0]
        if len(neg_dd) == 0:
            return 0.0
        burke_denom = float(np.sqrt(np.sum(neg_dd ** 2) / len(arr)))
        if burke_denom < 1e-10:
            return 0.0
        return (ann_return - rf) / burke_denom

    def _kappa(
        self, arr: np.ndarray, threshold: float, order: int, tdy: int
    ) -> float:
        """Kappa ratio (generalized Sortino)."""
        excess = arr - threshold
        ann_excess = float(np.mean(excess)) * tdy
        below = excess[excess < 0]
        if len(below) == 0:
            return 0.0
        lpm = float(np.mean(np.abs(below) ** order)) ** (1.0 / order)
        lpm_ann = lpm * np.sqrt(tdy)
        if lpm_ann < 1e-10:
            return 0.0
        return ann_excess / lpm_ann

    def _tail_ratio(self, arr: np.ndarray) -> float:
        """Tail ratio: 95th percentile / |5th percentile|."""
        p95 = float(np.percentile(arr, 95))
        p5 = abs(float(np.percentile(arr, 5)))
        if p5 < 1e-10:
            return 10.0
        return p95 / p5

    def _prospect_ratio(self, arr: np.ndarray) -> float:
        """Prospect ratio using loss aversion (lambda=2.25)."""
        loss_aversion = 2.25
        gains = arr[arr > 0]
        losses = arr[arr < 0]
        utility_gains = float(np.sum(gains)) if len(gains) > 0 else 0.0
        utility_losses = float(np.sum(np.abs(losses))) * loss_aversion if len(losses) > 0 else 0.0
        total = utility_gains + utility_losses
        if total < 1e-10:
            return 0.0
        return (utility_gains - utility_losses) / len(arr)

    def _ulcer_index(self, arr: np.ndarray) -> float:
        """Ulcer Index: RMS of drawdowns."""
        cum = np.cumprod(1 + arr)
        running_max = np.maximum.accumulate(cum)
        dd_pct = (cum - running_max) / running_max * 100
        return float(np.sqrt(np.mean(dd_pct ** 2)))

    def _pain_ratio(self, ann_return: float, rf: float, arr: np.ndarray) -> float:
        """Pain ratio: excess return / pain index (mean drawdown)."""
        cum = np.cumprod(1 + arr)
        running_max = np.maximum.accumulate(cum)
        dd = (cum - running_max) / running_max
        pain = abs(float(np.mean(dd)))
        if pain < 1e-10:
            return 0.0
        return (ann_return - rf) / pain

    def _martin_ratio(self, ann_return: float, rf: float, arr: np.ndarray) -> float:
        """Martin ratio (Ulcer Performance Index): excess return / ulcer index."""
        ui = self._ulcer_index(arr)
        if ui < 1e-10:
            return 0.0
        return (ann_return - rf) / (ui / 100)
