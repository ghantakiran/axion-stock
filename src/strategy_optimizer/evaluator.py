"""Strategy performance evaluator.

Measures the quality of a parameter set using trade history and equity-curve
data, producing a composite score normalised to 0-100.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class PerformanceMetrics:
    """Core performance metrics for a strategy configuration.

    All metrics are computed from trade history and / or an equity curve.
    """

    sharpe_ratio: float = 0.0
    total_return: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_trade_pnl: float = 0.0
    trade_count: int = 0
    calmar_ratio: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> PerformanceMetrics:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class EvaluationResult:
    """Output of a single strategy evaluation.

    Attributes:
        params: The parameter dict that was evaluated.
        metrics: Computed performance metrics.
        score: Composite score 0-100.
        evaluated_at: UTC timestamp.
        regime: Detected or assumed regime label.
    """

    params: dict[str, Any]
    metrics: PerformanceMetrics
    score: float = 0.0
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    regime: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "params": self.params,
            "metrics": self.metrics.to_dict(),
            "score": self.score,
            "evaluated_at": self.evaluated_at.isoformat(),
            "regime": self.regime,
        }


class StrategyEvaluator:
    """Evaluate a strategy parameter-set against historical trades.

    The composite score uses a weighted combination of normalised metrics:

        score = sharpe*0.30 + return*0.20 + (1-drawdown)*0.20
                + win_rate*0.15 + profit_factor*0.15

    Each component is clamped to [0, 1] before weighting, then
    the result is scaled to 0-100.
    """

    # -- weight constants ------------------------------------------------
    W_SHARPE = 0.30
    W_RETURN = 0.20
    W_DRAWDOWN = 0.20
    W_WINRATE = 0.15
    W_PROFIT_FACTOR = 0.15

    # -- normalisation bounds -------------------------------------------
    SHARPE_MAX = 3.0
    RETURN_MAX = 1.0  # 100 %
    PROFIT_FACTOR_MAX = 3.0

    def __init__(self, regime: str = "unknown") -> None:
        self.regime = regime

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        params: dict[str, Any],
        trades: list[dict[str, Any]],
        equity_curve: list[float] | None = None,
    ) -> EvaluationResult:
        """Evaluate *params* given *trades* and optional *equity_curve*.

        Parameters
        ----------
        params:
            Strategy configuration dict.
        trades:
            List of trade dicts with at least ``pnl`` and ``pnl_pct`` keys.
        equity_curve:
            Equity values over time.  Used for drawdown / Sharpe when present.

        Returns
        -------
        EvaluationResult
        """

        metrics = self._compute_metrics(trades, equity_curve)
        score = self.score(metrics)
        return EvaluationResult(
            params=params,
            metrics=metrics,
            score=score,
            regime=self.regime,
        )

    def score(self, metrics: PerformanceMetrics) -> float:
        """Compute composite 0-100 score from *metrics*."""

        sharpe_norm = _clamp(metrics.sharpe_ratio / self.SHARPE_MAX, 0.0, 1.0)
        return_norm = _clamp(metrics.total_return / self.RETURN_MAX, 0.0, 1.0)
        dd_norm = _clamp(1.0 - abs(metrics.max_drawdown), 0.0, 1.0)
        wr_norm = _clamp(metrics.win_rate, 0.0, 1.0)
        pf_norm = _clamp(metrics.profit_factor / self.PROFIT_FACTOR_MAX, 0.0, 1.0)

        raw = (
            self.W_SHARPE * sharpe_norm
            + self.W_RETURN * return_norm
            + self.W_DRAWDOWN * dd_norm
            + self.W_WINRATE * wr_norm
            + self.W_PROFIT_FACTOR * pf_norm
        )

        # Apply regime penalty for bear markets
        if self.regime == "bear":
            raw *= 0.9

        return round(_clamp(raw * 100.0, 0.0, 100.0), 2)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _compute_metrics(
        self,
        trades: list[dict[str, Any]],
        equity_curve: list[float] | None,
    ) -> PerformanceMetrics:
        if not trades:
            return PerformanceMetrics()

        pnls = [t.get("pnl", 0.0) or 0.0 for t in trades]
        pnl_pcts = [t.get("pnl_pct", 0.0) or 0.0 for t in trades]
        trade_count = len(trades)
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        win_rate = len(wins) / trade_count if trade_count else 0.0

        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (
            float("inf") if gross_profit > 0 else 0.0
        )
        # Cap profit factor for scoring
        if profit_factor == float("inf"):
            profit_factor = self.PROFIT_FACTOR_MAX

        avg_trade_pnl = sum(pnls) / trade_count if trade_count else 0.0
        total_return = sum(pnl_pcts)

        # Drawdown from equity curve or cumulative pnl
        if equity_curve and len(equity_curve) >= 2:
            max_drawdown = self._max_drawdown_from_curve(equity_curve)
        else:
            max_drawdown = self._max_drawdown_from_pnls(pnls)

        # Sharpe from pnl_pcts
        sharpe_ratio = self._sharpe(pnl_pcts)

        calmar_ratio = (
            (total_return / abs(max_drawdown)) if max_drawdown != 0 else 0.0
        )

        return PerformanceMetrics(
            sharpe_ratio=round(sharpe_ratio, 4),
            total_return=round(total_return, 4),
            max_drawdown=round(max_drawdown, 4),
            win_rate=round(win_rate, 4),
            profit_factor=round(min(profit_factor, 999.0), 4),
            avg_trade_pnl=round(avg_trade_pnl, 4),
            trade_count=trade_count,
            calmar_ratio=round(calmar_ratio, 4),
        )

    @staticmethod
    def _sharpe(returns: list[float], risk_free: float = 0.0) -> float:
        if len(returns) < 2:
            return 0.0
        mean_r = sum(returns) / len(returns)
        var = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std = math.sqrt(var) if var > 0 else 0.0
        if std == 0.0:
            return 0.0
        return (mean_r - risk_free) / std

    @staticmethod
    def _max_drawdown_from_curve(curve: list[float]) -> float:
        peak = curve[0]
        max_dd = 0.0
        for val in curve:
            if val > peak:
                peak = val
            dd = (val - peak) / peak if peak != 0 else 0.0
            if dd < max_dd:
                max_dd = dd
        return max_dd

    @staticmethod
    def _max_drawdown_from_pnls(pnls: list[float]) -> float:
        if not pnls:
            return 0.0
        equity = [100_000.0]
        for p in pnls:
            equity.append(equity[-1] + p)
        peak = equity[0]
        max_dd = 0.0
        for val in equity:
            if val > peak:
                peak = val
            dd = (val - peak) / peak if peak != 0 else 0.0
            if dd < max_dd:
                max_dd = dd
        return max_dd


# ── helpers ────────────────────────────────────────────────────────────


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))
