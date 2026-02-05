"""Drawdown Analysis.

Maximum drawdown computation, underwater curves, drawdown
duration analysis, and conditional drawdown metrics.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional
from datetime import date

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass
class DrawdownEvent:
    """A single drawdown episode."""
    start_idx: int = 0
    trough_idx: int = 0
    end_idx: Optional[int] = None  # None if ongoing
    peak_value: float = 0.0
    trough_value: float = 0.0
    drawdown_pct: float = 0.0
    duration_to_trough: int = 0
    recovery_duration: Optional[int] = None
    total_duration: Optional[int] = None

    @property
    def is_ongoing(self) -> bool:
        return self.end_idx is None

    @property
    def severity(self) -> str:
        dd = abs(self.drawdown_pct)
        if dd > 0.30:
            return "severe"
        elif dd > 0.15:
            return "significant"
        elif dd > 0.05:
            return "moderate"
        return "minor"

    @property
    def recovery_ratio(self) -> Optional[float]:
        """Recovery time / decline time."""
        if self.recovery_duration is None or self.duration_to_trough == 0:
            return None
        return self.recovery_duration / self.duration_to_trough


@dataclass
class DrawdownMetrics:
    """Comprehensive drawdown statistics."""
    symbol: str = ""
    max_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    current_drawdown: float = 0.0
    n_drawdowns: int = 0
    avg_duration: float = 0.0
    max_duration: int = 0
    avg_recovery_time: float = 0.0
    pct_time_underwater: float = 0.0
    calmar_ratio: Optional[float] = None  # Return / MaxDD
    ulcer_index: float = 0.0  # RMS of drawdowns

    @property
    def is_underwater(self) -> bool:
        return self.current_drawdown < -0.001

    @property
    def drawdown_risk_score(self) -> float:
        """0-100 score: higher = more drawdown risk."""
        # Combine multiple factors
        dd_component = min(abs(self.max_drawdown) * 200, 40)
        duration_component = min(self.avg_duration / 50, 30)
        freq_component = min(self.n_drawdowns * 2, 30)
        return round(dd_component + duration_component + freq_component, 2)


@dataclass
class UnderwaterCurve:
    """Underwater (drawdown) curve over time."""
    symbol: str = ""
    drawdowns: list[float] = field(default_factory=list)
    running_max: list[float] = field(default_factory=list)
    values: list[float] = field(default_factory=list)
    n_periods: int = 0

    @property
    def current_drawdown(self) -> float:
        return self.drawdowns[-1] if self.drawdowns else 0.0

    @property
    def max_drawdown(self) -> float:
        return min(self.drawdowns) if self.drawdowns else 0.0


@dataclass
class ConditionalDrawdown:
    """Conditional drawdown metrics (tail risk)."""
    symbol: str = ""
    cvar_5: float = 0.0  # Expected DD given DD > 5th percentile worst
    cvar_1: float = 0.0  # Expected DD given DD > 1st percentile worst
    expected_shortfall: float = 0.0
    worst_5_drawdowns: list[float] = field(default_factory=list)

    @property
    def tail_risk_ratio(self) -> float:
        """CVaR 1% / CVaR 5%."""
        if abs(self.cvar_5) < 0.0001:
            return 1.0
        return abs(self.cvar_1) / abs(self.cvar_5)


# ---------------------------------------------------------------------------
# Drawdown Analyzer
# ---------------------------------------------------------------------------
class DrawdownAnalyzer:
    """Analyzes drawdown characteristics of return series.

    Computes max drawdown, underwater curves, duration analysis,
    and conditional drawdown (tail risk) metrics.
    """

    def __init__(
        self,
        min_drawdown_threshold: float = 0.01,
    ) -> None:
        self.min_drawdown_threshold = min_drawdown_threshold

    def compute_underwater_curve(
        self,
        values: list[float],
        symbol: str = "",
    ) -> UnderwaterCurve:
        """Compute drawdown/underwater curve from value series.

        Args:
            values: Portfolio or asset values over time.
            symbol: Ticker symbol.

        Returns:
            UnderwaterCurve with drawdown at each point.
        """
        if not values:
            return UnderwaterCurve(symbol=symbol)

        arr = np.array(values, dtype=float)
        running_max = np.maximum.accumulate(arr)
        drawdowns = (arr - running_max) / np.where(running_max > 0, running_max, 1.0)

        return UnderwaterCurve(
            symbol=symbol,
            drawdowns=[round(float(d), 6) for d in drawdowns],
            running_max=[round(float(m), 2) for m in running_max],
            values=[round(float(v), 2) for v in arr],
            n_periods=len(values),
        )

    def identify_drawdown_events(
        self,
        values: list[float],
        symbol: str = "",
    ) -> list[DrawdownEvent]:
        """Identify individual drawdown episodes.

        Args:
            values: Portfolio or asset values over time.
            symbol: Ticker symbol.

        Returns:
            List of DrawdownEvent objects.
        """
        if len(values) < 2:
            return []

        curve = self.compute_underwater_curve(values, symbol)
        dd_arr = np.array(curve.drawdowns)

        events = []
        in_drawdown = False
        start_idx = 0
        trough_idx = 0
        trough_dd = 0.0
        peak_value = values[0]

        for i in range(len(dd_arr)):
            dd = dd_arr[i]

            if not in_drawdown:
                if dd < -self.min_drawdown_threshold:
                    # Start of drawdown
                    in_drawdown = True
                    start_idx = max(0, i - 1)
                    peak_value = float(curve.running_max[i])
                    trough_idx = i
                    trough_dd = dd
            else:
                if dd < trough_dd:
                    # Deeper trough
                    trough_idx = i
                    trough_dd = dd
                elif dd >= -0.001:
                    # Recovery complete
                    events.append(DrawdownEvent(
                        start_idx=start_idx,
                        trough_idx=trough_idx,
                        end_idx=i,
                        peak_value=peak_value,
                        trough_value=float(values[trough_idx]),
                        drawdown_pct=round(trough_dd, 6),
                        duration_to_trough=trough_idx - start_idx,
                        recovery_duration=i - trough_idx,
                        total_duration=i - start_idx,
                    ))
                    in_drawdown = False

        # Handle ongoing drawdown
        if in_drawdown:
            events.append(DrawdownEvent(
                start_idx=start_idx,
                trough_idx=trough_idx,
                end_idx=None,
                peak_value=peak_value,
                trough_value=float(values[trough_idx]),
                drawdown_pct=round(trough_dd, 6),
                duration_to_trough=trough_idx - start_idx,
                recovery_duration=None,
                total_duration=None,
            ))

        return events

    def compute_metrics(
        self,
        values: list[float],
        returns: Optional[list[float]] = None,
        symbol: str = "",
    ) -> DrawdownMetrics:
        """Compute comprehensive drawdown metrics.

        Args:
            values: Portfolio or asset values over time.
            returns: Optional return series (for Calmar ratio).
            symbol: Ticker symbol.

        Returns:
            DrawdownMetrics with all statistics.
        """
        if len(values) < 2:
            return DrawdownMetrics(symbol=symbol)

        curve = self.compute_underwater_curve(values, symbol)
        events = self.identify_drawdown_events(values, symbol)

        max_dd = float(min(curve.drawdowns))
        avg_dd = float(np.mean([d for d in curve.drawdowns if d < 0])) if any(d < 0 for d in curve.drawdowns) else 0.0
        current_dd = curve.current_drawdown

        # Duration stats
        completed_events = [e for e in events if not e.is_ongoing]
        if completed_events:
            avg_duration = float(np.mean([e.total_duration for e in completed_events]))
            max_duration = max(e.total_duration for e in completed_events)
            recovery_times = [e.recovery_duration for e in completed_events if e.recovery_duration]
            avg_recovery = float(np.mean(recovery_times)) if recovery_times else 0.0
        else:
            avg_duration = 0.0
            max_duration = 0
            avg_recovery = 0.0

        # Time underwater
        underwater_periods = sum(1 for d in curve.drawdowns if d < -0.001)
        pct_underwater = underwater_periods / len(curve.drawdowns) if curve.drawdowns else 0.0

        # Calmar ratio
        calmar = None
        if returns and len(returns) > 0 and abs(max_dd) > 0.001:
            ann_return = float(np.mean(returns)) * 252
            calmar = ann_return / abs(max_dd)

        # Ulcer index
        dd_squared = [d ** 2 for d in curve.drawdowns if d < 0]
        ulcer = float(np.sqrt(np.mean(dd_squared))) if dd_squared else 0.0

        return DrawdownMetrics(
            symbol=symbol,
            max_drawdown=round(max_dd, 6),
            avg_drawdown=round(avg_dd, 6),
            current_drawdown=round(current_dd, 6),
            n_drawdowns=len(events),
            avg_duration=round(avg_duration, 2),
            max_duration=max_duration,
            avg_recovery_time=round(avg_recovery, 2),
            pct_time_underwater=round(pct_underwater, 4),
            calmar_ratio=round(calmar, 4) if calmar else None,
            ulcer_index=round(ulcer, 6),
        )

    def conditional_drawdown(
        self,
        values: list[float],
        symbol: str = "",
    ) -> ConditionalDrawdown:
        """Compute conditional drawdown (CVaR) metrics.

        Args:
            values: Portfolio or asset values over time.
            symbol: Ticker symbol.

        Returns:
            ConditionalDrawdown with tail risk metrics.
        """
        curve = self.compute_underwater_curve(values, symbol)
        dd_arr = np.array(curve.drawdowns)

        # Only consider negative drawdowns
        negative_dd = dd_arr[dd_arr < 0]
        if len(negative_dd) < 10:
            return ConditionalDrawdown(symbol=symbol)

        sorted_dd = np.sort(negative_dd)  # Most negative first

        # CVaR 5% (expected value of worst 5%)
        n_5pct = max(1, int(len(sorted_dd) * 0.05))
        cvar_5 = float(np.mean(sorted_dd[:n_5pct]))

        # CVaR 1%
        n_1pct = max(1, int(len(sorted_dd) * 0.01))
        cvar_1 = float(np.mean(sorted_dd[:n_1pct]))

        # Worst 5 drawdowns
        worst_5 = [round(float(d), 6) for d in sorted_dd[:5]]

        return ConditionalDrawdown(
            symbol=symbol,
            cvar_5=round(cvar_5, 6),
            cvar_1=round(cvar_1, 6),
            expected_shortfall=round(cvar_5, 6),
            worst_5_drawdowns=worst_5,
        )

    def compare_drawdowns(
        self,
        metrics_list: list[DrawdownMetrics],
    ) -> dict:
        """Compare drawdown metrics across multiple assets.

        Args:
            metrics_list: List of DrawdownMetrics.

        Returns:
            Dict with ranking and comparison.
        """
        if not metrics_list:
            return {"symbols": [], "ranking": []}

        # Rank by max drawdown (least negative = best)
        ranked = sorted(metrics_list, key=lambda m: m.max_drawdown, reverse=True)

        return {
            "symbols": [m.symbol for m in ranked],
            "ranking": [
                {
                    "symbol": m.symbol,
                    "max_drawdown": m.max_drawdown,
                    "avg_duration": m.avg_duration,
                    "risk_score": m.drawdown_risk_score,
                    "calmar": m.calmar_ratio,
                }
                for m in ranked
            ],
            "best": ranked[0].symbol if ranked else "",
            "worst": ranked[-1].symbol if ranked else "",
            "avg_max_dd": round(float(np.mean([m.max_drawdown for m in metrics_list])), 6),
        }
