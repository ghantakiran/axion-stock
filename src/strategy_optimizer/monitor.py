"""Performance drift monitor for adaptive strategy optimizer.

Tracks live strategy performance against backtest expectations and
generates alerts when metrics diverge beyond configurable thresholds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.strategy_optimizer.evaluator import PerformanceMetrics, StrategyEvaluator


class DriftStatus(Enum):
    """Severity level of performance drift."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    STALE = "stale"


@dataclass
class DriftConfig:
    """Configuration for drift detection thresholds."""

    check_interval_hours: int = 24
    sharpe_threshold: float = 0.3
    drawdown_threshold: float = 0.15
    min_trades_for_check: int = 20
    lookback_days: int = 30


@dataclass
class DriftReport:
    """Result of a single drift check."""

    status: DriftStatus
    current_metrics: PerformanceMetrics
    baseline_metrics: PerformanceMetrics
    sharpe_ratio_delta: float = 0.0
    drawdown_delta: float = 0.0
    recommendation: str = ""
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "current_metrics": self.current_metrics.to_dict(),
            "baseline_metrics": self.baseline_metrics.to_dict(),
            "sharpe_ratio_delta": round(self.sharpe_ratio_delta, 4),
            "drawdown_delta": round(self.drawdown_delta, 4),
            "recommendation": self.recommendation,
            "checked_at": self.checked_at.isoformat(),
        }


class PerformanceDriftMonitor:
    """Monitor live strategy performance against backtest baselines."""

    def __init__(
        self,
        config: DriftConfig | None = None,
        baseline_metrics: PerformanceMetrics | None = None,
    ) -> None:
        self.config = config or DriftConfig()
        self.baseline = baseline_metrics or PerformanceMetrics()
        self._evaluator = StrategyEvaluator()
        self._history: list[DriftReport] = []

    def check(
        self,
        recent_trades: list[dict[str, Any]],
        equity_curve: list[float] | None = None,
    ) -> DriftReport:
        """Evaluate current performance vs baseline."""
        if len(recent_trades) < self.config.min_trades_for_check:
            report = DriftReport(
                status=DriftStatus.STALE,
                current_metrics=PerformanceMetrics(trade_count=len(recent_trades)),
                baseline_metrics=self.baseline,
                recommendation="insufficient trades for drift check",
            )
            self._history.append(report)
            return report

        eval_result = self._evaluator.evaluate({}, recent_trades, equity_curve)
        current = eval_result.metrics
        sharpe_delta = current.sharpe_ratio - self.baseline.sharpe_ratio
        drawdown_delta = current.max_drawdown - self.baseline.max_drawdown
        status = self._determine_status(sharpe_delta, drawdown_delta)
        recommendation = self.get_recommendation_text(status)

        report = DriftReport(
            status=status,
            current_metrics=current,
            baseline_metrics=self.baseline,
            sharpe_ratio_delta=round(sharpe_delta, 4),
            drawdown_delta=round(drawdown_delta, 4),
            recommendation=recommendation,
        )
        self._history.append(report)
        return report

    def get_recommendation(self, report: DriftReport) -> str:
        """Return healthy, reoptimize, or halt_and_review."""
        if report.status == DriftStatus.CRITICAL:
            return "halt_and_review"
        if report.status == DriftStatus.WARNING:
            return "reoptimize"
        return "healthy"

    def get_history(self) -> list[DriftReport]:
        """Return all past drift reports."""
        return list(self._history)

    def _determine_status(self, sharpe_delta: float, drawdown_delta: float) -> DriftStatus:
        """Map metric deltas to a DriftStatus severity level."""
        baseline_sharpe = self.baseline.sharpe_ratio
        sharpe_threshold_abs = (
            abs(baseline_sharpe) * self.config.sharpe_threshold
            if baseline_sharpe != 0
            else self.config.sharpe_threshold
        )
        sharpe_breach = sharpe_delta < -sharpe_threshold_abs
        drawdown_breach = drawdown_delta < -self.config.drawdown_threshold

        if sharpe_breach and drawdown_breach:
            return DriftStatus.CRITICAL
        if sharpe_breach or drawdown_breach:
            return DriftStatus.WARNING
        return DriftStatus.HEALTHY

    @staticmethod
    def get_recommendation_text(status: DriftStatus) -> str:
        """Map a DriftStatus to a human-readable recommendation string."""
        mapping = {
            DriftStatus.HEALTHY: "Strategy performing within expected bounds. No action needed.",
            DriftStatus.WARNING: "Performance drift detected. Consider re-optimizing parameters.",
            DriftStatus.CRITICAL: "Severe performance drift. Halt trading and review strategy.",
            DriftStatus.STALE: "Insufficient recent data for evaluation.",
        }
        return mapping.get(status, "Unknown status.")
